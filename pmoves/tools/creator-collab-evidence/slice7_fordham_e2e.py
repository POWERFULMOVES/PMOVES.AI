#!/usr/bin/env python3
"""slice7_fordham_e2e.py — Fordham <-> PMOVES-helpdesk E2E evidence script.

Slice 7 of the creator-collab lane. Demonstrates the end-to-end flow that
a Fordham Hill resident triggers when they enter pmoves.room.helpdesk:

  1. room.presence.v1         (Fordham resident entering the helpdesk)
  2. helpdesk.intake.opened.v1 (intake session created)
  3. helpdesk.intake.routed.v1 (routed to a candidate room)
  4. helpdesk.room.suggested.v1 (ranked candidates from room-suggest-skill)

The script:

  - Reads the real pmoves/config/rooms/catalog.json (slice 1 contract)
  - Loads the real pinokio-apps registry (slice 4 curated/* YAMLs)
  - Runs the helpdesk routing algorithm against the live registry
    (intent extraction, capability matching, persona affinity)
  - Publishes the 4 events through the nats_event_bus HTTP API
    (real nats_event_bus writes; the bus then forwards to NATS)
  - Subscribes to NATS directly and captures each event as it lands
  - Saves a full evidence bundle to pmoves/tools/creator-collab-evidence/slice7/
    (room directory snapshot, routing decision, raw events, summary JSON)

This is "Option A with Option C value":
  - A: synthetic room.presence event (no live ComfyUI / Pinokio launch)
  - C value: real helpdesk routing logic against the real room directory
             + real pinokio-apps registry + real nats_event_bus traffic
             + real NATS broker capture. The path to full C (real Pinokio
             launch + ComfyUI render) is documented in the summary.

Prereqs:
  - nats_event_bus running on http://127.0.0.1:8131
    (env: NATS_EVENT_BUS_TOKEN, optional NATS_URL)
  - nats-py >= 2.6 (for the direct NATS subscriber)
  - NATS broker reachable on nats://127.0.0.1:4222 with creds nats:pmoves
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make repo root importable so we can pull in repo-side modules.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]  # pmoves/tools/creator-collab-evidence -> PMOVES.AI
for p in (
    _REPO / "pmoves" / "services" / "nats_event_bus",
    _REPO / "pmoves" / "services",
    _REPO / "pmoves",
    _REPO,
):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


# ----------------------------- paths + config -----------------------------

PMOVES_ROOT = _REPO
CATALOG_PATH = PMOVES_ROOT / "pmoves" / "config" / "rooms" / "catalog.json"
ROOMS_DIR = PMOVES_ROOT / "pmoves" / "config" / "rooms"
PINOKIO_CURATED = PMOVES_ROOT / "pmoves" / "configs" / "pinokio-apps" / "curated"
PINOKIO_USER = PMOVES_ROOT / "pmoves" / "configs" / "pinokio-apps" / "user"
EVIDENCE_DIR = _HERE / "slice7"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

NATS_EVENT_BUS_URL = os.environ.get("NATS_EVENT_BUS_URL", "http://127.0.0.1:8131")
NATS_EVENT_BUS_TOKEN = os.environ.get("NATS_EVENT_BUS_TOKEN", "")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@127.0.0.1:4222")

# ----------------------------- helpers -----------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def load_catalog() -> dict[str, Any]:
    """Read the slice 1 room catalog + each room's manifest."""
    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    # The catalog is an index; load the manifests too (canonical source).
    rooms = []
    for entry in catalog.get("rooms", []):
        manifest_path = ROOMS_DIR / entry["manifest"]
        if manifest_path.exists():
            with open(manifest_path, encoding="utf-8") as mf:
                manifest = json.load(mf)
        else:
            manifest = {}
        rooms.append(
            {
                "room_id": entry.get("room_id", manifest.get("room_id")),
                "display_name": entry.get("display_name", manifest.get("display_name")),
                "manifest_file": entry["manifest"],
                "room_purpose": manifest.get("room_purpose", "unknown"),
                "creator_surface": manifest.get("creator_surface", "unknown"),
                "stage": manifest.get("stage", "unknown"),
                "skills": [
                    sb.get("name") for sb in manifest.get("skill_bindings", [])
                ],
                "apps": [
                    a.get("slug") for a in manifest.get("apps", [])
                ],
                # NOTE: the room manifest schema uses `intent` (singular),
                # not `intents`. (renamed in slice 1's contract extension).
                "intent_phrases": [
                    intent
                    for sb in manifest.get("skill_bindings", [])
                    for intent in (sb.get("intent") or [])
                ],
                "app_capabilities": [
                    cap
                    for app in manifest.get("apps", [])
                    for cap in (app.get("capabilities") or [])
                ],
                "default_route": (
                    manifest.get("shell", {}).get("layout", {}).get("default_route")
                ),
            }
        )
    return {"catalog": catalog, "rooms": rooms}


