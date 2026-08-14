"""Deterministic, read-only evaluation of the production search pipelines."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from movie_inbox.application.library_service import ManagedLibraryService, _CatalogMatchIndex
from movie_inbox.application.search_service import rank_catalog_candidates, search_catalog_items
from movie_inbox.domain.catalog import canonical_url
from movie_inbox.domain.libraries import work_identity, work_identity_key
from movie_inbox.domain.matching import decide_match
from movie_inbox.domain.search import external_result_score


CORPUS_SCHEMA_VERSION = 1
SUPPORTED_CONTEXTS = {"catalog", "identity", "external", "scanner"}
DEFAULT_TOP_K = 5


class SearchCorpusError(ValueError):
    """Raised when a Search Lab corpus cannot be evaluated safely."""


def evaluate_search_corpus(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Run the current production rankers against a deterministic corpus."""
    validate_search_corpus(corpus)
    started = time.perf_counter()
    items = [dict(row) for row in corpus["catalog_items"]]
    case_results = [_evaluate_case(case, items) for case in corpus["cases"]]
    metrics = _aggregate_metrics(case_results)
    thresholds = dict(corpus.get("thresholds") or {})
    gate = _evaluate_gate(metrics, thresholds)
    return {
        "report_type": "search_corpus",
        "schema_version": CORPUS_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithm": "production-baseline",
        "corpus": {
            "name": str(corpus.get("name") or "unnamed"),
            "description": str(corpus.get("description") or ""),
            "case_count": len(case_results),
            "catalog_item_count": len(items),
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "gate": gate,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "cases": case_results,
    }


def inspect_catalog_search(
    items: Sequence[Mapping[str, Any]],
    query: str,
    *,
    mode: str = "catalog",
    year: str = "",
    kind: str = "pelicula",
    limit: int = 20,
) -> dict[str, Any]:
    """Inspect a JSON export without mutating it or consulting the network."""
    clean_query = " ".join(str(query or "").split())
    if len(clean_query) < 2:
        raise SearchCorpusError("Search Lab queries must contain at least two characters")
    if mode not in {"catalog", "identity", "scanner"}:
        raise SearchCorpusError(f"Unsupported inspection mode: {mode}")
    rows = [dict(item) for item in items]
    started = time.perf_counter()
    classification = ""
    if mode == "catalog":
        ranked = search_catalog_items(rows, clean_query, limit=limit)
        results = [_result_summary(row) for row in ranked]
    elif mode == "identity":
        candidate = {"title": clean_query, "year": str(year or ""), "kind": kind}
        ranked = rank_catalog_candidates(rows, candidate, limit=limit)
        results = [_result_summary(row) for row in ranked]
    else:
        candidate = {"title": clean_query, "year": str(year or ""), "kind": kind}
        results, classification = _scanner_results(rows, candidate)
        results = results[:limit]
    return {
        "report_type": "search_inspection",
        "schema_version": CORPUS_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithm": "production-baseline",
        "query": clean_query,
        "mode": mode,
        "year": str(year or ""),
        "kind": kind,
        "classification": classification,
        "catalog_item_count": len(rows),
        "result_count": len(results),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "results": results,
    }


def validate_search_corpus(corpus: Mapping[str, Any]) -> None:
    if not isinstance(corpus, Mapping):
        raise SearchCorpusError("Search Lab corpus root must be an object")
    if corpus.get("schema_version") != CORPUS_SCHEMA_VERSION:
        raise SearchCorpusError(f"Search Lab corpus must use schema_version {CORPUS_SCHEMA_VERSION}")
    items = corpus.get("catalog_items")
    cases = corpus.get("cases")
    if not isinstance(items, list) or any(not isinstance(row, Mapping) for row in items):
        raise SearchCorpusError("catalog_items must be an array of objects")
    if not isinstance(cases, list) or not cases or any(not isinstance(row, Mapping) for row in cases):
        raise SearchCorpusError("cases must be a non-empty array of objects")
    item_ids = [str(row.get("id") or "").strip() for row in items]
    if any(not item_id for item_id in item_ids) or len(item_ids) != len(set(item_ids)):
        raise SearchCorpusError("Every catalog item must have a unique non-empty id")
    catalog_ids = set(item_ids)
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        case_id = str(case.get("id") or "").strip()
        context = str(case.get("context") or "").strip()
        if not case_id or case_id in case_ids:
            raise SearchCorpusError(f"cases[{index}] must have a unique non-empty id")
        case_ids.add(case_id)
        if context not in SUPPORTED_CONTEXTS:
            raise SearchCorpusError(f"cases[{index}].context must be one of {sorted(SUPPORTED_CONTEXTS)}")
        if context in {"catalog", "external"} and not str(case.get("query") or "").strip():
            raise SearchCorpusError(f"cases[{index}].query is required")
        if context in {"identity", "scanner"} and not isinstance(case.get("candidate"), Mapping):
            raise SearchCorpusError(f"cases[{index}].candidate must be an object")
        if context in {"identity", "scanner"} and not str(case["candidate"].get("title") or "").strip():
            raise SearchCorpusError(f"cases[{index}].candidate.title is required")
        allowed_result_ids = catalog_ids
        if context == "external":
            results = case.get("results")
            if not isinstance(results, list) or any(not isinstance(row, Mapping) for row in results):
                raise SearchCorpusError(f"cases[{index}].results must be an array of objects")
            external_ids = [_result_key(row) for row in results]
            if any(not result_id for result_id in external_ids) or len(external_ids) != len(set(external_ids)):
                raise SearchCorpusError(f"cases[{index}].results must have unique stable ids or URLs")
            allowed_result_ids = set(external_ids)
        relevant = _string_list(case.get("relevant_ids"), f"cases[{index}].relevant_ids")
        forbidden = _string_list(case.get("forbidden_ids"), f"cases[{index}].forbidden_ids")
        if set(relevant) & set(forbidden):
            raise SearchCorpusError(f"cases[{index}] cannot mark the same result relevant and forbidden")
        unknown_ids = (set(relevant) | set(forbidden)) - allowed_result_ids
        if unknown_ids:
            raise SearchCorpusError(f"cases[{index}] references unknown result ids: {', '.join(sorted(unknown_ids))}")
        top_k = case.get("top_k", DEFAULT_TOP_K)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise SearchCorpusError(f"cases[{index}].top_k must be a positive integer")
        expected_acceptance = case.get("expected_acceptance", {})
        if not isinstance(expected_acceptance, Mapping) or any(
            str(key) not in allowed_result_ids or not isinstance(value, bool)
            for key, value in expected_acceptance.items()
        ):
            raise SearchCorpusError(f"cases[{index}].expected_acceptance must map known ids to booleans")
        required_reasons = case.get("required_reasons", {})
        if not isinstance(required_reasons, Mapping) or any(
            str(key) not in allowed_result_ids
            or not isinstance(value, list)
            or not value
            or any(not isinstance(reason, str) or not reason for reason in value)
            for key, value in required_reasons.items()
        ):
            raise SearchCorpusError(f"cases[{index}].required_reasons must map known ids to reason arrays")
        expected_classification = str(case.get("expected_classification") or "")
        if expected_classification and (context != "scanner" or expected_classification not in {"matched", "review", "new"}):
            raise SearchCorpusError(f"cases[{index}].expected_classification is invalid")
    thresholds = corpus.get("thresholds", {})
    if not isinstance(thresholds, Mapping):
        raise SearchCorpusError("thresholds must be an object")
    for name, value in thresholds.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SearchCorpusError(f"thresholds.{name} must be numeric")
        if name in {"precision_at_5", "mrr", "recall_at_5", "auto_match_precision"} and not 0 <= value <= 1:
            raise SearchCorpusError(f"thresholds.{name} must be between zero and one")
        if name in {"forbidden_hits", "auto_match_false_positives", "expectation_failures"} and value < 0:
            raise SearchCorpusError(f"thresholds.{name} cannot be negative")


def _evaluate_case(case: Mapping[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    context = str(case["context"])
    classification = ""
    if context == "catalog":
        ranked = search_catalog_items(items, str(case["query"]), limit=max(60, int(case.get("top_k", 5))))
        results = [_result_summary(row) for row in ranked]
    elif context == "identity":
        ranked = rank_catalog_candidates(
            items,
            dict(case["candidate"]),
            limit=max(60, int(case.get("top_k", 5))),
        )
        results = [_result_summary(row) for row in ranked]
    elif context == "external":
        results = _external_results(str(case["query"]), case["results"])
    else:
        results, classification = _scanner_results(items, case["candidate"])

    top_k = int(case.get("top_k", DEFAULT_TOP_K))
    top_results = results[:top_k]
    relevant = set(_string_list(case.get("relevant_ids"), "relevant_ids"))
    forbidden = set(_string_list(case.get("forbidden_ids"), "forbidden_ids"))
    ranked_keys = [str(row.get("key") or "") for row in top_results]
    hits = [key for key in ranked_keys if key in relevant]
    forbidden_hits = [key for key in ranked_keys if key in forbidden]
    if relevant:
        precision = len(hits) / len(top_results) if top_results else 0.0
        recall = len(set(hits)) / len(relevant)
        first_rank = next((index for index, key in enumerate(ranked_keys, 1) if key in relevant), 0)
        reciprocal_rank = 1.0 / first_rank if first_rank else 0.0
    else:
        precision = 1.0 if not top_results else 0.0
        recall = 1.0
        reciprocal_rank = 1.0 if not top_results else 0.0

    accepted = [row for row in results if bool(row.get("accepted"))]
    accepted_true = [str(row["key"]) for row in accepted if str(row.get("key") or "") in relevant]
    accepted_false = [str(row["key"]) for row in accepted if str(row.get("key") or "") not in relevant]
    expectation_failures = _expectation_failures(case, results, classification)
    passed = (
        precision == 1.0
        and recall == 1.0
        and not forbidden_hits
        and not accepted_false
        and not expectation_failures
    )
    return {
        "id": str(case["id"]),
        "label": str(case.get("label") or case["id"]),
        "context": context,
        "query": str(case.get("query") or (case.get("candidate") or {}).get("title") or ""),
        "top_k": top_k,
        "relevant_ids": sorted(relevant),
        "forbidden_ids": sorted(forbidden),
        "classification": classification,
        "metrics": {
            "precision_at_k": round(precision, 4),
            "recall_at_k": round(recall, 4),
            "reciprocal_rank": round(reciprocal_rank, 4),
            "forbidden_hits": len(forbidden_hits),
            "accepted_true_positives": len(accepted_true),
            "accepted_false_positives": len(accepted_false),
            "expectation_failures": len(expectation_failures),
        },
        "forbidden_hits": forbidden_hits,
        "accepted_true_positives": accepted_true,
        "accepted_false_positives": accepted_false,
        "expectation_failures": expectation_failures,
        "passed": passed,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "results": results[: max(top_k, 10)],
    }


def _external_results(query: str, raw_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = _dedupe_recorded_external_results(raw_results)
    ranked = sorted(enumerate(rows), key=lambda row: (-external_result_score(query, row[1]), row[0]))
    results: list[dict[str, Any]] = []
    for _, row in ranked:
        score = external_result_score(query, row)
        results.append(
            {
                **_result_summary(row),
                "score": round(score, 1),
                "reason": "external_relevance_score",
                "accepted": False,
                "evidence": {},
            }
        )
    return results


def _dedupe_recorded_external_results(
    raw_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Mirror the registry's stable URL/title dedupe without importing an outer layer."""
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for raw_result in raw_results:
        result = dict(raw_result)
        url = str(result.get("url") or "").strip().rstrip("/").casefold()
        key = url or f"{result.get('source')}:{result.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        results.append(result)
    return results


def _scanner_results(
    items: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    rows = [dict(item) for item in items]
    index = _CatalogMatchIndex.build(rows)
    state, selected_identity, classified_candidates = ManagedLibraryService._classification(None, candidate, index)
    grouped: dict[str, tuple[dict[str, Any], Any]] = {}
    for item in index.candidates(candidate):
        decision = decide_match(item, candidate)
        if not decision.accepted and decision.score < 0.72:
            continue
        identity_key = work_identity_key(work_identity(item))
        prior = grouped.get(identity_key)
        if not identity_key or (prior is not None and prior[1].score >= decision.score):
            continue
        grouped[identity_key] = (item, decision)

    ordered_keys: list[str]
    if state == "matched":
        selected_key = work_identity_key(selected_identity)
        ordered_keys = [selected_key] if selected_key else []
    elif state == "review":
        ordered_keys = [str(row.get("key") or "") for row in classified_candidates]
    else:
        ordered_keys = []
    results: list[dict[str, Any]] = []
    for identity_key in ordered_keys:
        grouped_row = grouped.get(identity_key)
        if grouped_row is None:
            continue
        item, decision = grouped_row
        results.append(
            {
                **_result_summary(item),
                "score": round(decision.score * 100, 1),
                "reason": decision.reason,
                "accepted": state == "matched" and identity_key == work_identity_key(selected_identity),
                "evidence": dict(decision.evidence),
            }
        )
    return results, state


def _result_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    search = row.get("_search") if isinstance(row.get("_search"), Mapping) else {}
    match = row.get("_match") if isinstance(row.get("_match"), Mapping) else {}
    evidence = search.get("evidence") if isinstance(search.get("evidence"), Mapping) else match.get("evidence", {})
    return {
        "key": _result_key(row),
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or ""),
        "year": str(row.get("year") or ""),
        "kind": str(row.get("kind") or ""),
        "source": str(row.get("source") or ""),
        "url": str(row.get("url") or ""),
        "score": round(float(search.get("score") or match.get("score") or 0), 1),
        "matched_field": str(search.get("matched_field") or ""),
        "matched_value": str(search.get("matched_value") or ""),
        "reason": str(search.get("reason") or match.get("reason") or ""),
        "accepted": bool(search.get("accepted") or match.get("accepted")),
        "evidence": dict(evidence) if isinstance(evidence, Mapping) else {},
    }


def _result_key(row: Mapping[str, Any]) -> str:
    item_id = str(row.get("id") or "").strip()
    if item_id:
        return item_id
    for field in ("url", "wikipedia_url", "imdb_url", "filmaffinity_url"):
        url = canonical_url(str(row.get(field) or ""))
        if url:
            return url
    return ":".join(
        value
        for value in (
            str(row.get("source") or "unknown").casefold(),
            str(row.get("title") or "").casefold(),
            str(row.get("year") or ""),
        )
        if value
    )


def _expectation_failures(
    case: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    classification: str,
) -> list[str]:
    by_key = {str(row.get("key") or ""): row for row in results}
    failures: list[str] = []
    expected_classification = str(case.get("expected_classification") or "")
    if expected_classification and classification != expected_classification:
        failures.append(f"classification expected {expected_classification}, got {classification or 'none'}")
    for key, expected in dict(case.get("expected_acceptance") or {}).items():
        row = by_key.get(str(key))
        actual = bool(row and row.get("accepted"))
        if actual != bool(expected):
            failures.append(f"{key} accepted expected {bool(expected)}, got {actual}")
    for key, reasons in dict(case.get("required_reasons") or {}).items():
        allowed = [str(reason) for reason in (reasons if isinstance(reasons, list) else [reasons])]
        actual = str((by_key.get(str(key)) or {}).get("reason") or "")
        if actual not in allowed:
            failures.append(f"{key} reason expected one of {allowed}, got {actual or 'none'}")
    return failures


def _aggregate_metrics(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    contexts: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in cases:
        contexts[str(case["context"])].append(case)
    overall = _metric_summary(cases)
    overall["by_context"] = {name: _metric_summary(rows) for name, rows in sorted(contexts.items())}
    return overall


def _metric_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(cases)
    metrics = [case["metrics"] for case in cases]
    accepted_true = sum(int(row["accepted_true_positives"]) for row in metrics)
    accepted_false = sum(int(row["accepted_false_positives"]) for row in metrics)
    accepted_total = accepted_true + accepted_false
    return {
        "case_count": count,
        "passed_cases": sum(1 for case in cases if case.get("passed")),
        "precision_at_5": round(sum(float(row["precision_at_k"]) for row in metrics) / count, 4) if count else 0.0,
        "mrr": round(sum(float(row["reciprocal_rank"]) for row in metrics) / count, 4) if count else 0.0,
        "recall_at_5": round(sum(float(row["recall_at_k"]) for row in metrics) / count, 4) if count else 0.0,
        "forbidden_hits": sum(int(row["forbidden_hits"]) for row in metrics),
        "auto_match_true_positives": accepted_true,
        "auto_match_false_positives": accepted_false,
        "auto_match_precision": round(accepted_true / accepted_total, 4) if accepted_total else 1.0,
        "expectation_failures": sum(int(row["expectation_failures"]) for row in metrics),
    }


def _evaluate_gate(metrics: Mapping[str, Any], thresholds: Mapping[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    minimums = {"precision_at_5", "mrr", "recall_at_5", "auto_match_precision"}
    maximums = {"forbidden_hits", "auto_match_false_positives", "expectation_failures"}
    for metric, target in thresholds.items():
        if metric not in minimums | maximums:
            raise SearchCorpusError(f"Unsupported Search Lab threshold: {metric}")
        actual = metrics.get(metric)
        passed = float(actual) >= float(target) if metric in minimums else float(actual) <= float(target)
        checks.append({"metric": metric, "actual": actual, "target": target, "passed": passed})
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(row, str) or not row.strip() for row in value):
        raise SearchCorpusError(f"{field} must be an array of non-empty strings")
    return [row.strip() for row in value]


__all__ = [
    "CORPUS_SCHEMA_VERSION",
    "SearchCorpusError",
    "evaluate_search_corpus",
    "inspect_catalog_search",
    "validate_search_corpus",
]
