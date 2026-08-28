"""Reproducible per-source diagnostics for external search ([Q2], tareas.md).

Runs the real IMDb/Wikipedia/FilmAffinity adapters against recorded HTTP
responses (`search_lab.recorded_responses`) and, for every raw candidate
each source actually returns, scores it with the same
`domain.search.external_result_score()` production uses. That gives a
report that can tell "the source never returned this work" apart from
"Movie Inbox found it and discarded it", per query variant, per source,
per declared language -- see docs/search-quality.md for the corpus this
is meant to protect and why it needed real adapter execution rather than
a hand-scored candidate list (the older `context: "external"` cases in
`search_lab/corpus/v1.json`, still in use and untouched by this module).
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from movie_inbox.application.search_evaluation import SearchCorpusError, evaluate_gate
from movie_inbox.domain.search import external_result_score
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy
from movie_inbox.external.filmaffinity import FilmAffinityAdapter
from movie_inbox.external.imdb import ImdbAdapter, imdb_id_from_text
from movie_inbox.external.wikipedia import WikipediaAdapter
from movie_inbox.search_lab.recorded_responses import (
    UnrecordedRequestError,
    replay_recorded_responses,
)

DIAGNOSTICS_SCHEMA_VERSION = 1
DEFAULT_TOP_K = 5

_ADAPTERS: dict[str, Callable[[], Any]] = {
    "imdb": ImdbAdapter,
    "wikipedia": WikipediaAdapter,
    "filmaffinity": FilmAffinityAdapter,
}

# One recognizer per source: does this list of actually-requested URLs show
# evidence the source's own fallback path fired? Reads the adapters' real
# behavior (imdb.py:71-78, wikipedia.py:100-117) -- never the adapters
# themselves, which stay untouched.
_FALLBACK_SIGNATURES: dict[str, Callable[[Sequence[str]], bool]] = {
    "imdb": lambda urls: any("wikidata.org" in url for url in urls),
    "wikipedia": lambda urls: any("redirects=1" in url and "titles=" in url for url in urls),
    "filmaffinity": lambda urls: False,
}


def validate_diagnostics_corpus(corpus: Mapping[str, Any]) -> None:
    if not isinstance(corpus.get("cases"), list) or not corpus["cases"]:
        raise SearchCorpusError("External diagnostics corpus needs a non-empty 'cases' list")
    for case in corpus["cases"]:
        if not isinstance(case, Mapping):
            raise SearchCorpusError("Every diagnostics case must be an object")
        for key in ("id", "label", "language", "stage", "queries", "sources"):
            if key not in case:
                raise SearchCorpusError(f"Diagnostics case missing '{key}': {case.get('id')}")
        if case["stage"] not in {"punctuation", "alias_expansion", "year_parsing"}:
            raise SearchCorpusError(f"Unsupported stage in case {case['id']}: {case['stage']}")
        if not isinstance(case["queries"], list) or not case["queries"]:
            raise SearchCorpusError(f"Case {case['id']} needs a non-empty 'queries' list")
        if not isinstance(case["sources"], Mapping) or not case["sources"]:
            raise SearchCorpusError(f"Case {case['id']} needs a non-empty 'sources' object")
        for source_name, source_case in case["sources"].items():
            if source_name not in _ADAPTERS:
                raise SearchCorpusError(f"Unknown source '{source_name}' in case {case['id']}")
            if "expected_key" not in source_case and "forbidden_keys" not in source_case:
                raise SearchCorpusError(
                    f"{case['id']}/{source_name} needs expected_key and/or forbidden_keys"
                )
            if "recorded_responses" not in source_case:
                raise SearchCorpusError(f"{case['id']}/{source_name} needs recorded_responses")


def evaluate_external_diagnostics(
    corpus: Mapping[str, Any], strategy: SearchStrategy = PRODUCTION_BASELINE
) -> dict[str, Any]:
    """Run the packaged multilingual diagnostics corpus for real."""
    validate_diagnostics_corpus(corpus)
    started = time.perf_counter()
    case_results = [_evaluate_case(case, strategy) for case in corpus["cases"]]
    metrics = _aggregate_metrics(case_results)
    thresholds = dict(corpus.get("thresholds") or {})
    gate = evaluate_gate(metrics, thresholds)
    return {
        "report_type": "search_external_diagnostics",
        "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithm": strategy.name,
        "corpus": {
            "name": str(corpus.get("name") or "unnamed"),
            "description": str(corpus.get("description") or ""),
            "case_count": len(case_results),
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "gate": gate,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "cases": case_results,
    }


def _evaluate_case(case: Mapping[str, Any], strategy: SearchStrategy) -> dict[str, Any]:
    top_k = int(case.get("top_k") or DEFAULT_TOP_K)
    trials: list[dict[str, Any]] = []
    for query in case["queries"]:
        for source_name, source_case in case["sources"].items():
            trials.append(_evaluate_trial(case, query, source_name, source_case, top_k, strategy))
    failures = [trial["failure"] for trial in trials if trial["failure"]]
    return {
        "id": case["id"],
        "label": case["label"],
        "language": case["language"],
        "stage": case["stage"],
        "passed": not failures,
        "failures": failures,
        "trials": trials,
    }


def _evaluate_trial(
    case: Mapping[str, Any],
    query: str,
    source_name: str,
    source_case: Mapping[str, Any],
    top_k: int,
    strategy: SearchStrategy,
) -> dict[str, Any]:
    expected_key = str(source_case.get("expected_key") or "")
    forbidden_keys = {str(key) for key in source_case.get("forbidden_keys") or []}
    recorded_responses = source_case.get("recorded_responses") or {}

    try:
        with replay_recorded_responses(recorded_responses) as log:
            raw_results = _ADAPTERS[source_name]().search(query)
        requested_urls = log.urls
        fetch_error = ""
    except UnrecordedRequestError as error:
        raw_results, requested_urls = [], []
        fetch_error = str(error)

    scored = sorted(
        (
            (
                external_result_score(query, result, strategy),
                index,
                _result_key(source_name, result),
            )
            for index, result in enumerate(raw_results)
        ),
        key=lambda entry: (-entry[0], entry[1]),
    )
    candidates = [
        {
            "key": key,
            "score": round(score, 1),
            "rank_in_raw": position,
            "accepted": score >= strategy.external_relevance_threshold,
        }
        for position, (score, _, key) in enumerate(scored, start=1)
    ]
    accepted_keys_in_top_k = {row["key"] for row in candidates[:top_k] if row["accepted"]}
    forbidden_hit = sorted(forbidden_keys & accepted_keys_in_top_k)
    found = expected_key and expected_key in accepted_keys_in_top_k
    expected_row = next((row for row in candidates if row["key"] == expected_key), None)

    fallback_signature = _FALLBACK_SIGNATURES.get(source_name)
    fallback_used = fallback_signature(requested_urls) if fallback_signature else False

    failure = ""
    if fetch_error:
        failure = f"fixture_error: {fetch_error}"
    elif forbidden_hit:
        failure = f"forbidden_accepted: {', '.join(forbidden_hit)}"
    elif expected_key and not found:
        if expected_row is None:
            failure = "source_did_not_return_it"
        elif not expected_row["accepted"]:
            failure = f"discarded_by_threshold: score={expected_row['score']}"
        else:
            failure = f"accepted_outside_top_k: rank={expected_row['rank_in_raw']}"

    return {
        "case_id": case["id"],
        "query": query,
        "source": source_name,
        "expected_key": expected_key or None,
        "forbidden_keys": sorted(forbidden_keys),
        "requested_urls": requested_urls,
        "fallback_used": fallback_used,
        "candidates": candidates,
        "found": bool(found),
        "failure": failure,
    }


def _result_key(source_name: str, result: Mapping[str, Any]) -> str:
    if source_name == "imdb":
        return imdb_id_from_text(str(result.get("url") or ""))
    return str(result.get("url") or "").strip().rstrip("/").casefold()


def _aggregate_metrics(case_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    all_trials = [trial for case in case_results for trial in case["trials"]]
    graded_trials = [trial for trial in all_trials if trial["expected_key"]]
    found = sum(1 for trial in graded_trials if trial["found"])
    forbidden_hits = sum(
        1 for trial in all_trials if trial["failure"].startswith("forbidden_accepted")
    )
    source_missing = sum(
        1 for trial in graded_trials if trial["failure"] == "source_did_not_return_it"
    )
    discarded_by_threshold = sum(
        1 for trial in graded_trials if trial["failure"].startswith("discarded_by_threshold")
    )

    by_language_source: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"trials": 0, "found": 0})
    )
    for case in case_results:
        for trial in case["trials"]:
            if not trial["expected_key"]:
                continue
            bucket = by_language_source[case["language"]][trial["source"]]
            bucket["trials"] += 1
            bucket["found"] += int(trial["found"])
    recall_by_language_source = {
        language: {
            source: round(bucket["found"] / bucket["trials"], 4) if bucket["trials"] else 1.0
            for source, bucket in sources.items()
        }
        for language, sources in by_language_source.items()
    }

    return {
        "case_count": len(case_results),
        "passed_cases": sum(1 for case in case_results if case["passed"]),
        "trial_count": len(all_trials),
        "graded_trial_count": len(graded_trials),
        "recall_at_5": round(found / len(graded_trials), 4) if graded_trials else 1.0,
        "recall_at_5_by_language_source": recall_by_language_source,
        "forbidden_hits": forbidden_hits,
        "source_did_not_return_it": source_missing,
        "discarded_by_threshold": discarded_by_threshold,
        "fallback_used_count": sum(1 for trial in all_trials if trial["fallback_used"]),
    }


__all__ = [
    "DEFAULT_TOP_K",
    "DIAGNOSTICS_SCHEMA_VERSION",
    "evaluate_external_diagnostics",
    "validate_diagnostics_corpus",
]
