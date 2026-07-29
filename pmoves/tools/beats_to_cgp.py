#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12",
#   "rich>=13",
#   "numpy>=1.26",
#   "nats-py>=2.7",
#   "httpx>=0.27",
#   "jsonschema>=4",
# ]
# ///
"""
beats_to_cgp.py — DARKXSIDE Beats → Hyperdimensions Control Plane Bridge

Translates the sonic group analysis output from `analyze_beats.py` into
`geometry.cgp.v1` NATS events so Hyperdimensions renders each track and
sonic group as a navigable 3D constellation.

It also registers the GROUP-level state vector with the Hyperdimensions
Control Plane, turning sonic attributes into live parameter knobs:

  tempo_bpm         → delta  (phase velocity / tree-likeness)
  spectral_centroid → Hz     (spectral entropy / signal character)
  loudness_LRA      → kappa  (curvature / dynamic range)
  spectral_flatness → A      (attribution confidence / tonal clarity)
  coherence_score   → F      (swarm fitness / group separation quality)

This means the operator can literally "tune" the analysis by dragging the
Hyperdimensions knobs — and the NATS events flow back to re-parameterize
the Cipher Beats Analyst in real-time.

Usage:
    # Render existing groups in Hyperdimensions
    uv run pmoves/tools/beats_to_cgp.py render

    # Render a single group by name
    uv run pmoves/tools/beats_to_cgp.py render --group "Allegro_balanced_Bright"

    # Watch mode: re-publish whenever groups_summary.json changes
    uv run pmoves/tools/beats_to_cgp.py watch

    # Dump CGP JSON without publishing (inspect mode)
    uv run pmoves/tools/beats_to_cgp.py dump --group "Allegro_balanced_Bright"
"""

import asyncio
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from pmoves.tools.cgp_v2_build import build_attribution, build_hyperbolic_block
from pmoves.tools.chit_security import sign_cgp
from pmoves.tools.analyze_beats import (
    _tempo_label, _timbre_label, _energy_label, _character,
)

app = typer.Typer(
    name="beats-to-cgp",
    help="DARKXSIDE Beats → Hyperdimensions CGP Bridge",
    rich_markup_mode="rich",
)
console = Console()

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SUMMARY   = os.environ.get("BEATS_SUMMARY",  "pmoves/data/beats/playlists/groups_summary.json")
DEFAULT_FP        = os.environ.get("BEATS_FP",        "pmoves/data/beats/soundcloud/darkxside/.fingerprints.json")
DEFAULT_NATS      = os.environ.get("NATS_URL",         "nats://nats:pmoves@nats:4222")
DEFAULT_GATEWAY   = os.environ.get("GATEWAY_URL",      "http://localhost:8100")
SUBJECT_CGP       = "geometry.cgp.v1"
SUBJECT_CTRL      = "geometry.beats.control.v1"


# ── State vector mapping ───────────────────────────────────────────────────────

def track_to_state_vector(rec: dict) -> dict:
    """
    Map a single track's sonic fingerprint to the Hyperdimensions state vector.

    delta  ← tempo_bpm     (normalized 60–180 → 0–1)
    Hz     ← spectral_centroid (normalized 500–8000 → 0–1)
    kappa  ← loudness_LRA  (normalized 0–20 LU → curvature −1–0)
    A      ← spectral_flatness (inverted: tonal=1.0, noisy=0.0)
    F      ← 0.5 default (overridden at group level with silhouette score)
    """
    bpm       = rec.get("tempo_bpm", 90.0)
    centroid  = rec.get("spectral_centroid", 2000.0)
    lra       = rec.get("loudness_LRA", 8.0)
    flatness  = rec.get("spectral_flatness", 0.3)

    delta = (bpm - 60) / 120.0               # 0 = Largo, 1 = Presto
    hz    = min(centroid / 8000.0, 1.0)       # 0 = bass, 1 = airy
    kappa = -(lra / 20.0)                     # tighter LRA = less curvature
    A     = 1.0 - min(flatness * 2, 1.0)      # tonal=1.0, noisy=0.0

    return {
        "delta": round(delta, 4),
        "kappa": round(kappa, 4),
        "Hz":    round(hz, 4),
        "A":     round(A, 4),
        "F":     0.5,                          # group-level coherence applied below
    }


def _stable_id(name: str) -> str:
    return hashlib.md5(name.encode()).hexdigest()[:12]


