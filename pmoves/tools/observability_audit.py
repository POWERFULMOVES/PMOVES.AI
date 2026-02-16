#!/usr/bin/env python3
"""Generate an observability mapping audit for PMOVES monitoring."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
PROM_CONFIG = ROOT / "monitoring" / "prometheus" / "prometheus.yml"
DASHBOARD_DIR = ROOT / "monitoring" / "grafana" / "dashboards"
DEFAULT_OUTPUT = ROOT / "docs" / "services" / "monitoring" / "OBSERVABILITY_MAP.md"


@dataclass
class JobConfig:
    name: str
    targets: List[str] = field(default_factory=list)
    metrics_path: str = "/metrics"
    module: str = ""


def _strip_quotes(value: str) -> str:
    raw = value.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    return raw


def parse_prometheus_jobs(path: Path) -> Dict[str, JobConfig]:
    jobs: Dict[str, JobConfig] = {}
    current: JobConfig | None = None
    collecting_targets = False

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m_job = re.match(r"^\s*-\s*job_name:\s*(.+)\s*$", line)
        if m_job:
            name = _strip_quotes(m_job.group(1))
            current = JobConfig(name=name)
            jobs[name] = current
            collecting_targets = False
            continue

        if current is None:
            continue

        if re.match(r"^\s*-\s*targets:\s*$", line):
            collecting_targets = True
            continue

        m_targets_inline = re.match(r"^\s*-\s*targets:\s*\[(.+)\]\s*$", line)
        if m_targets_inline:
            collecting_targets = False
            entries = [part.strip() for part in m_targets_inline.group(1).split(",")]
            for item in entries:
                target = _strip_quotes(item)
                if target:
                    current.targets.append(target)
            continue

        m_metrics_path = re.match(r"^\s*metrics_path:\s*(.+)\s*$", line)
        if m_metrics_path:
            current.metrics_path = _strip_quotes(m_metrics_path.group(1))
            continue

        m_module = re.match(r"^\s*module:\s*\[(.+)\]\s*$", line)
        if m_module:
            current.module = _strip_quotes(m_module.group(1))
            continue

        if collecting_targets:
            m_target = re.match(r"^\s*-\s+(.+)\s*$", line)
            if m_target:
                target = _strip_quotes(m_target.group(1).split("#", 1)[0].strip())
                if target:
                    current.targets.append(target)
                continue
            if re.match(r"^\s*[a-zA-Z_]+\s*:", line):
                collecting_targets = False

    return jobs


def parse_dashboard_job_usage(path: Path) -> Dict[str, Set[str]]:
    usage: Dict[str, Set[str]] = {}
    dashboard_files = sorted(path.glob("*.json"))
    for dashboard_file in dashboard_files:
        text = dashboard_file.read_text(encoding="utf-8", errors="ignore")
        matches = re.findall(r'job\s*=~?\s*"([^"]+)"', text)
        for token in matches:
            parts = [part.strip() for part in token.split("|")]
            for part in parts:
                if not part or any(ch in part for ch in ("$", "^", ".", "*", "+", "(", ")")):
                    continue
                usage.setdefault(part, set()).add(dashboard_file.name)

    # Filename heuristic coverage for dashboards that do not include explicit job selectors.
    # Example: archon.json -> job `archon`.
    known_files = [f.name for f in dashboard_files]
    normalized_files = {
        name: re.sub(r"[^a-z0-9]", "", name.replace(".json", "").lower()) for name in known_files
    }
    for dashboard_name, normalized in normalized_files.items():
        if not normalized:
            continue
        usage.setdefault(f"__dashboard__:{normalized}", set()).add(dashboard_name)
    return usage


def fetch_live_target_health(prom_url: str) -> Dict[str, Tuple[int, int]]:
    url = f"{prom_url.rstrip('/')}/api/v1/targets"
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return {}

    targets = payload.get("data", {}).get("activeTargets", [])
    summary: Dict[str, Tuple[int, int]] = {}
    counts: Dict[str, List[int]] = {}
    for item in targets:
        labels = item.get("labels", {})
        job = labels.get("job")
        if not job:
            continue
        total, up = counts.get(job, [0, 0])
        total += 1
        if item.get("health") == "up":
            up += 1
        counts[job] = [total, up]

    for job, (total, up) in counts.items():
        summary[job] = (up, total)
    return summary


def build_markdown(
    jobs: Dict[str, JobConfig],
    dashboard_usage: Dict[str, Set[str]],
    live_health: Dict[str, Tuple[int, int]],
) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []
    lines.append("# Observability Map")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("## Scrape Jobs")
    lines.append("| Job | Targets (config) | Module/Path | Live Health (up/total) |")
    lines.append("| --- | --- | --- | --- |")

    for job_name in sorted(jobs):
        job = jobs[job_name]
        target_preview = ", ".join(job.targets[:3]) if job.targets else "-"
        if len(job.targets) > 3:
            target_preview += f" (+{len(job.targets)-3} more)"
        mode = job.module or job.metrics_path
        up_total = live_health.get(job_name)
        health = f"{up_total[0]}/{up_total[1]}" if up_total else "n/a"
        lines.append(f"| `{job_name}` | {target_preview} | `{mode}` | {health} |")

    lines.append("")
    lines.append("## Dashboard Coverage")
    lines.append("| Job | Dashboards |")
    lines.append("| --- | --- |")
    known_jobs = set(jobs.keys())
    dashboard_jobs = set(dashboard_usage.keys())
    normalized_dashboard_map: Dict[str, Set[str]] = {}
    for key, dashboards in dashboard_usage.items():
        if not key.startswith("__dashboard__:"):
            continue
        normalized_dashboard_map[key.split(":", 1)[1]] = dashboards

    def heuristic_dashboards_for_job(job_name: str) -> Set[str]:
        normalized_job = re.sub(r"[^a-z0-9]", "", job_name.lower())
        hits: Set[str] = set()
        for normalized_name, dashboards in normalized_dashboard_map.items():
            if normalized_job in normalized_name or normalized_name in normalized_job:
                hits.update(dashboards)
        return hits

    for job_name in sorted(known_jobs):
        explicit = dashboard_usage.get(job_name, set())
        heuristic = heuristic_dashboards_for_job(job_name)
        dashboards = explicit or heuristic
        dashboard_text = ", ".join(f"`{d}`" for d in sorted(dashboards))
        if explicit:
            source = "explicit"
        elif heuristic:
            source = "heuristic"
        else:
            source = ""
        if source:
            dashboard_text = f"{dashboard_text} ({source})"
        lines.append(f"| `{job_name}` | {dashboard_text if dashboards else '_none_'} |")

    missing_in_dashboards = sorted(
        job for job in known_jobs if not dashboard_usage.get(job) and not heuristic_dashboards_for_job(job)
    )
    unknown_dashboard_jobs = sorted(
        job for job in dashboard_jobs if job not in known_jobs and not job.startswith("__dashboard__:")
    )

    lines.append("")
    lines.append("## Gaps")
    if missing_in_dashboards:
        lines.append("- Scrape jobs with no explicit dashboard job selector:")
        for job in missing_in_dashboards:
            lines.append(f"  - `{job}`")
    else:
        lines.append("- All scrape jobs are referenced by at least one dashboard query.")

    if unknown_dashboard_jobs:
        lines.append("- Dashboard job selectors not found in current scrape config:")
        for job in unknown_dashboard_jobs:
            refs = ", ".join(sorted(dashboard_usage.get(job, set())))
            lines.append(f"  - `{job}` (from {refs})")
    else:
        lines.append("- No orphaned dashboard job selectors detected.")

    lines.append("")
    lines.append("## Notes")
    lines.append("- `monitoring-smoke` validates monitoring stack readiness + blackbox samples.")
    lines.append("- `monitoring-smoke-prod` adds required-job assertions for production audits.")
    lines.append("- Run `make -C pmoves observability-audit` after changing Prometheus jobs or Grafana dashboards.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prom-config", type=Path, default=PROM_CONFIG)
    parser.add_argument("--dashboards-dir", type=Path, default=DASHBOARD_DIR)
    parser.add_argument("--prom-url", default="")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    jobs = parse_prometheus_jobs(args.prom_config.expanduser().resolve())
    usage = parse_dashboard_job_usage(args.dashboards_dir.expanduser().resolve())
    live = fetch_live_target_health(args.prom_url) if args.prom_url else {}
    report = build_markdown(jobs, usage, live)

    out = args.output.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report + "\n", encoding="utf-8")
    print(f"Wrote observability report: {out}")
    print(f"Jobs parsed: {len(jobs)}  Dashboard job selectors: {len(usage)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
