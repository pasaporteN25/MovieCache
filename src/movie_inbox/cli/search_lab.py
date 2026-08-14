"""Run the read-only Search Lab baseline and inspect catalog exports."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from movie_inbox.application.search_evaluation import (
    SearchCorpusError,
    evaluate_search_corpus,
    inspect_catalog_search,
)
from movie_inbox.infrastructure.schema import CatalogSchemaError, extract_catalog_items
from movie_inbox.search_lab import load_builtin_corpus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the current search behavior without writing to a catalog or using the network."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run the packaged golden corpus or a custom corpus.")
    run_parser.add_argument("--corpus", type=Path, help="Optional Search Lab corpus JSON.")
    add_report_arguments(run_parser)
    run_parser.add_argument(
        "--enforce",
        action="store_true",
        help="Return exit code 1 when the quality gate fails. Baseline runs otherwise return 0.",
    )

    inspect_parser = commands.add_parser(
        "inspect",
        help="Rank one query against a read-only JSON catalog export.",
    )
    inspect_parser.add_argument("catalog", type=Path, help="JSON catalog export to inspect read-only.")
    inspect_parser.add_argument("query", help="Title or identity to inspect.")
    inspect_parser.add_argument(
        "--mode",
        choices=("catalog", "identity", "scanner"),
        default="catalog",
        help="Production context to inspect.",
    )
    inspect_parser.add_argument("--year", default="", help="Candidate year for identity or scanner mode.")
    inspect_parser.add_argument("--kind", default="pelicula", help="Candidate kind for identity or scanner mode.")
    inspect_parser.add_argument("--limit", type=int, default=20, help="Maximum results to include.")
    add_report_arguments(inspect_parser)

    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            corpus = read_json_object(args.corpus) if args.corpus else load_builtin_corpus()
            report = evaluate_search_corpus(corpus)
            protected = [args.corpus] if args.corpus else []
            write_reports(report, args.json_report, args.html_report, protected)
            print_corpus_summary(report)
            return 1 if args.enforce and not report["gate"]["passed"] else 0

        if args.limit < 1:
            parser.error("--limit must be greater than zero")
        items = read_catalog_export(args.catalog)
        report = inspect_catalog_search(
            items,
            args.query,
            mode=args.mode,
            year=args.year,
            kind=args.kind,
            limit=args.limit,
        )
        write_reports(report, args.json_report, args.html_report, [args.catalog])
        print_inspection_summary(report)
        return 0
    except (OSError, json.JSONDecodeError, CatalogSchemaError, SearchCorpusError, ValueError) as error:
        print(f"Search Lab error: {error}", file=sys.stderr)
        return 2


def add_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", dest="json_report", type=Path, help="Write the report as JSON.")
    parser.add_argument("--html", dest="html_report", type=Path, help="Write a standalone HTML report.")


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SearchCorpusError("Search Lab corpus root must be an object")
    return payload


def read_catalog_export(path: Path) -> list[dict[str, Any]]:
    if path.suffix.casefold() != ".json":
        raise SearchCorpusError("Inspection accepts a JSON export, never a live SQLite database")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return extract_catalog_items(raw)


def write_reports(
    report: Mapping[str, Any],
    json_path: Path | None,
    html_path: Path | None,
    protected_paths: Sequence[Path | None],
) -> None:
    protected = {path.resolve() for path in protected_paths if path is not None}
    for target in (json_path, html_path):
        if target is not None and target.resolve() in protected:
            raise SearchCorpusError(f"Refusing to overwrite read-only input: {target}")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if html_path is not None:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html_report(report), encoding="utf-8")


def print_corpus_summary(report: Mapping[str, Any]) -> None:
    corpus = report["corpus"]
    metrics = report["metrics"]
    gate = report["gate"]
    print("Search Lab production baseline")
    print(f"- Corpus: {corpus['name']}")
    print(f"- Cases: {metrics['passed_cases']}/{metrics['case_count']} strict cases passed")
    print(f"- Precision@5: {float(metrics['precision_at_5']):.3f}")
    print(f"- MRR: {float(metrics['mrr']):.3f}")
    print(f"- Recall@5: {float(metrics['recall_at_5']):.3f}")
    print(f"- Forbidden hits: {metrics['forbidden_hits']}")
    print(f"- Auto-match precision: {float(metrics['auto_match_precision']):.3f}")
    print(f"- Quality gate: {'PASS' if gate['passed'] else 'FAIL (baseline recorded)'}")


def print_inspection_summary(report: Mapping[str, Any]) -> None:
    print("Search Lab read-only inspection")
    print(f"- Query: {report['query']}")
    print(f"- Mode: {report['mode']}")
    if report.get("classification"):
        print(f"- Scanner classification: {report['classification']}")
    print(f"- Catalog items: {report['catalog_item_count']}")
    print(f"- Results: {report['result_count']}")
    for index, row in enumerate(report["results"][:10], 1):
        title = row.get("title") or row.get("key") or "Untitled"
        year = f" ({row.get('year')})" if row.get("year") else ""
        accepted = " accepted" if row.get("accepted") else ""
        print(f"  {index:>2}. {title}{year} score={row.get('score', 0)} {row.get('reason', '')}{accepted}".rstrip())


def render_html_report(report: Mapping[str, Any]) -> str:
    if report.get("report_type") == "search_inspection":
        title = f"Search Lab: {report.get('query') or 'inspection'}"
        summary = _inspection_summary_html(report)
        cases = _results_table(report.get("results") or [])
    else:
        corpus = report.get("corpus") if isinstance(report.get("corpus"), Mapping) else {}
        title = f"Search Lab: {corpus.get('name') or 'corpus'}"
        summary = _corpus_summary_html(report)
        cases = "".join(_case_html(case) for case in report.get("cases") or [])
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#090a18; --panel:#12152a; --line:#343960; --text:#f4f1ff; --muted:#adb3cf; --cyan:#35d7e8; --pink:#ff45bd; --good:#67dfa5; --bad:#ff7d96; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,sans-serif; }}
    main {{ width:min(1180px,calc(100% - 32px)); margin:32px auto 64px; }} h1 {{ margin:0 0 8px; font-size:clamp(28px,5vw,52px); letter-spacing:0; }}
    h2 {{ font-size:19px; margin:0; }} p {{ color:var(--muted); }} .eyebrow {{ color:var(--cyan); font-size:12px; font-weight:800; text-transform:uppercase; }}
    .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:1px; margin:24px 0; border:1px solid var(--line); background:var(--line); }}
    .metric {{ min-height:96px; padding:16px; background:var(--panel); }} .metric strong {{ display:block; font-size:25px; }} .metric span {{ color:var(--muted); }}
    .case {{ margin:14px 0; border:1px solid var(--line); background:var(--panel); }} .case summary {{ cursor:pointer; padding:14px 16px; font-weight:750; }} .case-body {{ padding:0 16px 16px; }}
    .pass {{ color:var(--good); }} .fail {{ color:var(--bad); }} table {{ width:100%; border-collapse:collapse; margin-top:12px; }} th,td {{ padding:9px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }} code {{ color:var(--cyan); overflow-wrap:anywhere; }}
    .pill {{ display:inline-block; border:1px solid var(--line); padding:2px 7px; margin:2px; font-size:12px; }}
    @media(max-width:700px) {{ main {{ width:min(100% - 20px,1180px); margin-top:18px; }} .table-wrap {{ overflow-x:auto; }} th,td {{ min-width:100px; }} }}
  </style>
</head>
<body><main><div class="eyebrow">Movie Inbox / lectura solamente</div><h1>{_escape(title)}</h1><p>Ranking productivo actual, ejecutado sin red y sin escribir en el catálogo.</p>{summary}{cases}</main></body>
</html>
"""


