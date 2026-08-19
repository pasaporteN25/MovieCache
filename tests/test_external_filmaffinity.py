from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_inbox.external.filmaffinity import (
    FilmAffinityMetadataParser,
    fetch_filmaffinity_metadata,
)

# Captured from https://www.filmaffinity.com/es/film267267.html (Heat, 1995) on
# 2026-08-18, trimmed of unrelated chrome. The rating div and the dl.movie-info
# block -- the only parts fetch_filmaffinity_metadata reads -- keep the real
# schema.org microdata, including the quirks the parser has to handle: "Titulo
# original" and "Guion" (writers) carry no itemprop, the cast carousel ends in
# a "Ver todos los creditos" <li> with no itemprop="actor", and the genre <dd>
# also lists broader topic tags after a "|" that must not count as genres.
HEAT_FILM_PAGE_HTML = """
<html>
<head><title>Heat (1995) - Filmaffinity</title></head>
<body>
<h1 id="main-title">
        <span itemprop="name">Heat</span>

        <span class="movie-type"></span>

    </h1>
<div id="movie-rat-avg" itemprop="ratingValue" content="7.5">
                        7,5                    </div>
<dl class="movie-info">
            <dt>Título original</dt>
            <dd>
                Heat            </dd>

            <dt>Año</dt>
            <dd itemprop="datePublished">1995</dd>

            <dt>Duración</dt>
            <dd itemprop="duration">172 min.</dd>

            <dt>País</dt>
            <dd><span id="country-img"><img class="nflag" src="/imgs/countries2/US.png" alt="Estados Unidos"></span>&nbsp;Estados Unidos</dd>
            <dt>Dirección</dt>
            <dd class="directors">
<div class="credits"><span class="nb" itemprop="director" itemscope="" itemtype="http://schema.org/Person"><a class="link" itemprop="url" href="https://www.filmaffinity.com/es/name.php?name-id=101626315" title="Michael Mann"><span itemprop="name">Michael Mann</span></a></span></div>            </dd>
            <dt>Guion</dt>
            <dd><div class="credits"><span class="nb"><a href="https://www.filmaffinity.com/es/name.php?name-id=101626315" title="Michael Mann">Michael Mann</a></span></div></dd>
            <dt>Reparto</dt>
            <dd class="card-cast-debug">
                <div class="cast-wrapper">
<ul class="credits-scroller">
<li class="nb" itemprop="actor" itemscope="" itemtype="http://schema.org/Person"><a class="link" itemprop="url" href="https://www.filmaffinity.com/es/name.php?name-id=627577077" title="Robert De Niro"><img src="https://pics.filmaffinity.com/robert_de_niro.jpg" alt="Robert De Niro"><div class="name" itemprop="name">Robert De Niro</div></a></li>
<li class="nb" itemprop="actor" itemscope="" itemtype="http://schema.org/Person"><a class="link" itemprop="url" href="https://www.filmaffinity.com/es/name.php?name-id=951364861" title="Al Pacino"><img src="https://pics.filmaffinity.com/al_pacino.jpg" alt="Al Pacino"><div class="name" itemprop="name">Al Pacino</div></a></li>
<li class="nb" itemprop="actor" itemscope="" itemtype="http://schema.org/Person"><a class="link" itemprop="url" href="https://www.filmaffinity.com/es/name.php?name-id=322187927" title="Val Kilmer"><img src="https://pics.filmaffinity.com/val_kilmer.jpg" alt="Val Kilmer"><div class="name" itemprop="name">Val Kilmer</div></a></li>
<li class="see-more-cre"><a href="https://www.filmaffinity.com/es/fullcredits.php?movie_id=267267"> Ver todos los creditos</a></li>
</ul>
                </div>
            </dd>
            <dt>Música</dt>
            <dd><div class="credits"><span class="nb"><a href="https://www.filmaffinity.com/es/name.php?name-id=538285107" title="Elliot Goldenthal">Elliot Goldenthal</a></span></div></dd>
            <dt>Fotografía</dt>
            <dd><div class="credits"><span class="nb"><a href="https://www.filmaffinity.com/es/name.php?name-id=547183953" title="Dante Spinotti">Dante Spinotti</a></span></div></dd>
<style>.card-producer .credits {display: inline;} </style>

            <dt>Compañías</dt>
            <dd class="card-producer">
<div class="credits"><span class="nb"><a href="https://www.filmaffinity.com/es/name.php?name-id=241265159" title="Warner Bros">Warner Bros</a>,</span> <span class="nb"><a href="https://www.filmaffinity.com/es/name.php?name-id=697760714" title="Regency Enterprises">Regency Enterprises</a>.</span></div>            </dd>

            <dt>Género</dt>
            <dd class="card-genres">
                <span itemprop="genre"><a href="https://www.filmaffinity.com/es/moviegenre.php?genre=TH&amp;attr=rat_count&amp;nodoc">Thriller</a></span>.                 <span itemprop="genre"><a href="https://www.filmaffinity.com/es/moviegenre.php?genre=AC&amp;attr=rat_count&amp;nodoc">Acción</a></span>.                 <span itemprop="genre"><a href="https://www.filmaffinity.com/es/moviegenre.php?genre=INT&amp;attr=rat_count&amp;nodoc">Intriga</a></span> |                 <a href="https://www.filmaffinity.com/es/movietopic.php?topic=124690&amp;attr=rat_count&amp;nodoc">Policíaco</a>
            </dd>

        <dt>Sinopsis</dt>
        <dd class="" itemprop="description">Neil McCauley (Robert De Niro) es un experto ladrón. Su filosofía consiste en vivir sin ataduras ni vínculos que puedan constituir un obstáculo si las cosas se complican. (FILMAFFINITY)</dd>
    </dl>
</body>
</html>
"""