def fingerprint_hash(rec: dict) -> str:
    """Stable content hash over the grounding-relevant fields only.

    Excludes volatile fields (timestamps, sense_mode, transient flags) so the
    same audio + model revision always hashes identically (CI reproducibility)."""
    keep = ("name", "tempo_bpm", "spectral_centroid", "spectral_flatness",
            "loudness_LRA", "clap_embedding", "mfcc", "chroma",
            "spectral_contrast", "tonnetz", "onset_rate")
    canon = {k: rec[k] for k in keep if k in rec}
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def group_to_cgp(group: dict, fingerprints: dict[str, dict], coherence: float = 0.5) -> dict:
    """
    Convert a sonic group + its member fingerprints to a `geometry.cgp.v1` packet.

    Each track becomes a Point (audio modality → ConeGeometry in Hyperdimensions).
    The group centroid becomes the Constellation anchor.
    The group state vector is broadcast as the control-plane knob values.
    """
    group_name  = group["group"]
    track_names = group["tracks"]
    members     = [fingerprints[n] for n in track_names if n in fingerprints]

    if not members:
        return {}

    # Group centroid state vector
    avg_bpm      = float(np.mean([r.get("tempo_bpm", 90)       for r in members]))
    avg_centroid = float(np.mean([r.get("spectral_centroid", 2000) for r in members]))
    avg_lra      = float(np.mean([r.get("loudness_LRA", 8)     for r in members]))
    avg_flatness = float(np.mean([r.get("spectral_flatness", 0.3) for r in members]))
    group_sv     = {
        "delta": round((avg_bpm - 60) / 120.0, 4),
        "kappa": round(-(avg_lra / 20.0), 4),
        "Hz":    round(min(avg_centroid / 8000.0, 1.0), 4),
        "A":     round(1.0 - min(avg_flatness * 2, 1.0), 4),
        "F":     round(coherence, 4),
    }

    # Place constellation on sphere surface (BPM → elevation, centroid → azimuth)
    theta = group_sv["delta"] * math.pi              # 0–π elevation
    phi   = group_sv["Hz"] * 2 * math.pi            # 0–2π azimuth
    r     = 10 + group_sv["F"] * 5                  # radius 10–15 based on quality
    anchor = [
        round(r * math.sin(theta) * math.cos(phi), 3),
        round(r * math.sin(theta) * math.sin(phi), 3),
        round(r * math.cos(theta), 3),
    ]

    # Build Points (one per track)
    points = []
    for i, rec in enumerate(members):
        sv = track_to_state_vector(rec)
        # Offset each track point slightly from the constellation anchor
        offset = [
            sv["delta"] * 2 - 1,
            sv["Hz"] * 2 - 1,
            sv["kappa"],
        ]
        points.append({
            "id":       _stable_id(rec.get("name", f"track_{i}")),
            "label":    rec.get("name", f"track_{i}"),
            "modality": "audio",
            "proj":     [sv["Hz"], sv["delta"], abs(sv["kappa"])],   # RGB color
            "conf":     sv["A"],                                       # opacity = tonal clarity
            "sv":       sv,
            "offset":   offset,
            "duration_s": rec.get("duration_s", 0),
            "file":     rec.get("file", ""),
        })

    return {
        # Legacy packet: point.proj is a 3-element RGB array, which is NOT valid
        # under cgp.v2.schema.json (proj must be a scalar number). Labelled v0.1
        # so it is not mistaken for / validated as a v0.2 packet.
        "spec":    "chit.cgp.v0.1",
        "type":    "geometry.cgp.v1",
        "id":      _stable_id(group_name),
        "label":   group_name,
        "source":  "cipher_beats_analyst",
        "ts":      time.time(),
        "super_nodes": [{
            "id":          _stable_id(f"sn_{group_name}"),
            "label":       f"Beats: {group_name}",
            "type":        "beats_constellation",
            "x":           group_sv["delta"],
            "y":           group_sv["Hz"],
            "r":           r,
            "state_vector": group_sv,
            "constellations": [{
                "id":      _stable_id(f"c_{group_name}"),
                "label":   group_name,
                "anchor":  anchor,
                "spectrum": [group_sv["Hz"], group_sv["delta"], 1.0 - abs(group_sv["kappa"])],
                "points":  points,
            }],
        }],
        # Control plane metadata — Hyperdimensions can update these as knobs
        "control_plane": {
            "state_vector":       group_sv,
            "param_surface": {
                "sense_mode_threshold": 1.0 - group_sv["F"],   # low cohesion → lower gaze threshold
                "n_groups_hint":        max(2, round(group_sv["delta"] * 12)),
                "temperature":          0.3 + group_sv["delta"] * 0.4,
                "top_k":                max(5, round(group_sv["Hz"] * 20)),
            }
        }
    }


# ── CGP v2 builders ─────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# Deterministic full-embedding -> 2D projection. A fixed, seeded random matrix
# per dimensionality means similar 512-d embeddings map to similar 2D angles,
# so Poincaré placement reflects the WHOLE semantic vector (not just dims 0..1).
_PROJ_CACHE: dict[int, "np.ndarray"] = {}


def _proj_matrix(d: int) -> "np.ndarray":
    P = _PROJ_CACHE.get(d)
    if P is None:
        P = np.random.default_rng(42).standard_normal((d, 2))
        _PROJ_CACHE[d] = P
    return P


def _project_2d(vec: list[float]) -> "np.ndarray":
    """Project an arbitrary-length vector to 2D via a fixed seeded matrix.

    Deterministic: same input -> same 2D point -> same Poincaré angle. For
    vectors shorter than 2 dims, pad with zeros and return as-is (length 2)."""
    v = np.asarray(vec, dtype=float).reshape(-1)
    if v.shape[0] < 2:
        out = np.zeros(2, dtype=float)
        out[: v.shape[0]] = v
        return out
    return v @ _proj_matrix(v.shape[0])


def _coerce_mfcc(mfcc, n: int = 20) -> list[float]:
    """Coerce an mfcc value to a fixed-length-`n` float list (pad/truncate).

    Guards against None or wrong-length mfcc so the constellation spectrum is
    always `n` plain floats and ``np.mean`` never builds a ragged object array."""
    if not mfcc:
        return [0.0] * n
    out = [0.0] * n
    for i, x in enumerate(mfcc[:n]):
        try:
            out[i] = float(x)
        except (TypeError, ValueError):
            out[i] = 0.0
    return out


def _group_anchor_vec(members: list[dict]) -> "np.ndarray":
    embs = [_project_2d(m["clap_embedding"]) for m in members if m.get("clap_embedding")]
    if not embs:
        return np.array([0.0, 0.0])
    return np.mean(np.array(embs), axis=0)


def build_cgp_v2(groups: list[dict], fingerprints: dict[str, dict], coherence: float = 0.5) -> dict:
    """Assemble a single signed CGP v2 packet across all groups.

    Each track is a point (modality 'audio'); each group is a constellation +
    a Poincaré hierarchy node; attribution is Dirichlet-weighted by track count.
    """
    super_constellations = []
    hb_groups: dict[str, np.ndarray] = {}
    hb_members: dict[str, dict[str, np.ndarray]] = {}
    raw_contrib: dict[str, float] = {}

    for g in groups:
        gname = g["group"]
        members = [fingerprints[n] for n in g["tracks"] if n in fingerprints]
        if not members:
            continue
        gid = _stable_id(gname)
        hb_groups[gid] = _group_anchor_vec(members)
        hb_members[gid] = {}
        raw_contrib[gid] = float(len(members))

        points = []
        for i, rec in enumerate(members):
            sv = track_to_state_vector(rec)
            tid = _stable_id(rec.get("name", f"track_{i}"))
            emb = rec.get("clap_embedding")
            hb_members[gid][tid] = _project_2d(emb) if emb else np.array([0.0, 0.0])
            points.append({
                "id": tid,
                "label": rec.get("name", f"track_{i}"),
                "modality": "audio",
                # Schema requires point.proj to be a scalar number; the RGB-style
                # projection triple lives in meta.proj_rgb for downstream rendering.
                "proj": sv["Hz"],
                "conf": sv["A"],
                "summary": rec.get("name", ""),
                "meta": {"grounding": rec.get("grounding", "full"),
                         "duration_s": rec.get("duration_s", 0),
                         "proj_rgb": [sv["Hz"], sv["delta"], abs(sv["kappa"])],
                         "fingerprint_hash": fingerprint_hash(rec)},
            })
        anchor = _group_anchor_vec(members).tolist()
        super_constellations.append({
            "id": gid,
            "summary": gname,
            "anchor": anchor if anchor else [0.0, 0.0],
            "spectrum": list(np.mean(
                np.array([_coerce_mfcc(m.get("mfcc")) for m in members]), axis=0)),
            "points": points,
        })

    # NOTE: created_at is intentionally OMITTED from the signed body. A volatile
    # timestamp inside the HMAC scope would make the same audio sign differently
    # every run (spec §7 wants reproducible sigs). Provenance lives in `meta`
    # instead, and `meta.signed` is deterministic so it is safe to sign.
    cgp = {
        "spec": "chit.cgp.v0.2",
        "summary": "DARKXSIDE beats grounding (WS-A)",
        "meta": {"source": "cipher_beats_analyst", "coherence": round(coherence, 4),
                 "clap_model": os.environ.get("CLAP_MODEL_ID", "laion/larger_clap_music")},
        "hyperbolic": build_hyperbolic_block(hb_groups, hb_members),
        "attribution": build_attribution(raw_contrib),
        "super_nodes": [{
            "id": _stable_id("sn_beats"),
            "label": "Beats Grounding",
            "constellations": super_constellations,
        }],
    }

    # Graceful signing: sign_cgp raises RuntimeError if no CHIT key env is set.
    # Emit an UNSIGNED but schema-valid packet (sig is optional) rather than crash.
    # meta.signed is set BEFORE signing so it is covered by the HMAC and the
    # signature both reproduces (no timestamps) and verifies (verify_cgp signs
    # everything except `sig`).
    try:
        cgp["meta"]["signed"] = True
        cgp = sign_cgp(cgp, passphrase=os.environ.get("CHIT_PASSPHRASE"))
    except Exception as e:  # no signing key, or signing backend unavailable
        console.print(f"  [yellow]CGP signing skipped (unsigned packet):[/] {e}")
        cgp["meta"]["signed"] = False
    return cgp


