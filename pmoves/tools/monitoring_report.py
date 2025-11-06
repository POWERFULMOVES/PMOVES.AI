#!/usr/bin/env python3
"""
Quick Prometheus/Grafana status reporter.

Usage:
  python pmoves/tools/monitoring_report.py [--prom http://localhost:9090]

Prints:
  - Prometheus active targets
  - Blackbox probe failures (last 5m)
  - Top 5 containers by CPU (if cAdvisor is scraped)
"""
import argparse
import json
import sys
import urllib.request


def q(prom, query):
    with urllib.request.urlopen(f"{prom}/api/v1/query?query=" + urllib.parse.quote(query)) as r:
        data = json.load(r)
        return data.get("data", {}).get("result", [])


def get_targets(prom):
    with urllib.request.urlopen(f"{prom}/api/v1/targets") as r:
        data = json.load(r)
        return data.get("data", {}).get("activeTargets", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom", default="http://localhost:9090")
    args = ap.parse_args()

    prom = args.prom.rstrip("/")
    print(f"Prometheus: {prom}")

    # Targets
    print("\nActive targets:")
    for t in get_targets(prom):
        print(f"  - {t['labels'].get('job')} {t['labels'].get('instance')}: {t['health']}")

    # Blackbox failures
    print("\nRecent blackbox probe failures (5m):")
    failures = q(prom, 'max_over_time((probe_success==0)[5m:])')
    if not failures:
        print("  (none)")
    else:
        for s in failures:
            inst = s["metric"].get("instance")
            print(f"  - {inst}")

    # Container CPU
    print("\nTop containers by CPU (1m rate):")
    cpu = q(prom, 'topk(5, sum by (name) (rate(container_cpu_usage_seconds_total{image!=""}[1m])))')
    if not cpu:
        print("  (no cadvisor samples)")
    else:
        for s in cpu:
            name = s["metric"].get("name")
            val = float(s["value"][1])
            print(f"  - {name}: {val:.4f} cores")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

