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
        "spec":    "chit.cgp.v0.2",
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
        return {"spec": "chit.cgp.v0.2", "super_nodes":
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


def validate_cgp_v2(cgp: dict) -> None:
    """Reject a schema-invalid CGP v2 packet before it reaches NATS (spec §8).

    On a real validation failure this logs the offending field and raises
    ``typer.Exit(1)`` so the publish never happens. If the validator library or
    the schema file is unavailable the check is *skipped with a visible warning*
    rather than silently — an absent optional dependency is not evidence that the
    packet is malformed, so we do not block publishing on it.
    """
    try:
        import jsonschema
    except ImportError:
        console.print("  [yellow]⚠ CGP v2 schema validation skipped — jsonschema not installed[/]")
        return
    try:
        schema = json.loads(_CGP_V2_SCHEMA_PATH.read_text(encoding="utf-8"))
    except OSError as e:
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


if __name__ == "__main__":
    app()