def select_builder(v2: bool = True):
    """Return a (groups, fingerprints, coherence) -> cgp callable.

    v2  -> build_cgp_v2 (whole-packet, signed). Legacy -> per-group group_to_cgp,
    wrapped so the signature matches.
    """
    if v2:
        return build_cgp_v2
    def _legacy(groups, fps, coherence=0.5):
        built = [group_to_cgp(g, fps, coherence) for g in groups]
        return {"spec": "chit.cgp.v0.1", "super_nodes":
                [c["super_nodes"][0] for c in built if c]}
    return _legacy


# ── NATS publish ───────────────────────────────────────────────────────────────

async def publish_cgp(cgp: dict, nats_url: str):
    try:
        import nats as natspy
        nc = await natspy.connect(nats_url)
        await nc.publish(SUBJECT_CGP, json.dumps(cgp).encode())
        # Also publish the control-plane knob update (v1 packets only; v2 has no control_plane)
        if "control_plane" in cgp:
            ctrl = {"group": cgp.get("label", ""), "control_plane": cgp.get("control_plane", {})}
            await nc.publish(SUBJECT_CTRL, json.dumps(ctrl).encode())
        await nc.drain()
    except Exception as e:
        console.print(f"  [yellow]NATS publish skipped:[/] {e}")


# ── Schema validation fence ─────────────────────────────────────────────────────

_CGP_V2_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts" / "schemas" / "geometry" / "cgp.v2.schema.json"
)

# The v0.2 extension blocks the shared schema cannot mandate. cgp.v2.schema.json
# also validates v0.1 packets (spec enum includes "chit.cgp.v0.1"), which
# legitimately omit these, so they are NOT in the schema's top-level `required`
# list — `spec` + `super_nodes` alone satisfy it. We enforce them here for
# packets that advertise the v0.2 spec so a regressed builder cannot publish a v2
# packet stripped of its advertised hyperbolic/attribution payload.
_CGP_V2_REQUIRED_BLOCKS = ("hyperbolic", "attribution")


