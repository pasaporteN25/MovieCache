"""[F6.1] end to end: a real index built from TSV, reaching the gateway."""

from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import movie_inbox.infrastructure.external_catalog as external_catalog
from movie_inbox.external.imdb_dataset_source import ImdbDatasetSource
from movie_inbox.infrastructure.imdb_dataset_index import build_index

BASICS = "\t".join(
    [
        "tconst",
        "titleType",
        "primaryTitle",
        "originalTitle",
        "isAdult",
        "startYear",
        "endYear",
        "runtimeMinutes",
        "genres",
    ]
)
AKAS = "\t".join(
    [
        "titleId",
        "ordering",
        "title",
        "region",
        "language",
        "types",
        "attributes",
        "isOriginalTitle",
    ]
)


def write_dataset(root: Path) -> Path:
    basics = root / "title.basics.tsv.gz"
    akas = root / "title.akas.tsv.gz"
    with gzip.open(basics, "wt", encoding="utf-8") as handle:
        handle.write(BASICS + "\n")
        handle.write("tt0113277\tmovie\tHeat\tHeat\t0\t1995\t\\N\t170\tAction,Crime,Drama\n")
        # A mini-series, the case normalize_kind gets wrong on its own.
        handle.write(
            "tt0306414\ttvMiniSeries\tThe Wire\tThe Wire\t0\t2002\t2008\t59\tCrime,Drama\n"
        )
        # An episode: the index must decline to classify it at all.
        handle.write("tt0959621\ttvEpisode\tPine Barrens\tPine Barrens\t0\t2001\t\\N\t56\tDrama\n")
    with gzip.open(akas, "wt", encoding="utf-8") as handle:
        handle.write(AKAS + "\n")
        handle.write("tt0113277\t1\tFuego contra fuego\tAR\t\\N\t\\N\t\\N\t0\n")
        handle.write("tt0113277\t2\tHeat\tUS\t\\N\t\\N\t\\N\t1\n")
        handle.write("tt0113277\t3\tHiito\tJP\t\\N\t\\N\t\\N\t0\n")
    destination = root / "imdb-dataset.db"
    build_index(basics, akas, destination)
    return destination


class ImdbDatasetGatewayTests(unittest.TestCase):
    def test_a_real_index_contributes_the_matrix_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index = write_dataset(Path(temporary))
            source = ImdbDatasetSource(index)

            heat = source.metadata_for("tt0113277")
            self.assertEqual(heat["year"], "1995")
            self.assertEqual(heat["kind"], "pelicula")
            self.assertEqual(heat["duration_minutes"], 170)
            self.assertEqual(heat["genres"], "Action,Crime,Drama")
            self.assertIn("Fuego contra fuego", heat["alternative_titles"])
            self.assertNotIn("Hiito", heat["alternative_titles"])

            # The case that motivated the translation table.
            self.assertEqual(source.metadata_for("tt0306414")["kind"], "serie")
            # An episode contributes structured data but never a kind.
            self.assertNotIn("kind", source.metadata_for("tt0959621"))

            self.assertEqual(source.metadata_for("tt9999999"), {})

    def test_the_configured_gateway_lets_the_index_win_over_a_live_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index = write_dataset(Path(temporary))
            # Stand in for the live source with a deliberately wrong year plus a
            # field the index has no claim on, to see which of each survives.
            live = {
                "year": "1996",
                "description": "de Wikipedia",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
            }
            try:
                with patch.object(external_catalog, "fetch_metadata", lambda url, **_: dict(live)):
                    external_catalog.configure_external_catalog(imdb_dataset_index_path=str(index))
                    loader = external_catalog.EXTERNAL_CATALOG.metadata_loader
                    metadata = loader("https://es.wikipedia.org/wiki/Heat")
            finally:
                external_catalog.configure_external_catalog()

            self.assertEqual(metadata["year"], "1995", "el indice local es la autoridad de [Q5]")
            self.assertEqual(metadata["duration_minutes"], 170)
            # A field outside the index's lane comes through untouched.
            self.assertEqual(metadata["description"], "de Wikipedia")

    def test_without_an_index_the_gateway_behaves_exactly_as_before(self) -> None:
        live = {"year": "1996", "imdb_url": "https://www.imdb.com/title/tt0113277/"}
        try:
            with patch.object(external_catalog, "fetch_metadata", lambda url, **_: dict(live)):
                external_catalog.configure_external_catalog()
                metadata = external_catalog.EXTERNAL_CATALOG.metadata_loader("https://imdb.com/x")
        finally:
            external_catalog.configure_external_catalog()
        self.assertEqual(metadata["year"], "1996")


if __name__ == "__main__":
    unittest.main()
