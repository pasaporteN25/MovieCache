from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_inbox.domain.search import EXTERNAL_RELEVANCE_THRESHOLD, external_result_score
from movie_inbox.external.filmaffinity import (
    FilmAffinityAdapter,
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
            <dd><span id="country-img">
<img class="nflag" src="/imgs/countries2/US.png" alt="Estados Unidos">
</span>&nbsp;Estados Unidos</dd>
            <dt>Dirección</dt>
            <dd class="directors">
<div class="credits">
<span class="nb" itemprop="director" itemscope="" itemtype="http://schema.org/Person">
<a class="link" itemprop="url"
   href="https://www.filmaffinity.com/es/name.php?name-id=101626315"
   title="Michael Mann"><span itemprop="name">Michael Mann</span></a>
</span></div>            </dd>
            <dt>Guion</dt>
            <dd><div class="credits"><span class="nb">
<a href="https://www.filmaffinity.com/es/name.php?name-id=101626315"
   title="Michael Mann">Michael Mann</a>
</span></div></dd>
            <dt>Reparto</dt>
            <dd class="card-cast-debug">
                <div class="cast-wrapper">
<ul class="credits-scroller">
<li class="nb" itemprop="actor" itemscope="" itemtype="http://schema.org/Person">
<a class="link" itemprop="url"
   href="https://www.filmaffinity.com/es/name.php?name-id=627577077"
   title="Robert De Niro">
<img src="https://pics.filmaffinity.com/robert_de_niro.jpg" alt="Robert De Niro">
<div class="name" itemprop="name">Robert De Niro</div></a></li>
<li class="nb" itemprop="actor" itemscope="" itemtype="http://schema.org/Person">
<a class="link" itemprop="url"
   href="https://www.filmaffinity.com/es/name.php?name-id=951364861"
   title="Al Pacino">
<img src="https://pics.filmaffinity.com/al_pacino.jpg" alt="Al Pacino">
<div class="name" itemprop="name">Al Pacino</div></a></li>
<li class="nb" itemprop="actor" itemscope="" itemtype="http://schema.org/Person">
<a class="link" itemprop="url"
   href="https://www.filmaffinity.com/es/name.php?name-id=322187927"
   title="Val Kilmer">
<img src="https://pics.filmaffinity.com/val_kilmer.jpg" alt="Val Kilmer">
<div class="name" itemprop="name">Val Kilmer</div></a></li>
<li class="see-more-cre">
<a href="https://www.filmaffinity.com/es/fullcredits.php?movie_id=267267">
 Ver todos los creditos</a></li>
</ul>
                </div>
            </dd>
            <dt>Música</dt>
            <dd><div class="credits"><span class="nb">
<a href="https://www.filmaffinity.com/es/name.php?name-id=538285107"
   title="Elliot Goldenthal">Elliot Goldenthal</a>
</span></div></dd>
            <dt>Fotografía</dt>
            <dd><div class="credits"><span class="nb">
<a href="https://www.filmaffinity.com/es/name.php?name-id=547183953"
   title="Dante Spinotti">Dante Spinotti</a>
</span></div></dd>
<style>.card-producer .credits {display: inline;} </style>

            <dt>Compañías</dt>
            <dd class="card-producer">
<div class="credits"><span class="nb">
<a href="https://www.filmaffinity.com/es/name.php?name-id=241265159"
   title="Warner Bros">Warner Bros</a>,</span>
<span class="nb">
<a href="https://www.filmaffinity.com/es/name.php?name-id=697760714"
   title="Regency Enterprises">Regency Enterprises</a>.</span>
</div>            </dd>

            <dt>Género</dt>
            <dd class="card-genres">
                <span itemprop="genre">
<a href="https://www.filmaffinity.com/es/moviegenre.php?genre=TH&amp;attr=rat_count&amp;nodoc">
Thriller</a></span>.
                <span itemprop="genre">
<a href="https://www.filmaffinity.com/es/moviegenre.php?genre=AC&amp;attr=rat_count&amp;nodoc">
Acción</a></span>.
                <span itemprop="genre">
<a href="https://www.filmaffinity.com/es/moviegenre.php?genre=INT&amp;attr=rat_count&amp;nodoc">
Intriga</a></span> |
                <a href="https://www.filmaffinity.com/es/movietopic.php?topic=124690&amp;attr=rat_count&amp;nodoc">
Policíaco</a>
            </dd>

        <dt>Sinopsis</dt>
        <dd class="" itemprop="description">Neil McCauley (Robert De Niro) es un
experto ladrón. Su filosofía consiste en vivir sin ataduras ni vínculos que
puedan constituir un obstáculo si las cosas se complican. (FILMAFFINITY)</dd>
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


# Captured from https://www.filmaffinity.com/es/search.php on 2026-09-10 through
# the adapter's own fetch_text, then trimmed. Searching an original title the
# site recognises does not return a listing at all: it serves the film's own
# page. The trim keeps the tags both parsers read, verbatim -- the Open Graph
# pair that says which kind of response this is, the title/year/synopsis
# microdata, and the two navigation anchors ("Ficha", "Imagenes") the listing
# parser used to return as if they were films. Verified rather than eyeballed:
# this body and the full 117 KB one produce an identical result row.
SPIRITED_AWAY_SEARCH_HTML = """<html><head><meta property="og:type" content="video." ><meta property="og:url" content="https://www.filmaffinity.com/es/film759533.html" ></head><body><h1 id="main-title">
        <span itemprop="name">El viaje de Chihiro</span>
        
        <span class="movie-type"><span class="type">Animación</span></span>
        
    </h1><dt>Título original</dt>
            <dd>
                Sen to Chihiro no kamikakushi<span class="show-akas ui-corner-all" >aka <i class="fa-solid fa-caret-down"></i></span>             </dd><dd itemprop="datePublished">2001</dd><dd class="" itemprop="description">Chihiro es una niña de diez años que viaja en coche con sus padres. Después de atravesar un túnel, llegan a un mundo fantástico, en el que no hay lugar para los seres humanos, sólo para los dioses de primera y segunda clase. Cuando descubre que sus padres han sido convertidos en cerdos, Chihiro se siente muy sola y asustada. (FILMAFFINITY)</dd><a class="active" href="https://www.filmaffinity.com/es/film759533.html">

                                <span class="icon d-md-none"><i class="fa-light fa-film"></i></span>

                                <span class="d-none d-md-block">Ficha&nbsp;</span>

                            </a><a  href="https://www.filmaffinity.com/es/filmimages.php?movie_id=759533">

                                <span class="icon d-md-none"><i class="fa-light fa-images"></i></span>

                                <span class="d-none d-md-block">Imágenes&nbsp;<em>[113]</em></span>

                            </a></body></html>"""

# The same search endpoint answering with an actual listing, for the same query
# shape. Two result cards, verbatim, from the response to "Der Untergang".
LISTING_SEARCH_HTML = """<html><head><meta property="og:type" content="website" ><meta property="og:url" content="https%3A%2F%2Fwww.filmaffinity.com%2Fes%2Fsearch.php%3Fstext%3DDer%2520Untergang"></head><body><div class="fs-6 mc-title">

                    <a class="d-none d-md-inline-block" href="https://www.filmaffinity.com/es/film599984.html">El hundimiento</a>

                    <a class="d-md-none stretched-link" href="https://www.filmaffinity.com/es/film599984.html">El hundimiento</a>

                </div><div class="fs-6 mc-title">

                    <a class="d-none d-md-inline-block" href="https://www.filmaffinity.com/es/film592705.html">Stalingrado: el ataque, el cerco y la caída</a>

                    <a class="d-md-none stretched-link" href="https://www.filmaffinity.com/es/film592705.html">Stalingrado: el ataque, el cerco y la caída</a>

                </div></body></html>"""


class SearchResolvingToAFilmPageTests(unittest.TestCase):
    """[B1]: a search that lands on a film page has to be read as one.

    Measured against the live site before the fix. Searching "Sen to Chihiro no
    kamikakushi" returned eight rows and not one of them was the film: the top
    two were the page's own navigation, titled "Ficha" and "Imagenes", and the
    rest were other Ghibli films from the related rail. "Ficha" scored 10.2 and
    the relevance floor is 28.0, so FilmAffinity contributed nothing at all for
    a query whose answer was at the top of the response it sent.
    """

    def _search(self, query: str, body: str) -> list[dict[str, object]]:
        with patch("movie_inbox.external.filmaffinity.fetch_text", return_value=body):
            return FilmAffinityAdapter()._fetch(query)

    def test_the_film_page_is_read_as_the_film(self) -> None:
        [row] = self._search("Sen to Chihiro no kamikakushi", SPIRITED_AWAY_SEARCH_HTML)

        self.assertEqual(row["title"], "El viaje de Chihiro")
        self.assertEqual(row["original_title"], "Sen to Chihiro no kamikakushi")
        self.assertEqual(row["year"], "2001")
        self.assertEqual(row["url"], "https://www.filmaffinity.com/es/film759533.html")

    def test_the_page_navigation_is_no_longer_returned_as_films(self) -> None:
        rows = self._search("Sen to Chihiro no kamikakushi", SPIRITED_AWAY_SEARCH_HTML)

        titles = [str(row["title"]) for row in rows]
        self.assertNotIn("Ficha", titles)
        self.assertFalse([title for title in titles if title.startswith("Im")])

    def test_the_original_title_is_what_makes_the_row_score(self) -> None:
        # The whole point: the query is in the original language and the site
        # answers in Spanish. Without the original title travelling with the
        # row there is nothing for the query to match.
        [row] = self._search("Sen to Chihiro no kamikakushi", SPIRITED_AWAY_SEARCH_HTML)

        score = external_result_score("Sen to Chihiro no kamikakushi", row)

        self.assertGreaterEqual(score, EXTERNAL_RELEVANCE_THRESHOLD)

    def test_a_listing_is_still_read_as_a_listing(self) -> None:
        # The same endpoint answers both ways; only the response says which.
        rows = self._search("Der Untergang", LISTING_SEARCH_HTML)

        self.assertEqual(
            [row["url"] for row in rows],
            [
                "https://www.filmaffinity.com/es/film599984.html",
                "https://www.filmaffinity.com/es/film592705.html",
            ],
        )


if __name__ == "__main__":
    unittest.main()