def validate_cgp_v2(cgp: dict) -> None:
    """Reject a schema-invalid CGP v2 packet before it reaches NATS (spec §8).

    On a real validation failure this logs the offending field and raises
    ``typer.Exit(1)`` so the publish never happens. If the validator library or
    the schema file is unavailable the check is *skipped with a visible warning*
    rather than silently — an absent optional dependency is not evidence that the
    packet is malformed, so we do not block publishing on it.

    The v0.2 extension-block check runs *unconditionally* (it needs no validator
    library), so a v2 packet missing its hyperbolic/attribution payload is
    rejected even where ``jsonschema`` is not installed.
    """
    # v0.2-spec structural contract — the gap the shared JSON-Schema cannot cover.
    if cgp.get("spec") == "chit.cgp.v0.2":
        missing = [b for b in _CGP_V2_REQUIRED_BLOCKS if not isinstance(cgp.get(b), dict)]
        if missing:
            console.print(
                "  [red]✗ CGP v2 packet missing advertised extension block(s) — refusing to publish.[/]\n"
                f"    missing: {', '.join(missing)}"
            )
            raise typer.Exit(1)
    try:
        import jsonschema
    except ImportError:
        console.print("  [yellow]⚠ CGP v2 schema validation skipped — jsonschema not installed[/]")
        return
    try:
        schema = json.loads(_CGP_V2_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        console.print(f"  [yellow]⚠ CGP v2 schema validation skipped — cannot read {_CGP_V2_SCHEMA_PATH.name}: {e}[/]")
        return
    try:
        jsonschema.validate(cgp, schema)
    except jsonschema.ValidationError as e:
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        console.print(
            "  [red]✗ CGP v2 packet failed schema validation — refusing to publish.[/]\n"
            f"    {e.message} (at {loc})"
        )
        raise typer.Exit(1)


# ── Load helpers ──────────────────────────────────────────────────────────────

def load_summary(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        console.print(f"[red]groups_summary.json not found at {path}[/]")
        console.print("  Run: [bold]uv run pmoves/tools/analyze_beats.py analyze[/] first")
        raise typer.Exit(1)
    with open(p) as f:
        return json.load(f)


def load_fingerprints(path: str) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        console.print(f"[yellow].fingerprints.json not found at {path} — track-level detail unavailable[/]")
        return {}
    with open(p) as f:
        records = json.load(f)
    return {r["name"]: r for r in records}


# ═══════════════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def render(
    summary:     str  = typer.Option(DEFAULT_SUMMARY, "--summary", help="Path to groups_summary.json"),
    fingerprints: str = typer.Option(DEFAULT_FP,     "--fingerprints", help="Path to .fingerprints.json"),
    nats:        str  = typer.Option(DEFAULT_NATS,   "--nats",         help="NATS URL"),
    group:       Optional[str] = typer.Option(None,  "--group",        help="Render only this group name"),
    coherence:   float = typer.Option(0.5,           "--coherence",    help="Silhouette score to embed as swarm fitness F"),
    v2:          bool  = typer.Option(True, "--v2/--no-v2", help="Emit CGP v2 (hyperbolic+attribution+sig)"),
):
    """[bold cyan]Publish sonic group constellations to Hyperdimensions via NATS.[/bold cyan]"""
    groups = load_summary(summary)
    fps    = load_fingerprints(fingerprints)

    if group:
        groups = [g for g in groups if g["group"] == group]
        if not groups:
            console.print(f"[red]Group '{group}' not found.[/]")
            raise typer.Exit(1)

    if v2:
        cgp = select_builder(v2=True)(groups, fps, coherence=coherence)
        validate_cgp_v2(cgp)  # spec §8 fence: reject schema-invalid packets before publish

        async def _publish_one():
            await publish_cgp(cgp, nats)
            console.print(f"  [green]→[/] Published CGP v2 packet "
                          f"({len(groups)} groups) to [bold]{SUBJECT_CGP}[/]")

        asyncio.run(_publish_one())
        console.print(f"\n[bold green]✓ Done.[/] Open Hyperdimensions to see the constellations.")
        return

    table = Table("Group", "Tracks", "delta", "Hz", "kappa", "A", title="CGP State Vectors")

    async def _publish_all():
        for g in groups:
            cgp = group_to_cgp(g, fps, coherence=coherence)
            if not cgp:
                continue
            sv = cgp["control_plane"]["state_vector"]
            table.add_row(
                g["group"], str(g["count"]),
                str(sv["delta"]), str(sv["Hz"]), str(sv["kappa"]), str(sv["A"])
            )
            await publish_cgp(cgp, nats)
            console.print(f"  [green]→[/] Published [cyan]{g['group']}[/] ({g['count']} tracks) to [bold]{SUBJECT_CGP}[/]")

    asyncio.run(_publish_all())
    console.print(table)
    console.print(f"\n[bold green]✓ Done.[/] Open Hyperdimensions to see the constellations.")


@app.command()
def dump(
    summary:      str  = typer.Option(DEFAULT_SUMMARY, "--summary"),
    fingerprints: str  = typer.Option(DEFAULT_FP,      "--fingerprints"),
    group:        str  = typer.Option(...,              "--group", help="Group name to dump"),
    coherence:    float = typer.Option(0.5,             "--coherence"),
    output:       Optional[str] = typer.Option(None,   "--output", "-o", help="Write JSON to file"),
    v2:           bool  = typer.Option(True, "--v2/--no-v2", help="Emit CGP v2 (hyperbolic+attribution+sig)"),
):
    """[bold]Dump CGP JSON for a group without publishing (inspect mode).[/bold]"""
    groups = load_summary(summary)
    fps    = load_fingerprints(fingerprints)
    match  = next((g for g in groups if g["group"] == group), None)
    if not match:
        console.print(f"[red]Group '{group}' not found. Available: {[g['group'] for g in groups]}[/]")
        raise typer.Exit(1)

    if v2:
        cgp = select_builder(v2=True)([match], fps, coherence=coherence)
    else:
        cgp = group_to_cgp(match, fps, coherence=coherence)
    out = json.dumps(cgp, indent=2)

    if output:
        Path(output).write_text(out)
        console.print(f"[green]✓[/] Written to {output}")
    else:
        console.print_json(out)


@app.command()
def watch(
    summary:      str  = typer.Option(DEFAULT_SUMMARY, "--summary"),
    fingerprints: str  = typer.Option(DEFAULT_FP,      "--fingerprints"),
    nats:         str  = typer.Option(DEFAULT_NATS,    "--nats"),
    interval:     int  = typer.Option(30,              "--interval", help="Poll interval in seconds"),
):
    """[bold]Watch groups_summary.json and re-publish to Hyperdimensions on change.[/bold]"""
    import hashlib as _hash
    console.print(f"[cyan]Watching[/] {summary} every {interval}s — press Ctrl+C to stop.")

    last_hash = ""
    while True:
        try:
            content = Path(summary).read_bytes()
            h = _hash.md5(content).hexdigest()
            if h != last_hash:
                last_hash = h
                console.print(f"[yellow]Change detected[/] — re-publishing constellations…")
                # Re-invoke render logic inline
                groups = json.loads(content)
                fps    = load_fingerprints(fingerprints)
                async def _pub():
                    for g in groups:
                        cgp = group_to_cgp(g, fps)
                        if cgp:
                            await publish_cgp(cgp, nats)
                asyncio.run(_pub())
                console.print("[green]✓[/] Published.")
        except FileNotFoundError:
            pass
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/]")
            break
        time.sleep(interval)


@app.command()
def map_params(
    summary:      str  = typer.Option(DEFAULT_SUMMARY, "--summary"),
    fingerprints: str  = typer.Option(DEFAULT_FP,      "--fingerprints"),
):
    """[bold]Show the control-plane parameter mapping for all groups.[/bold]"""
    groups = load_summary(summary)
    fps    = load_fingerprints(fingerprints)

    table = Table(
        "Group", "δ delta", "κ kappa", "Hz", "A conf", "F fit",
        "temp", "top_k", "gaze threshold",
        title="Hyperdimensions Control Plane Param Map"
    )
    for g in groups:
        cgp = group_to_cgp(g, fps)
        if not cgp:
            continue
        sv = cgp["control_plane"]["state_vector"]
        ps = cgp["control_plane"]["param_surface"]
        table.add_row(
            g["group"][:30],
            str(sv["delta"]), str(sv["kappa"]), str(sv["Hz"]),
            str(sv["A"]), str(sv["F"]),
            str(round(ps["temperature"], 2)),
            str(ps["top_k"]),
            str(round(ps["sense_mode_threshold"], 2)),
        )
    console.print(table)


# ═══════════════════════════════════════════════════════════════════════════════
# export-hyperdim: Generate Hyperdimensions save files from real analysis data
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_HYPERDIM_SAVES = os.environ.get(
    "HYPERDIM_SAVES_DIR", "website/hyperdim/saves")
DEFAULT_EMBED_DIR = os.environ.get(
    "BEATS_EMBED_DIR", "website/embeds/beats-constellation")


