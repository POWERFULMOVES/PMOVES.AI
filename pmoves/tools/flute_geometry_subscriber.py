#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12",
#   "rich>=13",
#   "nats-py>=2.7",
# ]
# ///
"""
flute_geometry_subscriber.py — Flute Geometry CGP v0.2 Packet Consumer

Subscribes to `geometry.cgp.v1` NATS subject, decodes CGP v0.2 packets
into human-readable parameters, resolves chakra bands, and republishes
decoded results to `geometry.packet.decoded.v1` for the Flute/Remotion
rendering pipeline.

This is the missing consumer that bridges the geometry bus (publish side
lives in `beats_to_cgp.py`) and the Flute renderer.

State vector decode formulas (inverse of bpm_encoder.py):
    bpm             = delta * 120 + 60
    freq_hz         = Hz * 523.0
    dynamic_range_lu = -kappa * 20.0
    tonal_clarity   = A          (1.0 = fully tonal, 0.0 = noisy)
    swarm_fitness   = F          (0–1)

Usage:
    # Continuous listen (default, Ctrl+C to stop)
    uv run pmoves/tools/flute_geometry_subscriber.py listen

    # Dump last N packets from the bus and exit
    uv run pmoves/tools/flute_geometry_subscriber.py dump --count 5

    # Test mode: listen for 10 seconds, report packet count
    uv run pmoves/tools/flute_geometry_subscriber.py test
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="flute-geometry-subscriber",
    help="Flute Geometry CGP v0.2 Packet Consumer",
    rich_markup_mode="rich",
)
console = Console()

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_NATS = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
SUBJECT_CGP = "geometry.cgp.v1"
SUBJECT_DECODED = "geometry.packet.decoded.v1"
CGP_SPEC = "chit.cgp.v0.2"

# ── Chakra lookup ─────────────────────────────────────────────────────────────
# Import from the canonical chakra module with graceful fallback.
# The subscriber is in pmoves/tools/; chakra.py is in pmoves/services/common/.
_tools_dir = Path(__file__).resolve().parent
_project_root = _tools_dir.parent  # pmoves/
_services_common = _project_root / "services" / "common"

_freq_to_chakra = None
_CHAKRA_BANDS = None

try:
    _sys_path_backup = sys.path[:]
    if str(_services_common) not in sys.path:
        sys.path.insert(0, str(_services_common))
    if str(_tools_dir) not in sys.path:
        sys.path.insert(0, str(_tools_dir))
    from chakra import freq_to_chakra as _imported_freq_to_chakra, CHAKRA_BANDS as _imported_bands
    _freq_to_chakra = _imported_freq_to_chakra
    _CHAKRA_BANDS = _imported_bands
except ImportError:
    # Inline fallback — enough for Hz-based lookup
    _CHAKRA_BANDS = [
        {"name": "muladhara",    "label": "Root",      "element": "Earth",        "hz": 65.41,  "note": "C2"},
        {"name": "svadhisthana", "label": "Sacral",    "element": "Water",        "hz": 146.83, "note": "D3"},
        {"name": "manipura",     "label": "Solar",     "element": "Fire",         "hz": 164.81, "note": "E3"},
        {"name": "anahata",      "label": "Heart",     "element": "Air",          "hz": 349.23, "note": "F4"},
        {"name": "vishuddha",    "label": "Throat",    "element": "Ether",        "hz": 392.00, "note": "G4"},
        {"name": "ajna",         "label": "Third Eye", "element": "Light",        "hz": 440.00, "note": "A4"},
        {"name": "sahasrara",    "label": "Crown",     "element": "Consciousness", "hz": 523.25, "note": "C5"},
    ]

    def _fallback_freq_to_chakra(hz: float) -> dict[str, Any]:
        return min(_CHAKRA_BANDS, key=lambda b: abs(hz - b["hz"]))

    _freq_to_chakra = _fallback_freq_to_chakra
finally:
    # Restore sys.path to avoid polluting imports for other modules
    sys.path[:] = _sys_path_backup


# ── Packet decode ─────────────────────────────────────────────────────────────

def decode_state_vector(sv: dict[str, float]) -> dict[str, Any]:
    """Decode a CGP v0.2 state vector into human-readable parameters.

    Inverse of the encoding in bpm_encoder.py / beats_to_cgp.py:
        bpm              = delta * 120 + 60
        freq_hz          = Hz * 523.0
        dynamic_range_lu = -kappa * 20.0
        tonal_clarity    = A
        swarm_fitness    = F
    """
    delta = sv.get("delta", 0.0)
    hz_norm = sv.get("Hz", 0.0)
    kappa = sv.get("kappa", 0.0)
    A = sv.get("A", 0.0)
    F = sv.get("F", 0.0)

    bpm = delta * 120.0 + 60.0
    freq_hz = hz_norm * 523.0
    dynamic_range_lu = -kappa * 20.0

    # Resolve chakra from the actual frequency
    chakra = _freq_to_chakra(freq_hz) if _freq_to_chakra else None

    return {
        "bpm": round(bpm, 1),
        "freq_hz": round(freq_hz, 1),
        "dynamic_range_lu": round(dynamic_range_lu, 1),
        "tonal_clarity": round(A, 3),
        "swarm_fitness": round(F, 3),
        "chakra": {
            "name": chakra.get("name", "unknown") if chakra else "unknown",
            "label": chakra.get("label", "?") if chakra else "?",
            "element": chakra.get("element", "?") if chakra else "?",
            "note": chakra.get("note", "?") if chakra else "?",
        } if chakra else None,
    }


def validate_cgp_packet(packet: dict[str, Any]) -> list[str]:
    """Validate a CGP packet structure. Returns list of issues (empty = valid)."""
    issues: list[str] = []
    spec = packet.get("spec", "")
    if spec != CGP_SPEC:
        issues.append(f"Unexpected spec '{spec}' (expected '{CGP_SPEC}')")
    if "super_nodes" not in packet and "control_plane" not in packet:
        issues.append("Missing both super_nodes and control_plane")
    cp = packet.get("control_plane", {})
    if cp and "state_vector" not in cp:
        # State vector may also be in super_nodes
        sn = packet.get("super_nodes", [])
        if not any("state_vector" in s for s in sn):
            issues.append("No state_vector found in control_plane or super_nodes")
    return issues


def extract_state_vector(packet: dict[str, Any]) -> Optional[dict[str, float]]:
    """Extract the primary state vector from a CGP packet.

    Checks control_plane first, then falls back to the first super_node.
    """
    cp = packet.get("control_plane", {})
    if cp and "state_vector" in cp:
        return cp["state_vector"]

    for sn in packet.get("super_nodes", []):
        if "state_vector" in sn:
            return sn["state_vector"]

    return None


def process_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Full decode pipeline: validate → extract state vector → decode → enrich.

    Returns a decoded result dict ready for publishing to
    `geometry.packet.decoded.v1`.
    """
    issues = validate_cgp_packet(packet)
    sv = extract_state_vector(packet)

    result: dict[str, Any] = {
        "spec": CGP_SPEC,
        "type": "geometry.packet.decoded.v1",
        "source_id": packet.get("id", ""),
        "source_label": packet.get("label", ""),
        "source": packet.get("source", ""),
        "original_ts": packet.get("ts", 0),
        "decoded_ts": time.time(),
        "validation": {
            "valid": len(issues) == 0,
            "issues": issues,
        },
    }

    if sv:
        decoded = decode_state_vector(sv)
        result["state_vector_raw"] = sv
        result["params"] = decoded
    else:
        result["params"] = None
        result["validation"]["issues"].append("No state vector to decode")

    # Carry forward control_plane param_surface if present
    cp = packet.get("control_plane", {})
    if cp and "param_surface" in cp:
        result["param_surface"] = cp["param_surface"]

    # Summarize super_nodes
    super_nodes = packet.get("super_nodes", [])
    if super_nodes:
        result["super_nodes_summary"] = [
            {
                "id": sn.get("id", ""),
                "label": sn.get("label", ""),
                "type": sn.get("type", ""),
                "constellation_count": len(sn.get("constellations", [])),
            }
            for sn in super_nodes
        ]

    return result


