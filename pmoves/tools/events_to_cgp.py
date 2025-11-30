#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, sys
from typing import Any, Dict

here = os.path.dirname(os.path.abspath(__file__))
repo = os.path.normpath(os.path.join(here, "..", ".."))
sys.path.insert(0, os.path.join(repo, "pmoves", "services", "common"))

from cgp_mappers import (
    map_health_weekly_summary_to_cgp,
    map_finance_monthly_summary_to_cgp,
)

import requests


TOPIC_TO_MAPPER = {
    "health.weekly.summary.v1": map_health_weekly_summary_to_cgp,
    "finance.monthly.summary.v1": map_finance_monthly_summary_to_cgp,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Map summary events to geometry CGPs and optionally POST to gateway")
    ap.add_argument("--file", required=True, help="Path to event JSON ({topic, payload})")
    ap.add_argument("--topic", help="Topic override; if omitted, read from file.topic")
    ap.add_argument("--gateway", default=os.environ.get("HIRAG_URL", "http://localhost:8086"))
    ap.add_argument("--post", action="store_true", help="POST to /geometry/event after mapping")
    ap.add_argument("--print", action="store_true", help="Print mapped CGP JSON")
    args = ap.parse_args()

    doc = json.loads(open(args.file, "r", encoding="utf-8").read())
    topic = args.topic or doc.get("topic")
    if not topic:
        print("missing topic (pass --topic or include in file)", file=sys.stderr)
        return 2
    mapper = TOPIC_TO_MAPPER.get(topic)
    if not mapper:
        print(f"no mapper for topic: {topic}", file=sys.stderr)
        return 3
    cgp = mapper(doc)

    if args.print or not args.post:
        print(json.dumps(cgp, indent=2))

    if args.post:
        url = f"{args.gateway}/geometry/event"
        envelope = {"type": "geometry.cgp.v1", "data": cgp}
        r = requests.post(url, json=envelope, timeout=20)
        if r.status_code >= 400:
            print(f"POST {url} failed: {r.status_code} {r.text}", file=sys.stderr)
            return 4
        print(json.dumps(r.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