def _group_aggregate(members: list[dict]) -> dict:
    """Compute rich aggregate features from group member fingerprints."""
    bpms = [r.get("tempo_bpm", 90) for r in members]
    centroids = [r.get("spectral_centroid", 2000) for r in members]
    flatnesses = [r.get("spectral_flatness", 0.3) for r in members]
    lras = [r.get("loudness_LRA", 8) for r in members]
    loudnesses = [r.get("loudness_I", -16) for r in members]
    onsets = [r.get("onset_rate", 2.0) for r in members]

    avg = {
        "tempo_bpm": float(np.mean(bpms)),
        "spectral_centroid": float(np.mean(centroids)),
        "spectral_flatness": float(np.mean(flatnesses)),
        "loudness_LRA": float(np.mean(lras)),
        "loudness_I": float(np.mean(loudnesses)),
        "onset_rate": float(np.mean(onsets)),
    }

    avg["tempo_label"] = _tempo_label(avg["tempo_bpm"])
    avg["timbre"] = _timbre_label(avg["spectral_centroid"])
    avg["character"] = _character(avg["spectral_flatness"])
    avg["energy"] = _energy_label(avg["loudness_I"])

    chroma_matrix = np.array(
        [r.get("chroma", [0] * 12) for r in members if "chroma" in r])
    if chroma_matrix.size > 0:
        avg["chroma_mean"] = [round(float(v), 6) for v in chroma_matrix.mean(axis=0)]
        avg["chroma_dominant"] = int(np.argmax(chroma_matrix.mean(axis=0)))
    else:
        avg["chroma_mean"] = [0.0] * 12
        avg["chroma_dominant"] = 0

    mfcc_matrix = np.array(
        [r.get("mfcc", [0] * 20) for r in members if "mfcc" in r])
    if mfcc_matrix.size > 0:
        avg["spectral_flux"] = round(
            float(np.mean(np.std(mfcc_matrix, axis=0))), 6)
    else:
        avg["spectral_flux"] = 0.0

    # Cymatic features: harmonicity/symmetry from member fingerprints
    cym_vals = [r.get("cymatic", {}) for r in members if r.get("cymatic")]
    if cym_vals:
        avg["cymatic"] = {
            "harmonic_ratio": round(float(np.mean(
                [c.get("harmonic_ratio", 0) for c in cym_vals])), 4),
            "symmetry": round(float(np.mean(
                [c.get("symmetry", 0) for c in cym_vals])), 4),
            "n_fold": int(np.median(
                [c.get("n_fold", 1) for c in cym_vals])),
            "rotational_symmetry": round(float(np.mean(
                [c.get("rotational_symmetry", 0) for c in cym_vals])), 4),
        }
    else:
        avg["cymatic"] = {}

    # Key/scale from chroma (Krumhansl-Schmuckler)
    if chroma_matrix.size > 0:
        from pmoves.tools.analyze_beats import _detect_key
        avg.update(_detect_key(chroma_matrix.mean(axis=0)))
    else:
        avg["key"] = "C"
        avg["scale"] = "major"
        avg["key_strength"] = 0.0

    # Beat times: collect and normalize for particle burst timing
    all_beats = []
    for r in members:
        beats = r.get("beat_times", [])
        if beats:
            all_beats.append(beats)
    valid_intervals = [np.mean(np.diff(b)) for b in all_beats if len(b) > 1]
    if valid_intervals:
        avg["avg_beat_interval"] = round(float(np.mean(valid_intervals)), 4)
    else:
        avg["avg_beat_interval"] = round(60.0 / max(avg["tempo_bpm"], 1), 4)

    return avg