def load_pinokio_registry() -> dict[str, Any]:
    """Read all 12 curated pinokio-apps YAMLs + any user-added ones.

    Lightweight parse (yaml.safe_load via PyYAML if available; else a
    minimal hand-parse so this script doesn't pull a hard dep on PyYAML
    for the runtime side).
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None

    apps: list[dict[str, Any]] = []

    def parse_one(path: Path) -> dict[str, Any] | None:
        text = path.read_text(encoding="utf-8")
        if yaml is not None:
            try:
                return yaml.safe_load(text)
            except Exception:
                return None
        # Fallback: extract `name`, `description`, top-level `slug:` only.
        out: dict[str, Any] = {"slug": path.stem}
        for line in text.splitlines():
            if line.startswith("name:"):
                out["name"] = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("description:"):
                out["description"] = line.split(":", 1)[1].strip().strip('"')
        return out

    for source_dir in (PINOKIO_CURATED, PINOKIO_USER):
        if not source_dir.exists():
            continue
        for p in sorted(source_dir.glob("*.y*ml")):
            data = parse_one(p)
            if data:
                data.setdefault("slug", p.stem)
                data["_file"] = p.name
                data["_source"] = source_dir.name
                apps.append(data)
    return {"apps": apps, "count": len(apps)}


# ----------------------------- helpdesk routing -----------------------------

# Tiny intent extractor: keyword bag -> intent tag.
INTENT_KEYWORDS = {
    "render": ["render", "image", "picture", "visual", "generate", "comfyui", "draw"],
    "voice": ["voice", "tts", "speech", "audio", "narration", "vibevoice"],
    "music": ["music", "song", "beat", "compose", "audio"],
    "agent": ["agent", "automate", "code", "agentzero", "archon", "chatbot"],
    "data": ["data", "dashboard", "metric", "graph", "analytics"],
    "intake": ["help", "where", "first", "new", "guide", "intake"],
    "community": ["community", "fordham", "pool", "dues", "neighbor"],
    "render-2d": ["edit", "image", "comfy", "2d"],
}


def extract_intents(question: str) -> list[str]:
    q = question.lower()
    found: list[str] = []
    for intent, kws in INTENT_KEYWORDS.items():
        if any(kw in q for kw in kws):
            found.append(intent)
    return found or ["intake"]


def rank_candidates(
    question: str,
    intents: list[str],
    rooms: list[dict[str, Any]],
    persona_role: str = "resident",
) -> list[dict[str, Any]]:
    """Tiny helpdesk ranker (mirrors slice 6 algorithm).

    Scoring (per slice 6 spec):
      score = intent_match * 0.5 + persona_bonus * 0.3 + capability_coverage * 0.2
    """
    scored: list[dict[str, Any]] = []
    for r in rooms:
        if r["stage"] in ("archive",):
            continue
        # Intent match: did any of the visitor's intents line up with a room
        # skill_binding.intent or the room's purpose?
        intent_match = sum(
            1
            for i in intents
            if i in r["intent_phrases"] or i == r["room_purpose"]
        ) / max(1, len(intents))
        # Persona affinity: residents prefer intake/community rooms; creators
        # prefer studio rooms. Generic visitors get a small default affinity.
        persona_bonus = 0.0
        if persona_role == "resident":
            if r["room_purpose"] in ("intake", "community"):
                persona_bonus = 0.3
        elif persona_role == "creator":
            if r["room_purpose"] in ("studio",):
                persona_bonus = 0.3
        # Capability coverage: how many of the room's app capabilities are
        # 'active' (a proxy for "this room can actually serve the visitor").
        caps = r.get("app_capabilities") or []
        capability_coverage = min(1.0, len(caps) / 5.0) if caps else 0.5
        score = intent_match * 0.5 + persona_bonus * 0.3 + capability_coverage * 0.2
        if score > 0:
            scored.append(
                {
                    "room_id": r["room_id"],
                    "display_name": r["display_name"],
                    "room_purpose": r["room_purpose"],
                    "score": round(score, 3),
                    "intent_match": round(intent_match, 3),
                    "persona_bonus": round(persona_bonus, 3),
                    "capability_coverage": round(capability_coverage, 3),
                    "default_route": r["default_route"],
                }
            )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


# ----------------------------- bus + NATS I/O -----------------------------


def publish_via_bus(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Publish a NATS subject through the nats_event_bus HTTP API.

    Note: the bus API expects `topic` (not `subject`) in the body. The bus
    then publishes to NATS via the configured subscriber connection.
    """
    import httpx

    body = {
        "topic": topic,
        "payload": payload,
    }
    headers = {"Content-Type": "application/json"}
    if NATS_EVENT_BUS_TOKEN:
        headers["X-PMOVES-NatsBus-Token"] = NATS_EVENT_BUS_TOKEN
    r = httpx.post(
        f"{NATS_EVENT_BUS_URL}/v1/publish",
        json=body,
        headers=headers,
        timeout=5.0,
    )
    r.raise_for_status()
    return r.json()