def _corpus_summary_html(report: Mapping[str, Any]) -> str:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), Mapping) else {}
    gate = report.get("gate") if isinstance(report.get("gate"), Mapping) else {}
    values = (
        ("Casos estrictos", f"{metrics.get('passed_cases', 0)}/{metrics.get('case_count', 0)}"),
        ("Precision@5", _number(metrics.get("precision_at_5"))),
        ("MRR", _number(metrics.get("mrr"))),
        ("Recall@5", _number(metrics.get("recall_at_5"))),
        ("Prohibidos", str(metrics.get("forbidden_hits", 0))),
        ("Auto-match", _number(metrics.get("auto_match_precision"))),
        ("Gate", "PASS" if gate.get("passed") else "FAIL baseline"),
    )
    cards = "".join(f'<div class="metric"><strong>{_escape(value)}</strong><span>{_escape(label)}</span></div>' for label, value in values)
    checks = "".join(
        f'<span class="pill {"pass" if row.get("passed") else "fail"}">{_escape(row.get("metric"))}: {_escape(row.get("actual"))} / {_escape(row.get("target"))}</span>'
        for row in gate.get("checks") or []
    )
    return f'<section class="metrics">{cards}</section><p>{checks}</p>'


def _inspection_summary_html(report: Mapping[str, Any]) -> str:
    values = (
        ("Modo", report.get("mode", "")),
        ("Resultados", report.get("result_count", 0)),
        ("Catálogo", report.get("catalog_item_count", 0)),
        ("Clasificación", report.get("classification") or "n/a"),
        ("Duración", f"{report.get('duration_ms', 0)} ms"),
    )
    cards = "".join(f'<div class="metric"><strong>{_escape(value)}</strong><span>{_escape(label)}</span></div>' for label, value in values)
    return f'<section class="metrics">{cards}</section>'


def _case_html(case: Mapping[str, Any]) -> str:
    state = "pass" if case.get("passed") else "fail"
    metrics = case.get("metrics") if isinstance(case.get("metrics"), Mapping) else {}
    failures = "".join(f"<li>{_escape(value)}</li>" for value in case.get("expectation_failures") or [])
    failure_block = f"<ul>{failures}</ul>" if failures else ""
    return (
        f'<details class="case"><summary><span class="{state}">{"PASS" if case.get("passed") else "FAIL"}</span> '
        f'{_escape(case.get("label"))} <code>{_escape(case.get("context"))}</code></summary><div class="case-body">'
        f'<p>Consulta: <code>{_escape(case.get("query"))}</code> · P@K {_number(metrics.get("precision_at_k"))} · '
        f'R@K {_number(metrics.get("recall_at_k"))} · RR {_number(metrics.get("reciprocal_rank"))}</p>'
        f'{failure_block}{_results_table(case.get("results") or [])}</div></details>'
    )


def _results_table(results: Sequence[Mapping[str, Any]]) -> str:
    if not results:
        return "<p>Sin resultados.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{index}</td><td>{_escape(row.get('title') or row.get('key'))}</td>"
        f"<td>{_escape(row.get('year'))}</td><td>{_escape(row.get('score'))}</td>"
        f"<td>{_escape(row.get('matched_field'))}</td><td>{_escape(row.get('reason'))}</td>"
        f"<td>{'sí' if row.get('accepted') else 'no'}</td><td><code>{_escape(row.get('key'))}</code></td>"
        "</tr>"
        for index, row in enumerate(results, 1)
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>#</th><th>Título</th><th>Año</th><th>Score</th>'
        f'<th>Campo</th><th>Razón</th><th>Aceptada</th><th>Clave</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _number(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value or 0)


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