_SURFACE_TEMPLATES = {
    "bass-heavy": '''function surface(input) {{
    const u = (input.u - 0.5) * 2 * Math.PI;
    const v = (input.v - 0.5) * 2 * Math.PI;
    const delta = input.delta ?? {delta};
    const kappa = input.kappa ?? {kappa};
    const hz = input.hz || {hz};
    const fitness = input.fitness || {fitness};
    const t = input.t || 0;
    const lobes = {lobes};
    const r_base = 2.5 + fitness * 1.5;
    const warp = Math.abs(kappa) * 10;
    const orbit = delta * 3;
    const R = r_base + Math.sin(u * lobes + t * orbit) * warp;
    const x = (R + Math.cos(v) * 0.8) * Math.cos(u);
    const y = (R + Math.cos(v) * 0.8) * Math.sin(u);
    const z = Math.sin(v) * 1.2 + Math.sin(u * (lobes + 2) + t * orbit) * warp * 0.5;
    const hue = hz * 6.2832;
    const r_col = 0.5 + 0.5 * Math.sin(hue + u);
    const g_col = 0.5 + 0.5 * Math.sin(hue + u + 2.094);
    const b_col = 0.5 + 0.5 * Math.sin(hue + u + 4.189);
    const a = 0.7 + fitness * 0.3;
    return {{ x, y, z, r: r_col, g: g_col, b: b_col, a }};
}}''',

    "warm": '''function surface(input) {{
    const u = input.u * 2 * Math.PI;
    const v = input.v * 4 * Math.PI;
    const delta = input.delta ?? {delta};
    const kappa = input.kappa ?? {kappa};
    const hz = input.hz || {hz};
    const fitness = input.fitness || {fitness};
    const t = input.t || 0;
    const turns = {lobes};
    const r_base = 0.5 + (u / (2 * Math.PI)) * (3 + fitness * 2);
    const spiral = delta * 0.8;
    const flare = Math.abs(kappa) * 6;
    const x = r_base * Math.cos(u * turns + t * spiral) + Math.sin(v) * flare * 0.3;
    const y = r_base * Math.sin(u * turns + t * spiral) + Math.cos(v) * flare * 0.3;
    const z = (u / (2 * Math.PI) - 0.5) * 4 + Math.sin(v * 2 + u * 3) * Math.abs(kappa) * 2;
    const hue = hz * 6.2832;
    const r_col = 0.5 + 0.5 * Math.sin(hue + u * 0.5);
    const g_col = 0.5 + 0.5 * Math.sin(hue + u * 0.5 + 2.094);
    const b_col = 0.5 + 0.5 * Math.sin(hue + u * 0.5 + 4.189);
    const a = 0.65 + fitness * 0.35;
    return {{ x, y, z, r: r_col, g: g_col, b: b_col, a }};
}}''',

    "balanced": '''function surface(input) {{
    const u = (input.u - 0.5) * 2 * Math.PI;
    const v = (input.v - 0.5) * 2 * Math.PI;
    const delta = input.delta ?? {delta};
    const kappa = input.kappa ?? {kappa};
    const hz = input.hz || {hz};
    const fitness = input.fitness || {fitness};
    const t = input.t || 0;
    const r_base = 3 + fitness * 2;
    const warp = kappa * 8;
    const orbit = delta * 2;
    const R = r_base + Math.sin(u * 3 + t * orbit) * warp;
    const x = (R + Math.cos(v)) * Math.cos(u);
    const y = (R + Math.cos(v)) * Math.sin(u);
    const z = Math.sin(v) + Math.sin(u * 5 + t * orbit * 2) * Math.abs(kappa) * 3;
    const hue = hz * 6.2832;
    const r_col = 0.5 + 0.5 * Math.sin(hue + u);
    const g_col = 0.5 + 0.5 * Math.sin(hue + u + 2.094);
    const b_col = 0.5 + 0.5 * Math.sin(hue + u + 4.189);
    const a = 0.7 + fitness * 0.3;
    return {{ x, y, z, r: r_col, g: g_col, b: b_col, a }};
}}''',

    "electric": '''function surface(input) {{
    const u = (input.u - 0.5) * 2 * Math.PI;
    const v = (input.v - 0.5) * 2 * Math.PI;
    const delta = input.delta ?? {delta};
    const kappa = input.kappa ?? {kappa};
    const hz = input.hz || {hz};
    const fitness = input.fitness || {fitness};
    const t = input.t || 0;
    const p = {lobes};
    const q = p + 2;
    const orbit = delta * 1.5;
    const r_base = 2 + fitness * 2;
    const cu = Math.cos(u * p + t * orbit);
    const su = Math.sin(u * p + t * orbit);
    const cv = Math.cos(v * q);
    const sv = Math.sin(v * q);
    const x = (r_base + cu) * Math.cos(u) + cv * Math.abs(kappa) * 3;
    const y = (r_base + cu) * Math.sin(u) + sv * Math.abs(kappa) * 3;
    const z = su + Math.sin(u * q + v * 2) * Math.abs(kappa) * 4;
    const hue = hz * 6.2832;
    const intensity = 0.5 + 0.5 * Math.sin(hue + u * p);
    const r_col = intensity;
    const g_col = 0.3 + 0.4 * Math.sin(hue + u + 2.094);
    const b_col = 0.5 + 0.5 * Math.cos(hue + v);
    const a = 0.7 + fitness * 0.3;
    return {{ x, y, z, r: r_col, g: g_col, b: b_col, a }};
}}''',

    "airy": '''function surface(input) {{
    const u = (input.u - 0.5) * Math.PI;
    const v = (input.v - 0.5) * 2 * Math.PI;
    const delta = input.delta ?? {delta};
    const kappa = input.kappa ?? {kappa};
    const hz = input.hz || {hz};
    const fitness = input.fitness || {fitness};
    const t = input.t || 0;
    const harmonics = {lobes};
    const r = 3.5 + fitness * 1.5;
    const theta = u + Math.sin(t * delta) * 0.3;
    const x = r * Math.sin(theta) * Math.cos(v);
    const y = r * Math.sin(theta) * Math.sin(v);
    const ripple = Math.sin(theta * harmonics + v * 2 + t * delta * 2) * Math.abs(kappa) * 4;
    const z = r * Math.cos(theta) + ripple;
    const hue = hz * 6.2832;
    const r_col = 0.5 + 0.5 * Math.sin(hue + theta * harmonics);
    const g_col = 0.5 + 0.5 * Math.sin(hue + theta * harmonics + 2.094);
    const b_col = 0.5 + 0.5 * Math.sin(hue + theta * harmonics + 4.189);
    const a = 0.6 + fitness * 0.4;
    return {{ x, y, z, r: r_col, g: g_col, b: b_col, a }};
}}''',

    # ProjectM/MilkDrop-inspired fluid surface — audio-reactive ripples
    # Bass frequencies drive wave amplitude; treble drives turbulence.
    # Used when cymatic symmetry is low (chaotic/noisy character).
    "fluid": '''function surface(input) {{
    const u = (input.u - 0.5) * 4 * Math.PI;
    const v = (input.v - 0.5) * 4 * Math.PI;
    const delta = input.delta ?? {delta};
    const kappa = input.kappa ?? {kappa};
    const hz = input.hz || {hz};
    const fitness = input.fitness || {fitness};
    const t = input.t || 0;
    const sym = {symmetry};
    const orbit = delta * 2;
    const r_base = 2 + fitness * 2;
    const flow = Math.sin(u * 2 + v * 1.5 + t * orbit) * 1.5;
    const ripple2 = Math.cos(u * 4 - v * 3 + t * orbit * 2) * Math.abs(kappa) * 3;
    const turb = Math.sin(u * 7 + v * 5 + t * orbit * 0.7) * (1 - sym) * 2;
    const x = (r_base + flow) * Math.cos(u) + turb * 0.5;
    const y = (r_base + flow) * Math.sin(u) + turb * 0.5;
    const z = ripple2 + Math.sin(v * 3 + t * orbit) * sym * 2;
    const hue = hz * 6.2832;
    const wave = 0.5 + 0.5 * Math.sin(hue + u * 2 + t * orbit);
    const r_col = wave * (0.4 + sym * 0.6);
    const g_col = 0.3 + 0.5 * Math.sin(hue + u + v + 2.094);
    const b_col = 0.5 + 0.5 * Math.sin(hue + v * 3 + 4.189) * sym;
    const a = 0.6 + fitness * 0.4;
    return {{ x, y, z, r: r_col, g: g_col, b: b_col, a }};
}}''',
}


# Key-to-color palette: circle of fifths hue mapping
# Each key gets a deterministic hue offset; major = warmer, minor = cooler
_KEY_HUE_OFFSET = {
    "C": 0.0,    "C#": 0.083, "D": 0.167, "D#": 0.25,
    "E": 0.333,  "F": 0.417,  "F#": 0.5,  "G": 0.583,
    "G#": 0.667, "A": 0.75,   "A#": 0.833, "B": 0.917,
}


def _key_to_palette(key: str, scale: str) -> dict:
    """Map musical key/scale to color palette for surface rendering."""
    hue = _KEY_HUE_OFFSET.get(key, 0.0)
    if scale == "minor":
        hue = (hue + 0.5) % 1.0  # shift to complementary for minor
    sat = 0.7 if scale == "major" else 0.5
    return {
        "hue_offset": round(hue, 4),
        "saturation": sat,
        "warmth": 1.0 if scale == "major" else 0.6,
        "palette_name": f"{key} {scale}",
    }


