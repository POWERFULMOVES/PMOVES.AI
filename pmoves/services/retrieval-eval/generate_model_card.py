from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from eval_utils import ensure_directory, utc_now


@dataclass
class EvaluationRun:
    name: str
    metrics: Dict[str, Any]
    count: int | None
    k: int | None
    suites: List[Dict[str, Any]]
    source_file: Path
    generated_at: str | None
    endpoint: str | None
    extra: Dict[str, Any]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "model"


def load_results(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def extract_runs(results: Dict[str, Any], source: Path) -> List[EvaluationRun]:
    runs: List[EvaluationRun] = []
    overall = results.get("overall")
    if isinstance(overall, dict) and {"mrr", "ndcg"} & set(overall.keys()):
        metrics = {k: overall[k] for k in overall if k not in {"count", "k"}}
        run = EvaluationRun(
            name=results.get("run_label") or source.stem,
            metrics=metrics,
            count=overall.get("count"),
            k=overall.get("k") or (results.get("parameters") or {}).get("k"),
            suites=(results.get("suites") or {}).get("all", []),
            source_file=source,
            generated_at=results.get("generated_at"),
            endpoint=results.get("endpoint"),
            extra={"type": "overall"},
        )
        runs.append(run)

    for setting in results.get("settings", []):
        overall_setting = setting.get("overall") or {}
        metrics = overall_setting.get("metrics") or {}
        run = EvaluationRun(
            name=setting.get("label") or f"{source.stem}-{'rerank' if setting.get('use_rerank') else 'baseline'}",
            metrics=metrics,
            count=overall_setting.get("count"),
            k=(results.get("parameters") or {}).get("k"),
            suites=(setting.get("suites") or {}).get("all", []),
            source_file=source,
            generated_at=results.get("generated_at"),
            endpoint=results.get("endpoint"),
            extra={
                "type": "setting",
                "use_rerank": setting.get("use_rerank"),
            },
        )
        runs.append(run)
    return runs


def format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def suites_section(run: EvaluationRun) -> List[str]:
    if not run.suites:
        return []
    lines = [f"### Suite Results — {run.name}"]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for suite in run.suites:
        grouped.setdefault(suite.get("type", "custom"), []).append(suite)
    for suite_type, items in sorted(grouped.items()):
        lines.append(f"#### {suite_type.title()} suites")
        for item in items:
            metrics_str = ", ".join(
                f"{metric}={format_metric(value)}" for metric, value in sorted(item.get("metrics", {}).items())
            ) or "no metrics"
            status = item.get("passed")
            if status is True:
                status_label = "PASS"
            elif status is False:
                status_label = "FAIL"
            else:
                status_label = "N/A"
            description = item.get("description")
            lines.append(
                f"- **{item.get('name', 'suite')}** ({item.get('query_count', 0)} queries) — {metrics_str}. Status: {status_label}."
            )
            if description:
                lines.append(f"  - _{description}_")
            evaluations = item.get("threshold_evaluations") or {}
            for metric, details in sorted(evaluations.items()):
                qualifiers = []
                if details.get("min") is not None:
                    qualifiers.append(f"min={details['min']}")
                if details.get("max") is not None:
                    qualifiers.append(f"max={details['max']}")
                qualifier_str = f" ({', '.join(qualifiers)})" if qualifiers else ""
                lines.append(
                    f"  - {metric}: {format_metric(details.get('value'))} → {'PASS' if details.get('passed') else 'FAIL'}{qualifier_str}"
                )
    return lines


def markdown_to_html(markdown_text: str) -> str:
    try:
        import markdown

        return markdown.markdown(markdown_text, extensions=["tables"])  # type: ignore
    except Exception:  # pragma: no cover - graceful fallback when markdown lib unavailable
        import html

        escaped = html.escape(markdown_text)
        return f"<html><body><pre>{escaped}</pre></body></html>"


def build_markdown(
    *,
    model_name: str,
    generated_at: str,
    results_files: List[Path],
    datasets: List[Dict[str, Any]],
    runs: List[EvaluationRun],
    suite_configs: List[Dict[str, Any]],
    comparisons: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append(f"# Retrieval Evaluation Model Card — {model_name}")
    lines.append("")
    lines.append(f"Generated {generated_at} (UTC)")
    lines.append("")
    lines.append("## Source Results")
    for path in results_files:
        lines.append(f"- {path}")
    lines.append("")

    if datasets:
        lines.append("## Dataset Provenance")
        for dataset in datasets:
            path = dataset.get("path")
            sha = dataset.get("sha256")
            count = dataset.get("total_queries")
            lines.append(f"- `{path}` — {count} queries (sha256: `{sha}`)")
        lines.append("")

    if suite_configs:
        lines.append("## Suite Configuration Files")
        for suite in suite_configs:
            lines.append(f"- `{suite.get('path')}` (sha256: `{suite.get('sha256')}`)")
        lines.append("")

    if runs:
        all_metrics = sorted({metric for run in runs for metric in run.metrics.keys()})
        lines.append("## Metric Summary")
        header_cells = ["Run", "Queries", "Top-K"] + all_metrics
        header = "| " + " | ".join(header_cells) + " |"
        separator = "| " + " | ".join(["---"] * len(header_cells)) + " |"
        lines.append(header)
        lines.append(separator)
        for run in runs:
            row: List[str] = [
                run.name,
                str(run.count if run.count is not None else ""),
                str(run.k if run.k is not None else ""),
            ]
            row.extend(format_metric(run.metrics.get(metric, "")) for metric in all_metrics)
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    for run in runs:
        suite_lines = suites_section(run)
        if suite_lines:
            lines.extend(suite_lines)
            lines.append("")

    if comparisons:
        lines.append("## Rerank Comparisons")
        for comparison in comparisons:
            label = comparison.get("label")
            lines.append(f"- **{label}**")
            for metric, payload in sorted(comparison.get("comparison", {}).items()):
                baseline = format_metric(payload.get("baseline"))
                rerank = format_metric(payload.get("rerank"))
                delta = format_metric(payload.get("delta"))
                lines.append(f"  - {metric}: {baseline} → {rerank} (Δ {delta})")
        lines.append("")

    lines.append("## Operational Context")
    for run in runs:
        endpoint = run.endpoint or "unknown"
        timestamp = run.generated_at or "unknown"
        lines.append(f"- {run.name}: endpoint `{endpoint}` (run at {timestamp})")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate retrieval evaluation model card artifacts.")
    parser.add_argument("--results", nargs="+", required=True, help="Paths to JSON evaluation outputs.")
    parser.add_argument("--model-name", required=True, help="Display name for the evaluated model/system.")
    parser.add_argument(
        "--output-dir",
        default="pmoves/docs/evals",
        help="Root directory (relative to repo) where artifacts are stored.",
    )
    parser.add_argument("--slug", help="Optional slug override for output folder naming.")
    parser.add_argument(
        "--notes",
        help="Optional JSON file with additional notes to merge into the summary.json payload.",
    )
    args = parser.parse_args()

    result_paths = [Path(p) for p in args.results]
    runs: List[EvaluationRun] = []
    datasets_map: Dict[str, Dict[str, Any]] = {}
    suite_configs_map: Dict[str, Dict[str, Any]] = {}
    comparisons: List[Dict[str, Any]] = []

    for path in result_paths:
        data = load_results(path)
        datasets = data.get("dataset")
        if isinstance(datasets, dict):
            datasets_map[datasets.get("sha256") or str(path)] = datasets
        suite_config = data.get("suite_config")
        if isinstance(suite_config, dict):
            suite_configs_map[suite_config.get("sha256") or str(path)] = suite_config
        if "comparison" in data:
            comparisons.append({
                "label": data.get("run_label") or path.stem,
                "comparison": data["comparison"],
            })
        runs.extend(extract_runs(data, path))

    runs.sort(key=lambda r: (r.extra.get("type"), r.name))

    generated_at = utc_now()
    slug = args.slug or slugify(args.model_name)
    output_root = Path(args.output_dir) / slug / generated_at.replace(":", "")
    ensure_directory(output_root)

    markdown = build_markdown(
        model_name=args.model_name,
        generated_at=generated_at,
        results_files=result_paths,
        datasets=list(datasets_map.values()),
        runs=runs,
        suite_configs=list(suite_configs_map.values()),
        comparisons=comparisons,
    )
    html = markdown_to_html(markdown)

    markdown_path = output_root / "model_card.md"
    html_path = output_root / "model_card.html"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    summary_payload = {
        "model_name": args.model_name,
        "generated_at": generated_at,
        "results_files": [str(path) for path in result_paths],
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "count": run.count,
                "k": run.k,
                "suites": run.suites,
                "source_file": str(run.source_file),
                "generated_at": run.generated_at,
                "endpoint": run.endpoint,
                "extra": run.extra,
            }
            for run in runs
        ],
        "datasets": list(datasets_map.values()),
        "suite_configs": list(suite_configs_map.values()),
        "comparisons": comparisons,
    }

    if args.notes:
        notes_path = Path(args.notes)
        if notes_path.exists():
            with notes_path.open("r", encoding="utf-8") as fh:
                summary_payload["notes"] = json.load(fh)

    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    print(f"Model card written to {markdown_path}")
    print(f"HTML artifact written to {html_path}")
    print(f"Summary JSON written to {summary_path}")


if __name__ == "__main__":
    main()