# ── NATS helpers ──────────────────────────────────────────────────────────────

async def publish_decoded(decoded: dict[str, Any], nats_url: str) -> bool:
    """Publish a decoded packet to geometry.packet.decoded.v1.

    Uses the same lazy-import fail-open pattern as beats_to_cgp.py.
    Returns True on success, False on failure (never raises).
    """
    try:
        import nats as natspy
        nc = await natspy.connect(nats_url)
        payload = json.dumps(decoded).encode("utf-8")
        await nc.publish(SUBJECT_DECODED, payload)
        await nc.drain()
        return True
    except Exception as e:
        console.print(f"  [yellow]NATS publish skipped:[/] {e}")
        return False


# ── Shared state for modes ────────────────────────────────────────────────────

class _PacketStore:
    """Simple ring buffer for recent packets (used by dump mode)."""

    def __init__(self, maxlen: int = 100):
        self._buf: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self.count = 0

    def add(self, packet: dict[str, Any]) -> None:
        self._buf.append(packet)
        self.count += 1

    @property
    def recent(self) -> list[dict[str, Any]]:
        return list(self._buf)


# ── Listen mode ───────────────────────────────────────────────────────────────

async def _listen_loop(
    nats_url: str,
    republish: bool = True,
    quiet: bool = False,
    max_packets: int = 0,
) -> None:
    """Subscribe to geometry.cgp.v1 and continuously process packets.

    Args:
        nats_url: NATS connection URL.
        republish: If True, publish decoded results to geometry.packet.decoded.v1.
        quiet: If True, suppress per-packet console output.
        max_packets: If > 0, stop after this many packets (0 = infinite).
    """
    try:
        import nats as natspy
    except ImportError:
        console.print("[red]nats-py required for listen mode:[/] pip install nats-py")
        raise typer.Exit(1)

    store = _PacketStore()
    nc = await natspy.connect(nats_url)

    async def _handler(msg) -> None:
        try:
            raw = msg.data.decode("utf-8")
            packet = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            console.print(f"[red]Malformed packet:[/] {e}")
            return

        decoded = process_packet(packet)
        store.add(decoded)

        params = decoded.get("params")
        if params:
            if not quiet:
                chakra_info = params.get("chakra") or {}
                console.print(
                    f"  [green]→[/] [cyan]{decoded['source_label']}[/] | "
                    f"[bold]{params['bpm']:.0f} BPM[/] | "
                    f"[magenta]{params['freq_hz']:.0f} Hz[/] | "
                    f"[yellow]{chakra_info.get('label', '?')}[/] "
                    f"({chakra_info.get('element', '?')}) | "
                    f"clarity={params['tonal_clarity']:.2f} "
                    f"fitness={params['swarm_fitness']:.2f}"
                )

            if republish:
                ok = await publish_decoded(decoded, nats_url)
                if ok and not quiet:
                    console.print(f"    [dim]→ published to {SUBJECT_DECODED}[/]")
        else:
            if not quiet:
                issues = decoded.get("validation", {}).get("issues", [])
                console.print(
                    f"  [yellow]⚠[/] {decoded['source_label']} — "
                    f"no state vector: {'; '.join(issues)}"
                )

        if max_packets > 0 and store.count >= max_packets:
            raise _MaxPacketsReached(store.count)

    class _MaxPacketsReached(Exception):
        """Signal that the requested packet count has been reached."""
        pass

    await nc.subscribe(SUBJECT_CGP, cb=_handler)
    console.print(
        Panel(
            f"[bold green]Listening[/] on [cyan]{SUBJECT_CGP}[/]\n"
            f"Republishing decoded to [cyan]{SUBJECT_DECODED}[/]\n"
            f"NATS: [dim]{nats_url}[/]\n"
            f"Press [bold]Ctrl+C[/] to stop.",
            title="Flute Geometry Subscriber",
            border_style="green",
        )
    )

    try:
        while True:
            await asyncio.sleep(1)
    except _MaxPacketsReached as e:
        console.print(f"\n[yellow]Reached packet limit:[/] {e}")
    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print(f"\n[dim]Stopped after {store.count} packets.[/]")
    finally:
        await nc.drain()