def _select_surface(timbre: str, chroma_dominant: int, onset_rate: float,
                    symmetry: float = 0.5) -> tuple[str, int]:
    """Select surface template based on sonic character + cymatic symmetry.

    Low symmetry (chaotic/noisy) triggers the fluid surface;
    high symmetry keeps the geometric topology."""
    if symmetry < 0.3:
        template = _SURFACE_TEMPLATES["fluid"]
    else:
        template = _SURFACE_TEMPLATES.get(timbre, _SURFACE_TEMPLATES["balanced"])
    lobes = max(3, min(8, chroma_dominant + 3 + int(onset_rate)))
    return template, lobes


def _build_hyperdim_save(group: dict, fps: dict[str, dict],
                         coherence: float = 0.5) -> dict | None:
    """Build a single Hyperdimensions save JSON from a sonic group."""
    members = [fps[n] for n in group["tracks"] if n in fps]
    if not members:
        return None

    agg = _group_aggregate(members)
    sv = track_to_state_vector(agg)

    # Cymatic symmetry modulates kappa: high symmetry = smoother curvature
    cym = agg.get("cymatic", {})
    sym = cym.get("symmetry", 0.5)
    # Blend: high symmetry pulls kappa toward 0 (smooth), low pushes negative
    sv["kappa"] = round(sv["kappa"] * (1.0 - sym * 0.5), 4)
    sv["F"] = round(coherence, 4)

    template, lobes = _select_surface(agg["timbre"], agg["chroma_dominant"],
                                      agg["onset_rate"], sym)
    # Build surface code — fluid template needs symmetry param
    surface_kwargs = dict(
        delta=sv["delta"], kappa=sv["kappa"], hz=sv["Hz"],
        fitness=sv["F"], lobes=lobes)
    if "fluid" in template:
        surface_kwargs["symmetry"] = round(sym, 3)
    surface_code = template.format(**surface_kwargs)

    onset_anim_speed = round(max(2, min(30, agg["onset_rate"] * 3)), 1)

    # Key/scale -> color palette
    palette = _key_to_palette(agg.get("key", "C"), agg.get("scale", "major"))

    # Beat interval for particle burst timing
    beat_interval = agg.get("avg_beat_interval", 0.5)

    return {
        "surface": {"code": surface_code},
        "parameters": {
            "uMin": 0, "uMax": 1, "vMin": 0, "vMax": 1,
            "uSegs": 120, "vSegs": 120,
        },
        "extraParameters": [
            {"name": "t", "value": 0, "min": 0, "max": 6.2832,
             "step": 0.01, "runtime": onset_anim_speed},
            {"name": "delta", "value": sv["delta"],
             "min": round(max(0, sv["delta"] - 0.1), 3),
             "max": round(min(1, sv["delta"] + 0.1), 3),
             "step": 0.005, "runtime": 12},
            {"name": "kappa", "value": sv["kappa"],
             "min": round(min(sv["kappa"], sv["kappa"] - 0.05), 3),
             "max": round(max(sv["kappa"], sv["kappa"] + 0.05), 3),
             "step": 0.005, "runtime": 15},
            {"name": "hz", "value": sv["Hz"],
             "min": round(max(0, sv["Hz"] - 0.1), 3),
             "max": round(min(1, sv["Hz"] + 0.1), 3),
             "step": 0.01, "runtime": 20},
            {"name": "fitness", "value": sv["F"],
             "min": 0.1, "max": 1.0, "step": 0.05, "runtime": 25},
        ],
        "display": {
            "autoRotate": True,
            "showAxes": False,
            "showSurface": True,
            "showWireframe": False,
            "dirIntensity": 1.2,
            "ambientIntensity": 0.5,
            "shininess": max(50, int(200 - agg["spectral_flux"] * 100)),
            "globalSaturation": 1.5 + sv["Hz"] * 0.6,
            "camera": {
                "position": {"x": 12, "y": 8, "z": 6},
                "target": {"x": 0, "y": 0, "z": 0},
            },
        },
        "outputs": {"coordConversion": "none", "rgbToHsv": False},
        "meta": {
            "source": "cipher_beats_analyst",
            "cgp_spec": "chit.cgp.v0.2",
            "group": group["group"],
            "tracks": len(members),
            "state_vector": sv,
            "sonic_profile": {
                "tempo_bpm": round(agg["tempo_bpm"], 1),
                "tempo_label": agg["tempo_label"],
                "timbre": agg["timbre"],
                "character": agg["character"],
                "energy": agg["energy"],
                "onset_rate": round(agg["onset_rate"], 3),
                "spectral_flux": agg["spectral_flux"],
                "chroma_dominant": agg["chroma_dominant"],
                "loudness_I": round(agg["loudness_I"], 1),
                "key": agg.get("key", "C"),
                "scale": agg.get("scale", "major"),
                "key_strength": agg.get("key_strength", 0.0),
                "beat_interval": beat_interval,
            },
            "cymatic": cym,
            "color_palette": palette,
            "surface_topology": "fluid" if sym < 0.3 else agg["timbre"],
            "inferred_shape": f"{agg['timbre'].title()} {agg['tempo_label']} Constellation",
            "pipeline": "analyze_beats -> beats_to_cgp export-hyperdim",
        },
    }


def _build_tracks_json(groups: list[dict],
                       fps: dict[str, dict]) -> list[dict]:
    """Build track data array for the beats-constellation embed."""
    import os
    audio_rel = os.environ.get(
        "BEATS_AUDIO_REL",
        "/audio/beats")
    tracks = []
    for g in groups:
        gname = g["group"]
        family_parts = gname.rsplit("_", 1)
        family = family_parts[0] if len(family_parts) > 1 else gname

        for tname in g["tracks"]:
            rec = fps.get(tname)
            if not rec:
                continue
            sv = track_to_state_vector(rec)
            file_path = rec.get("file", "")
            file_name = os.path.basename(file_path) if file_path else ""
            audio_url = f"{audio_rel}/{file_name}" if file_name else ""
            tracks.append({
                "name": tname,
                "group": gname,
                "family": family,
                "bpm": round(rec.get("tempo_bpm", 90), 1),
                "delta": sv["delta"],
                "hz": sv["Hz"],
                "A": sv["A"],
                "kappa": sv["kappa"],
                "timbre": rec.get("timbre", "balanced"),
                "character": rec.get("character", "textured"),
                "energy": _energy_label(rec.get("loudness_I", -16)),
                "onset_rate": round(rec.get("onset_rate", 0), 3),
                "loudness_I": round(rec.get("loudness_I", -16), 1),
                "duration_s": round(rec.get("duration_s", 0), 1),
                "audio_url": audio_url,
                "key": rec.get("key", "C"),
                "scale": rec.get("scale", "major"),
                "key_strength": rec.get("key_strength", 0.0),
                "beat_count": rec.get("beat_count", 0),
                "chroma": rec.get("chroma", []),
                "mfcc": rec.get("mfcc", []),
                "spectral_centroid": round(rec.get("spectral_centroid", 2000), 1),
                "spectral_flatness": round(rec.get("spectral_flatness", 0.3), 4),
                "cymatic": rec.get("cymatic", {}),
            })
    return tracks