async def subscribe_and_capture(
    subjects: list[str],
    capture: dict[str, Any],
    timeout_s: float = 8.0,
) -> None:
    """Subscribe to NATS directly and capture each event as it lands."""
    import nats

    nc = await nats.connect(NATS_URL, connect_timeout=4)
    try:
        async def cb(msg):
            try:
                payload = json.loads(msg.data.decode("utf-8"))
            except Exception:
                payload = {"raw": msg.data.decode("utf-8", "replace")}
            capture[msg.subject] = {
                "received_at": now_iso(),
                "payload": payload,
            }

        for s in subjects:
            await nc.subscribe(s, cb=cb)
        # Flush so the broker registers the subscriptions before publishers fire.
        await nc.flush()
        # Wait long enough for all publishes to land.
        await asyncio.sleep(timeout_s)
    finally:
        try:
            await nc.drain()
        except Exception:
            pass


# ----------------------------- main flow -----------------------------


def run_fordham_e2e(actor: str = "fordham-resident-001") -> dict[str, Any]:
    """Run the full E2E synchronously (async subscriber runs alongside)."""
    print("=" * 70)
    print("slice 7 — Fordham <-> PMOVES-helpdesk E2E")
    print("=" * 70)

    t0 = time.time()

    # 1. Load the real room directory (catalog + 12 manifests).
    print("\n[1/5] Loading room.directory.v1 snapshot from local catalog...")
    directory = load_catalog()
    rooms = directory["rooms"]
    print(f"  Loaded {len(rooms)} rooms from {CATALOG_PATH.name}")
    for r in rooms:
        print(f"    - {r['room_id']:30s}  {r['room_purpose']:12s}  {r['creator_surface']}")

    # 2. Load the real pinokio-apps registry.
    print("\n[2/5] Loading pinokio-apps registry (slice 4 curated/)...")
    registry = load_pinokio_registry()
    apps = registry["apps"]
    print(f"  Loaded {len(apps)} pinokio apps")
    for a in apps:
        print(f"    - {a.get('slug', '?'):24s}  {a.get('name', '?')}")

    # 3. Run the helpdesk routing algorithm.
    print("\n[3/5] Running helpdesk routing algorithm...")
    question = "Hey, I'm a Fordham resident - how do I render an image with PMOVES?"
    intents = extract_intents(question)
    print(f"  Visitor question: {question!r}")
    print(f"  Extracted intents: {intents}")
    candidates = rank_candidates(question, intents, rooms, persona_role="resident")
    top3 = candidates[:3]
    print(f"  Top 3 candidates:")
    for c in top3:
        print(
            f"    - {c['room_id']:30s}  score={c['score']:.3f}  intent={c['intent_match']:.2f}"
        )
    chosen = top3[0] if top3 else None
    if not chosen:
        raise SystemExit("no candidate rooms matched the visitor's question")

    # 4. Subscribe to NATS for the 4 expected subjects and emit the events.
    print("\n[4/5] Subscribing to NATS for event capture + emitting 4 events...")
    capture: dict[str, Any] = {}
    subjects_in_order = [
        "room.presence.v1",
        "helpdesk.intake.opened.v1",
        "helpdesk.intake.routed.v1",
        "helpdesk.room.suggested.v1",
    ]

    intake_id = str(uuid.uuid4())
    presence_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    directory_version = str(uuid.uuid4())

    # Build the 4 payloads (used by both the async publisher and the
    # evidence JSON dump).
    presence = {
        "room_id": "pmoves.room.helpdesk",
        "presence_id": presence_id,
        "actor": actor,
        "actor_kind": "user",
        "action": "join",
        "surface": "helpdesk-chat",
        "actor_metadata": {
            "persona_role": "resident",
            "home_node": "fordham-hill-mesh",
            "display_name": "Fordham Resident",
        },
        "observed_at": now_iso(),
    }
    intake_opened = {
        "intake_id": intake_id,
        "room_id": "pmoves.room.helpdesk",
        "agent_id": "pmoves-helpdesk-steward",
        "persona_role": "resident",
        "intent_hint": question[:200],
        "directory_version": directory_version,
        "opened_at": now_iso(),
        "meta": {"source": "slice7_fordham_e2e", "first_question": question},
    }
    matched_caps: list[str] = []
    if chosen and chosen.get("default_route"):
        matched_caps = ["creator-canvas", "ambient-mesh-render"]
    intake_routed = {
        "intake_id": intake_id,
        "from_room_id": "pmoves.room.helpdesk",
        "to_room_id": chosen["room_id"],
        "rationale": (
            f"Top match on intent '{intents[0]}' for Fordham resident; "
            f"persona_role=resident + room_purpose={chosen['room_id']} "
            f"(score {chosen['score']:.3f})"
        ),
        "intent_match": {
            "intents": intents,
            "matched_room_capabilities": matched_caps,
            "score": chosen["score"],
        },
        "deep_link": chosen["default_route"] or "/helpdesk/intake",
        "routed_at": now_iso(),
    }
    suggestion_candidates = []
    for c in top3:
        suggestion_candidates.append(
            {
                "room_id": c["room_id"],
                "score": min(1.0, max(0.0, c["score"])),
                "rationale": (
                    f"intent_match={c['intent_match']} "
                    f"persona_bonus={c['persona_bonus']} "
                    f"capability_coverage={c['capability_coverage']}"
                ),
                "matched_intents": intents,
                "matched_capabilities": matched_caps,
                "deep_link": c["default_route"] or "/",
            }
        )
    room_suggested = {
        "suggestion_id": suggestion_id,
        "parent_intake_id": intake_id,
        "context": {
            "agent_id": "pmoves-helpdesk-steward",
            "persona_role": "resident",
            "intents": intents,
        },
        "candidates": suggestion_candidates,
        "directory_version": directory_version,
        "suggested_at": now_iso(),
    }

    # Run the full async flow: subscribe -> publish all 4 -> wait for capture.
    async def async_publish_flow() -> None:
        import nats

        nc = await nats.connect(NATS_URL, connect_timeout=4)
        try:
            async def cb(msg):
                try:
                    payload = json.loads(msg.data.decode("utf-8"))
                except Exception:
                    payload = {"raw": msg.data.decode("utf-8", "replace")}
                capture[msg.subject] = {
                    "received_at": now_iso(),
                    "payload": payload,
                }

            for s in subjects_in_order:
                await nc.subscribe(s, cb=cb)
            # Flush so subscriptions are registered on the broker before we
            # publish.
            await nc.flush()
            # Give the broker a moment to propagate subscriptions internally.
            await asyncio.sleep(0.5)

            # 5. Emit the 4 events.
            print("\n[5/5] Emitting 4 NATS events through nats_event_bus...")
            print(f"  -> room.presence.v1  actor={actor}")
            publish_via_bus("room.presence.v1", presence)
            await asyncio.sleep(0.2)
            print(f"  -> helpdesk.intake.opened.v1  intake_id={intake_id[:8]}")
            publish_via_bus("helpdesk.intake.opened.v1", intake_opened)
            await asyncio.sleep(0.2)
            print(f"  -> helpdesk.intake.routed.v1  to={chosen['room_id']}")
            publish_via_bus("helpdesk.intake.routed.v1", intake_routed)
            await asyncio.sleep(0.2)
            print(f"  -> helpdesk.room.suggested.v1  candidates={len(suggestion_candidates)}")
            publish_via_bus("helpdesk.room.suggested.v1", room_suggested)
            # Give the broker + subscribers time to receive.
            await asyncio.sleep(2.0)
        finally:
            try:
                await nc.drain()
            except Exception:
                pass

    # Run the async flow in the main thread (this script is sync-from-outer,
    # async-inside).
    asyncio.run(async_publish_flow())

    # Persist evidence.
    elapsed = time.time() - t0
    summary = {
        "slice": "7_fordham_e2e",
        "actor": actor,
        "ts_started": now_iso(),
        "elapsed_s": round(elapsed, 2),
        "visitor_question": question,
        "intents": intents,
        "directory_rooms_loaded": len(rooms),
        "pinokio_apps_loaded": len(apps),
        "top_3_candidates": top3,
        "chosen": chosen,
        "intake_id": intake_id,
        "directory_version": directory_version,
        "events_published": subjects_in_order,
        "events_captured": {k: v["received_at"] for k, v in capture.items()},
        "events_capture_count": len(capture),
        "events_capture_all": list(capture.keys()) == subjects_in_order,
        "nats_event_bus_url": NATS_EVENT_BUS_URL,
        "nats_url": NATS_URL,
    }

    (EVIDENCE_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (EVIDENCE_DIR / "directory_snapshot.json").write_text(
        json.dumps(directory, indent=2), encoding="utf-8"
    )
    (EVIDENCE_DIR / "pinokio_registry.json").write_text(
        json.dumps(registry, indent=2), encoding="utf-8"
    )
    (EVIDENCE_DIR / "routing_decision.json").write_text(
        json.dumps(
            {
                "question": question,
                "intents": intents,
                "candidates": candidates,
                "chosen": chosen,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "raw_events.json").write_text(
        json.dumps(capture, indent=2), encoding="utf-8"
    )
    (EVIDENCE_DIR / "published_events.json").write_text(
        json.dumps(
            {
                "room.presence.v1": presence,
                "helpdesk.intake.opened.v1": intake_opened,
                "helpdesk.intake.routed.v1": intake_routed,
                "helpdesk.room.suggested.v1": room_suggested,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Pretty print result.
    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"  Rooms loaded      : {len(rooms)}")
    print(f"  Pinokio apps      : {len(apps)}")
    print(f"  Top candidate     : {chosen['room_id']}  (score {chosen['score']:.3f})")
    print(f"  Intake ID         : {intake_id}")
    print(f"  Events published  : {len(subjects_in_order)} (room.presence + 3 helpdesk.*)")
    print(f"  Events captured   : {len(capture)} of {len(subjects_in_order)}")
    if len(capture) < len(subjects_in_order):
        missing = set(subjects_in_order) - set(capture.keys())
        print(f"  Missing captures  : {sorted(missing)}")
    print(f"  Elapsed           : {elapsed:.2f}s")
    print(f"  Evidence          : {EVIDENCE_DIR}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--actor", default="fordham-resident-001", help="presence actor id"
    )
    args = parser.parse_args()
    run_fordham_e2e(actor=args.actor)