# ── Test mode ─────────────────────────────────────────────────────────────────

async def _test_loop(nats_url: str, duration_sec: float = 10.0) -> int:
    """Subscribe for `duration_sec` seconds, count packets, exit."""
    try:
        import nats as natspy
    except ImportError:
        console.print("[red]nats-py required for test mode:[/] pip install nats-py")
        raise typer.Exit(1)

    count = 0
    nc = await natspy.connect(nats_url)

    async def _handler(msg) -> None:
        nonlocal count
        try:
            raw = msg.data.decode("utf-8")
            packet = json.loads(raw)
            decoded = process_packet(packet)
            params = decoded.get("params")
            count += 1

            chakra_info = (params or {}).get("chakra") or {}
            console.print(
                f"  [{count}] [cyan]{decoded['source_label']}[/] | "
                f"{params['bpm']:.0f} BPM | "
                f"{params['freq_hz']:.0f} Hz | "
                f"{chakra_info.get('label', '?')}"
                if params else f"  [{count}] [yellow]no state vector[/]"
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            count += 1
            console.print(f"  [{count}] [red]malformed[/]")

    await nc.subscribe(SUBJECT_CGP, cb=_handler)
    console.print(
        f"[cyan]Test mode:[/] listening on {SUBJECT_CGP} for {duration_sec:.0f}s…"
    )

    await asyncio.sleep(duration_sec)
    await nc.drain()
    return count


# ── Dump mode ─────────────────────────────────────────────────────────────────

async def _dump_loop(nats_url: str, count: int = 5, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Collect `count` packets (or timeout) and return them."""
    try:
        import nats as natspy
    except ImportError:
        console.print("[red]nats-py required for dump mode:[/] pip install nats-py")
        raise typer.Exit(1)

    collected: list[dict[str, Any]] = []
    event = asyncio.Event()
    nc = await natspy.connect(nats_url)

    async def _handler(msg) -> None:
        try:
            raw = msg.data.decode("utf-8")
            packet = json.loads(raw)
            decoded = process_packet(packet)
            collected.append(decoded)
            if len(collected) >= count:
                event.set()
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            console.print(f"  [red]Malformed packet:[/] {e}")

    await nc.subscribe(SUBJECT_CGP, cb=_handler)
    console.print(f"[cyan]Dump mode:[/] collecting {count} packets (timeout {timeout:.0f}s)…")

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        console.print(f"[yellow]Timeout:[/] collected {len(collected)}/{count} packets.")
    finally:
        await nc.drain()

    return collected


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Commands
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def listen(
    nats: str = typer.Option(DEFAULT_NATS, "--nats", help="NATS URL"),
    no_republish: bool = typer.Option(
        False, "--no-republish",
        help="Do not republish decoded packets to geometry.packet.decoded.v1",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress per-packet output"),
    max_packets: int = typer.Option(
        0, "--max-packets", "-n",
        help="Stop after N packets (0 = infinite)",
    ),
) -> None:
    """[bold cyan]Subscribe to geometry.cgp.v1 and continuously decode packets.[/bold cyan]"""
    asyncio.run(_listen_loop(
        nats_url=nats,
        republish=not no_republish,
        quiet=quiet,
        max_packets=max_packets,
    ))


@app.command()
def dump(
    nats: str = typer.Option(DEFAULT_NATS, "--nats", help="NATS URL"),
    count: int = typer.Option(5, "--count", "-n", help="Number of packets to collect"),
    timeout: float = typer.Option(30.0, "--timeout", "-t", help="Max seconds to wait"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Write JSON to file instead of stdout",
    ),
) -> None:
    """[bold]Collect N packets from the geometry bus, decode, and dump.[/bold]"""
    packets = asyncio.run(_dump_loop(nats_url=nats, count=count, timeout=timeout))

    if not packets:
        console.print("[yellow]No packets received.[/]")
        return

    # Build a rich summary table
    table = Table(
        "#", "Source", "BPM", "Hz", "Chakra", "Clarity", "Fitness",
        title=f"Decoded CGP Packets ({len(packets)} collected)",
    )
    for i, pkt in enumerate(packets, 1):
        p = pkt.get("params") or {}
        chakra_info = p.get("chakra") or {}
        table.add_row(
            str(i),
            pkt.get("source_label", "?")[:30],
            f"{p.get('bpm', 0):.0f}",
            f"{p.get('freq_hz', 0):.0f}",
            f"{chakra_info.get('label', '?')} ({chakra_info.get('element', '?')})",
            f"{p.get('tonal_clarity', 0):.2f}",
            f"{p.get('swarm_fitness', 0):.2f}",
        )
    console.print(table)

    # Output JSON
    out = json.dumps(packets, indent=2, default=str)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(out)
        console.print(f"\n[green]✓[/] Written to {output}")
    else:
        console.print("\n[bold]Raw decoded packets:[/]")
        console.print_json(out)


@app.command()
def test(
    nats: str = typer.Option(DEFAULT_NATS, "--nats", help="NATS URL"),
    duration: float = typer.Option(10.0, "--duration", "-d", help="Seconds to listen"),
) -> None:
    """[bold]Listen for N seconds, count packets, report, and exit.[/bold]"""
    started = time.monotonic()
    count = asyncio.run(_test_loop(nats_url=nats, duration_sec=duration))
    elapsed = time.monotonic() - started

    table = Table(title="Flute Geometry Subscriber — Test Report")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Packets received", str(count))
    table.add_row("Listen duration", f"{elapsed:.1f}s")
    table.add_row("Packets/sec", f"{count / max(elapsed, 0.001):.2f}")
    table.add_row("Subject", SUBJECT_CGP)
    table.add_row("Spec", CGP_SPEC)
    console.print(table)

    if count == 0:
        console.print(
            "\n[yellow]⚠ No packets received. "
            "Is `beats_to_cgp.py render` or another publisher running?[/]"
        )
    else:
        console.print(f"\n[bold green]✓[/] {count} packets decoded successfully.")


if __name__ == "__main__":
    app()