@app.command(name="export-hyperdim")
def export_hyperdim(
    summary:      str  = typer.Option(DEFAULT_SUMMARY, "--summary"),
    fingerprints: str  = typer.Option(DEFAULT_FP,      "--fingerprints"),
    saves_dir:    str  = typer.Option(DEFAULT_HYPERDIM_SAVES, "--saves-dir",
                                      help="Hyperdimensions saves directory"),
    embed_dir:    str  = typer.Option(DEFAULT_EMBED_DIR, "--embed-dir",
                                      help="Beats-constellation embed directory"),
    coherence:    float = typer.Option(0.5, "--coherence"),
):
    """[bold cyan]Export analysis data to Hyperdimensions saves + constellation embed.[/bold cyan]

    Generates one parametric surface save per sonic group (with unique topology
    derived from timbre/spectral data), a constellation overview, and a
    tracks.json for the star-chart embed — all from real fingerprint data.
    """
    groups = load_summary(summary)
    fps = load_fingerprints(fingerprints)
    saves_path = Path(saves_dir)
    embed_path = Path(embed_dir)
    saves_path.mkdir(parents=True, exist_ok=True)
    embed_path.mkdir(parents=True, exist_ok=True)

    table = Table("Group", "Tracks", "Shape", "delta", "Hz", "kappa",
                  "Timbre", title="Hyperdimensions Export")
    written = []

    for g in groups:
        save = _build_hyperdim_save(g, fps, coherence)
        if not save:
            console.print(f"  [yellow]skip {g['group']} — no fingerprints[/]")
            continue

        fname = f"beats_{g['group'].split('_c')[-1]}.json"
        fpath = saves_path / fname
        fpath.write_text(json.dumps(save, indent=2), encoding="utf-8")

        meta = save["meta"]
        sv = meta["state_vector"]
        sp = meta["sonic_profile"]
        table.add_row(
            g["group"][:32], str(g["count"]),
            meta["surface_topology"],
            str(sv["delta"]), str(sv["Hz"]), str(sv["kappa"]),
            sp["timbre"],
        )
        written.append({"file": fname, "name": g["group"],
                        "group": g["group"]})

    if not written:
        console.print("[red]No groups exported — check fingerprint data.[/]")
        raise typer.Exit(1)

    all_track_names = [n for g in groups for n in g["tracks"]]
    overview = _build_hyperdim_save(
        {"group": "constellation", "tracks": all_track_names,
         "count": len(all_track_names)},
        fps, coherence)
    if overview:
        ov_members = [fps[n] for g in groups for n in g["tracks"] if n in fps]
        if ov_members:
            agg = _group_aggregate(ov_members)
            sv = track_to_state_vector(agg)
            cym = agg.get("cymatic", {})
            sym = cym.get("symmetry", 0.5)
            sv["kappa"] = round(sv["kappa"] * (1.0 - sym * 0.5), 4)
            sv["F"] = round(coherence, 4)
            template, lobes = _select_surface(
                agg["timbre"], agg["chroma_dominant"], agg["onset_rate"], sym)
            surface_kwargs = dict(
                delta=sv["delta"], kappa=sv["kappa"], hz=sv["Hz"],
                fitness=sv["F"], lobes=lobes)
            if "fluid" in template:
                surface_kwargs["symmetry"] = round(sym, 3)
            overview["surface"]["code"] = template.format(**surface_kwargs)
            palette = _key_to_palette(agg.get("key", "C"), agg.get("scale", "major"))
            overview["meta"]["group"] = "DARKXSIDE Beats Constellation"
            overview["meta"]["tracks"] = len(ov_members)
            overview["meta"]["state_vector"] = sv
            overview["meta"]["sonic_profile"] = {
                "tempo_bpm": round(agg["tempo_bpm"], 1),
                "tempo_label": agg["tempo_label"],
                "timbre": agg["timbre"],
                "character": agg["character"],
                "energy": agg["energy"],
                "onset_rate": round(agg["onset_rate"], 3),
                "spectral_flux": agg["spectral_flux"],
                "chroma_dominant": agg["chroma_dominant"],
                "loudness_I": round(agg["loudness_I"], 1),
                "key": agg.get("key", "C"),
                "scale": agg.get("scale", "major"),
                "key_strength": agg.get("key_strength", 0.0),
                "beat_interval": agg.get("avg_beat_interval", 0.5),
            }
            overview["meta"]["cymatic"] = cym
            overview["meta"]["color_palette"] = palette
            overview["meta"]["surface_topology"] = "fluid" if sym < 0.3 else agg["timbre"]
            overview["meta"]["inferred_shape"] = "Full Catalog Constellation"
            ov_path = saves_path / "beats_constellation.json"
            ov_path.write_text(json.dumps(overview, indent=2), encoding="utf-8")
            console.print(f"  [green]OK[/] Overview -> beats_constellation.json")

    tracks = _build_tracks_json(groups, fps)
    tracks_path = embed_path / "tracks.json"
    tracks_path.write_text(json.dumps(tracks, indent=2), encoding="utf-8")
    console.print(f"  [green]OK[/] {len(tracks)} tracks -> {tracks_path}")

    list_path = saves_path / "_list.json"
    if list_path.exists():
        existing = json.loads(list_path.read_text(encoding="utf-8"))
    else:
        existing = []

    beats_entries = [
        {"file": "beats_constellation.json",
         "name": "🎵 Beats Constellation (DARKXSIDE)"},
    ]
    for w in written:
        beats_entries.append(
            {"file": w["file"],
             "name": f"🎵 {w['group']}"})
    non_beats = [e for e in existing if not e["file"].startswith("beats")]
    updated = non_beats + beats_entries
    list_path.write_text(json.dumps(updated, indent=4), encoding="utf-8")
    console.print(f"  [green]OK[/] _list.json updated ({len(beats_entries)} beats entries)")

    console.print(table)
    console.print(f"\n[bold green]OK Export complete.[/] "
                  f"{len(written)} group saves + overview + tracks.json")
    console.print(f"  Saves -> {saves_path}/")
    console.print(f"  Embed -> {embed_path}/tracks.json")


if __name__ == "__main__":
    app()