class FilmAffinityMetadataParserTests(unittest.TestCase):
    def test_parser_reads_schema_org_microdata_from_a_real_film_page(self) -> None:
        parser = FilmAffinityMetadataParser()
        parser.feed(HEAT_FILM_PAGE_HTML)

        self.assertEqual(parser.display_title, "Heat")
        self.assertEqual(parser.original_title, "Heat")
        self.assertEqual(parser.year, "1995")
        self.assertEqual(parser.genres, ["Thriller", "Acción", "Intriga"])
        self.assertEqual(parser.directors, ["Michael Mann"])
        self.assertEqual(parser.writers, ["Michael Mann"])
        self.assertEqual(parser.cast, ["Robert De Niro", "Al Pacino", "Val Kilmer"])
        self.assertIn("Neil McCauley", parser.description)
        self.assertIn("(FILMAFFINITY)", parser.description)

    def test_broader_topic_tags_after_the_genre_list_are_not_counted_as_genres(self) -> None:
        parser = FilmAffinityMetadataParser()
        parser.feed(HEAT_FILM_PAGE_HTML)

        self.assertNotIn("Policíaco", parser.genres)

    def test_the_trailing_see_more_credits_entry_is_not_counted_as_cast(self) -> None:
        parser = FilmAffinityMetadataParser()
        parser.feed(HEAT_FILM_PAGE_HTML)

        self.assertNotIn("Ver todos los creditos", parser.cast)
        self.assertEqual(len(parser.cast), 3)


class FetchFilmAffinityMetadataTests(unittest.TestCase):
    @patch("movie_inbox.external.filmaffinity.fetch_text")
    def test_returns_a_catalog_shaped_dict_for_a_filmaffinity_url(self, fetch_text) -> None:
        fetch_text.return_value = HEAT_FILM_PAGE_HTML

        metadata = fetch_filmaffinity_metadata("https://www.filmaffinity.com/es/film267267.html")

        self.assertEqual(metadata["title"], "Heat")
        self.assertEqual(metadata["spanish_title"], "Heat")
        self.assertEqual(metadata["original_title"], "Heat")
        self.assertEqual(metadata["year"], "1995")
        self.assertEqual(metadata["directors"], ["Michael Mann"])
        self.assertEqual(metadata["writers"], ["Michael Mann"])
        self.assertEqual(metadata["cast"][:2], ["Robert De Niro", "Al Pacino"])
        self.assertEqual(metadata["url"], "https://www.filmaffinity.com/es/film267267.html")
        self.assertEqual(
            metadata["filmaffinity_url"], "https://www.filmaffinity.com/es/film267267.html"
        )

    @patch("movie_inbox.external.filmaffinity.fetch_text")
    def test_does_not_smuggle_the_community_rating_into_the_personal_rating_field(
        self, fetch_text
    ) -> None:
        # CatalogItem.rating is the user's own 0-10 score (PRODUCT.md); there is
        # no schema field yet for an external site's own rating, so this must
        # not invent a "rating" key that a future merge could confuse with it.
        fetch_text.return_value = HEAT_FILM_PAGE_HTML

        metadata = fetch_filmaffinity_metadata("https://www.filmaffinity.com/es/film267267.html")

        self.assertNotIn("rating", metadata)

    def test_rejects_urls_from_other_sources_without_fetching(self) -> None:
        self.assertEqual(
            fetch_filmaffinity_metadata("https://en.wikipedia.org/wiki/Heat_(1995_film)"), {}
        )


if __name__ == "__main__":
    unittest.main()
