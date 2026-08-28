from __future__ import annotations

import json
import unittest

from movie_inbox.external import common as external_common
from movie_inbox.external import filmaffinity as external_filmaffinity
from movie_inbox.external.filmaffinity import FilmAffinityAdapter
from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.wikipedia import WikipediaAdapter
from movie_inbox.search_lab.recorded_responses import (
    UnrecordedRequestError,
    record_live_responses,
    replay_recorded_responses,
)

IMDB_SUGGESTION_URL = "https://v3.sg.media-imdb.com/suggestion/x/heat.json"
IMDB_SUGGESTION_BODY = {"d": [{"id": "tt0113277", "l": "Heat", "qid": "movie", "y": 1995}]}


class ReplayRecordedResponsesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_common_fetch_text = external_common.fetch_text
        # filmaffinity.py imports fetch_text without re-exporting it, so mypy's
        # strict re-export check doesn't consider this attribute typed public
        # API -- deliberate here, this test exists specifically to verify the
        # harness's monkey-patch on it.
        self.original_filmaffinity_fetch_text = external_filmaffinity.fetch_text  # type: ignore[attr-defined]

    def test_replay_serves_the_recorded_body_and_captures_the_url(self) -> None:
        with replay_recorded_responses({IMDB_SUGGESTION_URL: IMDB_SUGGESTION_BODY}) as log:
            results = ImdbAdapter().search("Heat")

        self.assertEqual(results[0]["title"], "Heat")
        self.assertEqual(results[0]["url"], "https://www.imdb.com/title/tt0113277/")
        self.assertEqual(log.urls, [IMDB_SUGGESTION_URL])

    def test_a_native_json_fixture_and_an_equivalent_json_string_produce_the_same_result(
        self,
    ) -> None:
        with replay_recorded_responses({IMDB_SUGGESTION_URL: IMDB_SUGGESTION_BODY}) as log:
            from_dict = ImdbAdapter().search("Heat")
        with replay_recorded_responses(
            {IMDB_SUGGESTION_URL: json.dumps(IMDB_SUGGESTION_BODY)}
        ) as log2:
            from_string = ImdbAdapter().search("Heat")

        self.assertEqual(from_dict, from_string)
        self.assertEqual(log.urls, log2.urls)

    def test_filmaffinity_is_intercepted_despite_importing_fetch_text_directly(self) -> None:
        # The regression this guards: filmaffinity.py does
        # `from movie_inbox.external.common import fetch_text` and calls
        # the bare name -- a binding independent of common.py's own
        # attribute. Patching only external_common.fetch_text would leave
        # this call going out to the real network.
        with replay_recorded_responses(
            {"https://www.filmaffinity.com/es/search.php?stext=Heat": ""}
        ) as log:
            results = FilmAffinityAdapter().search("Heat")

        self.assertEqual(results, [])
        self.assertEqual(log.urls, ["https://www.filmaffinity.com/es/search.php?stext=Heat"])

    def test_an_unrecorded_url_raises_and_names_the_exact_url(self) -> None:
        with replay_recorded_responses({}):
            with self.assertRaises(UnrecordedRequestError) as raised:
                ImdbAdapter().search("Heat")

        self.assertEqual(raised.exception.url, IMDB_SUGGESTION_URL)

    def test_the_patch_is_restored_even_if_the_block_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            with replay_recorded_responses({}):
                raise RuntimeError("boom")

        self.assertIs(external_common.fetch_text, self.original_common_fetch_text)
        self.assertIs(
            external_filmaffinity.fetch_text,  # type: ignore[attr-defined]
            self.original_filmaffinity_fetch_text,
        )

    def test_concurrent_requests_from_a_thread_pool_are_all_captured(self) -> None:
        # WikipediaAdapter fans en/es out across a real ThreadPoolExecutor --
        # this is the scenario the RequestLog lock exists for.
        en_url = (
            "https://en.wikipedia.org/w/api.php?action=query&generator=search"
            "&gsrsearch=Heat%20film&gsrlimit=8&gsrnamespace=0&gsrenablerewrites=1"
            "&prop=extracts%7Cpageimages%7Cpageprops&exintro=1&explaintext=1"
            "&pithumbsize=480&format=json&formatversion=2"
        )
        es_url = (
            "https://es.wikipedia.org/w/api.php?action=query&generator=search"
            "&gsrsearch=Heat%20pelicula&gsrlimit=8&gsrnamespace=0&gsrenablerewrites=1"
            "&prop=extracts%7Cpageimages%7Cpageprops&exintro=1&explaintext=1"
            "&pithumbsize=480&format=json&formatversion=2"
        )
        empty_query_result: dict[str, object] = {"query": {"pages": []}}
        resolve_title_bodies = {
            "https://en.wikipedia.org/w/api.php?action=query&redirects=1"
            "&prop=extracts%7Cpageimages%7Cpageprops%7Cinfo&exintro=1&explaintext=1"
            "&pithumbsize=480&inprop=url&format=json&formatversion=2"
            "&titles=Heat": empty_query_result,
            "https://es.wikipedia.org/w/api.php?action=query&redirects=1"
            "&prop=extracts%7Cpageimages%7Cpageprops%7Cinfo&exintro=1&explaintext=1"
            "&pithumbsize=480&inprop=url&format=json&formatversion=2"
            "&titles=Heat": empty_query_result,
        }
        responses = {en_url: empty_query_result, es_url: empty_query_result, **resolve_title_bodies}

        with replay_recorded_responses(responses) as log:
            WikipediaAdapter().search("Heat")

        self.assertIn(en_url, log.urls)
        self.assertIn(es_url, log.urls)


class RecordLiveResponsesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_common_fetch_text = external_common.fetch_text

    def test_record_mode_captures_the_pair_and_still_returns_the_body(self) -> None:
        # Stand in for "the real network" with our own stub, patched before
        # record_live_responses() captures its reference to the current
        # fetch_text -- this test never touches the actual network.
        def fake_fetch_text(url: str, accept: str = "", timeout: float = 0) -> str:
            return json.dumps(IMDB_SUGGESTION_BODY)

        external_common.fetch_text = fake_fetch_text
        try:
            with record_live_responses() as (log, captured):
                results = ImdbAdapter().search("Heat")
        finally:
            external_common.fetch_text = self.original_common_fetch_text

        self.assertEqual(results[0]["title"], "Heat")
        self.assertEqual(log.urls, [IMDB_SUGGESTION_URL])
        self.assertEqual(json.loads(captured[IMDB_SUGGESTION_URL]), IMDB_SUGGESTION_BODY)


if __name__ == "__main__":
    unittest.main()
