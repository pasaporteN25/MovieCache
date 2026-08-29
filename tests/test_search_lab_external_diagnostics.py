from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from movie_inbox.application.search_evaluation import SearchCorpusError
from movie_inbox.search_lab import load_builtin_external_diagnostics_corpus
from movie_inbox.search_lab.external_diagnostics import (
    evaluate_external_diagnostics,
    validate_diagnostics_corpus,
)

IMDB_URL = "https://v3.sg.media-imdb.com/suggestion/x/heat.json"
_WIKIDATA_SEARCH_URL = (
    "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json"
    "&language={lang}&uselang={lang}&type=item&limit=5&search={query}"
)


def _corpus(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": 1, "name": "unit-test", "thresholds": {}, "cases": cases}


def _empty_wikidata_searches(quoted_query: str) -> dict[str, dict[str, Any]]:
    """The 3 (es/en/ja) wbsearchentities calls fetch_wikidata_title_matches
    fans out to, each recorded as finding nothing -- fills out a fixture
    for a query that's expected to trigger IMDb's alias-bridge fallback
    without an entity match actually being available to rescue the score."""
    return {
        _WIKIDATA_SEARCH_URL.format(lang=lang, query=quoted_query): {"search": []}
        for lang in ("es", "en", "ja")
    }


class ValidateDiagnosticsCorpusTests(unittest.TestCase):
    def test_an_empty_cases_list_is_rejected(self) -> None:
        with self.assertRaises(SearchCorpusError):
            validate_diagnostics_corpus(_corpus([]))

    def test_a_case_missing_a_required_field_is_rejected(self) -> None:
        case = {
            "id": "x",
            "label": "x",
            "language": "en",
            "stage": "punctuation",
            "queries": ["Heat"],
        }
        with self.assertRaises(SearchCorpusError):
            validate_diagnostics_corpus(_corpus([case]))

    def test_an_unsupported_stage_is_rejected(self) -> None:
        case = {
            "id": "x",
            "label": "x",
            "language": "en",
            "stage": "not-a-real-stage",
            "queries": ["Heat"],
            "sources": {"imdb": {"expected_key": "tt1", "recorded_responses": {}}},
        }
        with self.assertRaises(SearchCorpusError):
            validate_diagnostics_corpus(_corpus([case]))

    def test_a_source_without_expected_or_forbidden_keys_is_rejected(self) -> None:
        case = {
            "id": "x",
            "label": "x",
            "language": "en",
            "stage": "punctuation",
            "queries": ["Heat"],
            "sources": {"imdb": {"recorded_responses": {}}},
        }
        with self.assertRaises(SearchCorpusError):
            validate_diagnostics_corpus(_corpus([case]))

    def test_an_unknown_source_name_is_rejected(self) -> None:
        case = {
            "id": "x",
            "label": "x",
            "language": "en",
            "stage": "punctuation",
            "queries": ["Heat"],
            "sources": {"not-a-real-source": {"expected_key": "tt1", "recorded_responses": {}}},
        }
        with self.assertRaises(SearchCorpusError):
            validate_diagnostics_corpus(_corpus([case]))


class EvaluateExternalDiagnosticsTests(unittest.TestCase):
    def test_a_result_below_threshold_is_reported_as_discarded_not_missing(self) -> None:
        # A below-threshold IMDb result also makes the adapter's own
        # Wikidata alias bridge fire (imdb.py:71-78) -- record it as empty
        # so the fallback completes instead of raising for a missing URL,
        # keeping this test isolated to the threshold-discard path.
        case = {
            "id": "low-score",
            "label": "Discarded by threshold",
            "language": "en",
            "stage": "alias_expansion",
            "queries": ["Heat"],
            "sources": {
                "imdb": {
                    "expected_key": "tt0113277",
                    "recorded_responses": {
                        IMDB_URL: {
                            "d": [
                                {
                                    "id": "tt0113277",
                                    "l": "A Completely Unrelated Title",
                                    "qid": "movie",
                                }
                            ]
                        },
                        **_empty_wikidata_searches("Heat"),
                    },
                }
            },
        }

        report = evaluate_external_diagnostics(_corpus([case]))

        trial = report["cases"][0]["trials"][0]
        self.assertFalse(trial["found"])
        self.assertTrue(trial["failure"].startswith("discarded_by_threshold"))
        self.assertEqual(report["metrics"]["discarded_by_threshold"], 1)
        self.assertEqual(report["metrics"]["source_did_not_return_it"], 0)

    def test_a_missing_candidate_is_reported_as_source_did_not_return_it(self) -> None:
        # [Q3]: an empty suggestion response now also triggers IMDb's Wikidata
        # bridge (imdb.py), so this needs empty search fixtures too, or the
        # harness raises UnrecordedRequestError instead of exercising the
        # "genuinely nothing found" path this test means to cover.
        case = {
            "id": "empty-source",
            "label": "Source returns nothing at all",
            "language": "en",
            "stage": "alias_expansion",
            "queries": ["Heat"],
            "sources": {
                "imdb": {
                    "expected_key": "tt0113277",
                    "recorded_responses": {
                        IMDB_URL: {"d": []},
                        **_empty_wikidata_searches("Heat"),
                    },
                }
            },
        }

        report = evaluate_external_diagnostics(_corpus([case]))

        trial = report["cases"][0]["trials"][0]
        self.assertFalse(trial["found"])
        self.assertEqual(trial["failure"], "source_did_not_return_it")
        self.assertEqual(report["metrics"]["source_did_not_return_it"], 1)
        self.assertEqual(report["metrics"]["discarded_by_threshold"], 0)

    def test_a_forbidden_key_accepted_into_top_k_fails_the_case(self) -> None:
        case = {
            "id": "false-positive",
            "label": "A decoy scores high enough to be accepted",
            "language": "en",
            "stage": "alias_expansion",
            "queries": ["Heat"],
            "sources": {
                "imdb": {
                    "forbidden_keys": ["tt9999999"],
                    "recorded_responses": {
                        IMDB_URL: {"d": [{"id": "tt9999999", "l": "Heat", "qid": "movie"}]}
                    },
                }
            },
        }

        report = evaluate_external_diagnostics(_corpus([case]))

        self.assertFalse(report["cases"][0]["passed"])
        self.assertIn("forbidden_accepted", report["cases"][0]["trials"][0]["failure"])
        self.assertEqual(report["metrics"]["forbidden_hits"], 1)

    def test_fallback_used_is_true_only_when_the_wikidata_bridge_actually_fires(self) -> None:
        imdb_url = "https://v3.sg.media-imdb.com/suggestion/x/addio_zio_tom.json"
        low_score_body = {
            "d": [{"id": "tt0180396", "l": "An Unrelated Suggestion", "qid": "movie"}]
        }
        case = {
            "id": "fallback-check",
            "label": "Low score triggers the bridge",
            "language": "it",
            "stage": "alias_expansion",
            "queries": ["Addio zio Tom"],
            "sources": {
                "imdb": {
                    "expected_key": "tt0180396",
                    "recorded_responses": {
                        imdb_url: low_score_body,
                        **_empty_wikidata_searches("Addio%20zio%20Tom"),
                    },
                }
            },
        }

        report = evaluate_external_diagnostics(_corpus([case]))

        trial = report["cases"][0]["trials"][0]
        self.assertTrue(trial["fallback_used"])
        self.assertEqual(report["metrics"]["fallback_used_count"], 1)
        # No Wikidata entity matched (empty search results), so the bridge
        # fired but couldn't rescue the low score -- still discarded.
        self.assertTrue(trial["failure"].startswith("discarded_by_threshold"))

    def test_recall_is_broken_down_by_language_and_source(self) -> None:
        found_case = {
            "id": "found",
            "label": "Found",
            "language": "en",
            "stage": "punctuation",
            "queries": ["Heat"],
            "sources": {
                "imdb": {
                    "expected_key": "tt0113277",
                    "recorded_responses": {
                        IMDB_URL: {
                            "d": [{"id": "tt0113277", "l": "Heat", "qid": "movie", "y": 1995}]
                        }
                    },
                }
            },
        }
        missing_case = {
            "id": "missing",
            "label": "Not found",
            "language": "it",
            "stage": "punctuation",
            "queries": ["Heat"],
            "sources": {
                "imdb": {
                    "expected_key": "tt0113277",
                    "recorded_responses": {
                        IMDB_URL: {"d": []},
                        **_empty_wikidata_searches("Heat"),
                    },
                }
            },
        }

        report = evaluate_external_diagnostics(_corpus([found_case, missing_case]))

        by_language = report["metrics"]["recall_at_5_by_language_source"]
        self.assertEqual(by_language["en"]["imdb"], 1.0)
        self.assertEqual(by_language["it"]["imdb"], 0.0)
        self.assertEqual(report["metrics"]["recall_at_5"], 0.5)

    def test_an_unrecorded_url_fails_the_trial_instead_of_reaching_the_network(self) -> None:
        case = {
            "id": "stale-fixture",
            "label": "Fixture missing a URL the adapter now requests",
            "language": "en",
            "stage": "punctuation",
            "queries": ["Heat"],
            "sources": {"imdb": {"expected_key": "tt0113277", "recorded_responses": {}}},
        }

        report = evaluate_external_diagnostics(_corpus([case]))

        trial = report["cases"][0]["trials"][0]
        self.assertTrue(trial["failure"].startswith("fixture_error"))
        self.assertIn(IMDB_URL, trial["failure"])

    def test_the_packaged_corpus_passes_its_own_gate(self) -> None:
        corpus = load_builtin_external_diagnostics_corpus()

        report = evaluate_external_diagnostics(corpus)

        self.assertTrue(report["gate"]["passed"], report["gate"])
        self.assertEqual(report["metrics"]["forbidden_hits"], 0)
        self.assertGreaterEqual(len(report["cases"]), 3)

    def test_the_packaged_corpus_never_reaches_the_real_network(self) -> None:
        # "Corre en CI sin red" as something actually asserted, not just
        # true because every fixture happens to be complete today.
        with mock.patch("movie_inbox.external.common.urlopen") as urlopen:
            urlopen.side_effect = AssertionError("must not touch the real network")
            evaluate_external_diagnostics(load_builtin_external_diagnostics_corpus())
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
