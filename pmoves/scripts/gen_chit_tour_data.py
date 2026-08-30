#!/usr/bin/env python3
"""Generate the CHIT tour's LIVE data tables from the agent registry (SSOT).

Emits ``website/chit-tour/data.generated.js`` with AGENT_ROSTER + NATS_SUBJECTS
+ LIVE_META, derived from ``pmoves/config/agent_registry.yaml`` — so the tour
shows the *real, current* roster and subject set instead of a hand-authored
subset that drifts. Regenerate at deploy (make chit-tour-data). Static output,
zero per-visitor cost (public "pre-canned" posture, voice design §1a).

Deterministic except the date stamp. Run: python pmoves/scripts/gen_chit_tour_data.py
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / "pmoves" / "config" / "agent_registry.yaml"
OUT = ROOT / "website" / "chit-tour" / "data.generated.js"

# primary_type → tier / element table lives in the registry `types:` block;
# fall back to the canonical order if a type is missing.
_FALLBACK_TIER = {"data": 1, "api": 2, "llm": 3, "worker": 4, "media": 5, "agent": 6, "ui": 7}


def _title(s: str | None) -> str:
    return (s or "").replace("_", " ").title() if s else ""


def build() -> dict:
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    agents: dict = reg.get("agents", {}) or {}
    types: dict = reg.get("types", {}) or {}

    def tier_for(ptype: str | None) -> int:
        if ptype and isinstance(types.get(ptype), dict) and "tier" in types[ptype]:
            return int(types[ptype]["tier"])
        return _FALLBACK_TIER.get(ptype or "", 0)

    # --- AGENT_ROSTER (all registered agents) ---
    roster = []
    for aid, a in sorted(agents.items(), key=lambda kv: kv[1].get("name", kv[0]).lower()):
        roster.append({
            "name": a.get("name", aid),
            "cls": _title(a.get("class")) or "Standard",
            "primary": _title(a.get("primary_type")),
            "secondary": _title(a.get("secondary_type")),
            "tier": tier_for(a.get("primary_type")),
            "stage": _title(a.get("evolution_stage")) or "Base",
            "layers": len(a.get("layers") or []),
        })

    # --- NATS_SUBJECTS (union of every agent's publishes/subscribes) ---
    pubs: dict[str, list[str]] = {}
    subs: dict[str, list[str]] = {}
    for a in agents.values():
        name = a.get("name", "?")
        nats = a.get("nats") or {}
        for s in (nats.get("publishes") or []):
            pubs.setdefault(s, []).append(name)
        for s in (nats.get("subscribes") or []):
            subs.setdefault(s, []).append(name)

    def _dir(subject: str) -> str:
        p, s = pubs.get(subject, []), subs.get(subject, [])
        parts = []
        if p:
            parts.append("Pub: " + ", ".join(sorted(set(p))[:3]) + ("…" if len(set(p)) > 3 else ""))
        if s:
            parts.append("Sub: " + ", ".join(sorted(set(s))[:3]) + ("…" if len(set(s)) > 3 else ""))
        return " ▸ ".join(parts) or "—"

    def _purpose(subject: str) -> str:
        # Humanize the versioned namespace: tokenism.cgp.ready.v1 → tokenism · cgp · ready
        segs = [seg for seg in subject.split(".") if not seg.startswith("v") or not seg[1:].isdigit()]
        return " · ".join(segs)

    subjects = sorted(set(pubs) | set(subs))
    nats_subjects = [{"subject": s, "dir": _dir(s), "purpose": _purpose(s)} for s in subjects]

    return {
        "roster": roster,
        "nats_subjects": nats_subjects,
        "meta": {
            "generated_at": datetime.date.today().isoformat(),
            "source": "pmoves/config/agent_registry.yaml",
            "agent_count": len(roster),
            "subject_count": len(nats_subjects),
            "taxonomy_version": reg.get("taxonomy_version", ""),
        },
    }


def render(data: dict) -> str:
    def js(v) -> str:
        return json.dumps(v, ensure_ascii=False, indent=2)

    return (
        "// data.generated.js — LIVE tour data, generated from the agent registry (SSOT).\n"
        "// DO NOT EDIT BY HAND. Regenerate: make -C pmoves chit-tour-data\n"
        f"// source: {data['meta']['source']} · agents: {data['meta']['agent_count']} · "
        f"subjects: {data['meta']['subject_count']} · generated: {data['meta']['generated_at']}\n\n"
        f"const LIVE_META = {js(data['meta'])};\n\n"
        f"const AGENT_ROSTER = {js(data['roster'])};\n\n"
        f"const NATS_SUBJECTS = {js(data['nats_subjects'])};\n"
    )


def main() -> int:
    data = build()
    OUT.write_text(render(data), encoding="utf-8")
    m = data["meta"]
    print(f"wrote {OUT.relative_to(ROOT)} — {m['agent_count']} agents, {m['subject_count']} subjects (from {m['source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
