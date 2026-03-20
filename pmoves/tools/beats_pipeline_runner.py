#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12",
#   "rich>=13",
#   "httpx>=0.27",
# ]
# ///
"""
beats_pipeline_runner.py — End-to-End Beats → CGP → A2UI Pipeline Orchestrator

Chains the four beats pipeline tools into a single invocation:

  1. analyze_beats.py  — fingerprint + cluster audio tracks
  2. beats_to_cgp.py   — convert sonic groups to CGP geometry
  3. chit_a2ui_bridge.py — transpile CGP to Remotion A2UI spec
  4. (optional) POST to a2ui-renderer /render → MP4/GIF/WebM

Usage:
    uv run pmoves/tools/beats_pipeline_runner.py run
    uv run pmoves/tools/beats_pipeline_runner.py run --group Allegro_balanced_Bright --render
    uv run pmoves/tools/beats_pipeline_runner.py run --cache --format gif
    uv run pmoves/tools/beats_pipeline_runner.py status
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(rich_markup_mode="rich")
console = Console()

TOOLS_DIR = Path(__file__).parent
DATA_DIR = TOOLS_DIR.parent / "data" / "beats"
DEFAULT_INPUT = DATA_DIR / "soundcloud" / "darkxside"
DEFAULT_PLAYLISTS = DATA_DIR / "playlists"
DEFAULT_SUMMARY = DEFAULT_PLAYLISTS / "groups_summary.json"
DEFAULT_FP = DEFAULT_INPUT / ".fingerprints.json"
DEFAULT_RENDERER = os.environ.get("A2UI_RENDERER_URL", "http://localhost:8105")


def _run_tool(script: str, args: list[str], label: str) -> subprocess.CompletedProcess:
    """Run a sibling PEP 723 tool via uv run."""
    tool_path = TOOLS_DIR / script
    cmd = ["uv", "run", "--script", str(tool_path)] + args
    console.print(f"  [dim]→ {label}[/]")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(TOOLS_DIR.parent.parent))
    if result.returncode != 0:
        console.print(f"  [red]✗ {label} failed (exit {result.returncode})[/]")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[-5:]:
                console.print(f"    [dim red]{line}[/]")
        raise typer.Exit(1)
    return result


@app.command()
def run(
    input_dir:   Path = typer.Option(DEFAULT_INPUT,    "--input",  "-i", help="Audio files folder"),
    output_dir:  Path = typer.Option(DEFAULT_PLAYLISTS, "--output", "-o", help="Pipeline output folder"),
    group:       Optional[str] = typer.Option(None,    "--group",  "-g", help="Process single group (default: all)"),
    n_groups:    int  = typer.Option(8,                "--n-groups",     help="Number of sonic groups"),
    sense_mode:  str  = typer.Option("auto",           "--sense-mode",   help="peek | glaze | gaze | auto"),
    cache:       bool = typer.Option(False,            "--cache",        help="Reuse cached fingerprints"),
    render:      bool = typer.Option(False,            "--render",       help="POST A2UI specs to renderer"),
    fmt:         str  = typer.Option("mp4",            "--format",       help="Render format: mp4 | gif | webm"),
    renderer:    str  = typer.Option(DEFAULT_RENDERER, "--renderer",     help="A2UI renderer base URL"),
    coherence:   float = typer.Option(0.5,             "--coherence",    help="CGP coherence parameter"),
    dry_run:     bool = typer.Option(False,            "--dry-run",      help="Show plan without executing"),
):
    """[bold cyan]Run the full beats → CGP → A2UI pipeline.[/bold cyan]

    Chains analyze_beats → beats_to_cgp → chit_a2ui_bridge → (optional) a2ui-renderer.
    """
    summary_path = output_dir / "groups_summary.json"
    fp_path = input_dir / ".fingerprints.json"

    console.print(Panel(
        "[bold]DARKXSIDE Beats Pipeline[/bold]\n"
        f"Input: {input_dir}\n"
        f"Output: {output_dir}\n"
        f"Mode: {sense_mode}  Groups: {n_groups}  Cache: {cache}  Render: {render}",
        border_style="cyan",
    ))

    if dry_run:
        console.print("[yellow]Dry run — no actions taken.[/]")
        _print_plan(input_dir, output_dir, group, cache, render, fmt)
        return

    # ── Step 1: Fingerprint + Cluster ────────────────────────────────────
    console.print("\n[bold]Step 1/3:[/] Sonic Fingerprinting + Clustering")

    if cache and fp_path.exists() and summary_path.exists():
        console.print("  [green]✓[/] Using cached fingerprints + groups")
    else:
        analyze_args = [
            "analyze",
            "--input", str(input_dir),
            "--output", str(output_dir),
            "--groups", str(n_groups),
            "--sense-mode", sense_mode,
        ]
        if cache and fp_path.exists():
            analyze_args.append("--cache")
        _run_tool("analyze_beats.py", analyze_args, "analyze_beats.py analyze")
        console.print("  [green]✓[/] Fingerprinting complete")

    # Load groups
    if not summary_path.exists():
        console.print(f"[red]✗ No groups_summary.json at {summary_path}[/]")
        raise typer.Exit(1)

    with open(summary_path) as f:
        groups_data = json.load(f)

    target_groups = groups_data
    if group:
        target_groups = [g for g in groups_data if g["group"] == group]
        if not target_groups:
            available = [g["group"] for g in groups_data]
            console.print(f"[red]Group '{group}' not found. Available: {available}[/]")
            raise typer.Exit(1)

    console.print(f"  Groups to process: {len(target_groups)}")

    # ── Step 2: CGP Generation ───────────────────────────────────────────
    console.print(f"\n[bold]Step 2/3:[/] CGP Geometry Generation ({len(target_groups)} groups)")

    cgp_dir = output_dir / "cgp"
    cgp_dir.mkdir(exist_ok=True)
    cgp_files = []

    for g in target_groups:
        gname = g["group"]
        cgp_out = cgp_dir / f"{gname}.cgp.json"
        _run_tool("beats_to_cgp.py", [
            "dump",
            "--summary", str(summary_path),
            "--fingerprints", str(fp_path),
            "--group", gname,
            "--coherence", str(coherence),
            "--output", str(cgp_out),
        ], f"beats_to_cgp dump → {gname}")
        cgp_files.append(cgp_out)

    console.print(f"  [green]✓[/] {len(cgp_files)} CGP packets generated")

    # ── Step 3: A2UI Transpilation ───────────────────────────────────────
    console.print(f"\n[bold]Step 3/3:[/] A2UI Transpilation ({len(cgp_files)} specs)")

    a2ui_dir = output_dir / "a2ui"
    a2ui_dir.mkdir(exist_ok=True)
    a2ui_files = []

    for cgp_file in cgp_files:
        stem = cgp_file.stem.replace(".cgp", "")
        a2ui_out = a2ui_dir / f"{stem}.a2ui.json"
        # chit_a2ui_bridge uses argparse — call via python directly
        # Use the same python that's running this script (consistent environment)
        bridge_path = str(TOOLS_DIR / "chit_a2ui_bridge.py")
        cmd = [sys.executable, bridge_path, "-i", str(cgp_file), "-o", str(a2ui_out)]
        console.print(f"  [dim]→ chit_a2ui_bridge → {stem}[/]")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"  [red]✗ Bridge failed for {stem}: {result.stderr.strip()}[/]")
            continue
        a2ui_files.append(a2ui_out)

    console.print(f"  [green]✓[/] {len(a2ui_files)} A2UI specs generated")

    # ── Step 4 (Optional): Render ────────────────────────────────────────
    render_results = []
    if render and a2ui_files:
        console.print(f"\n[bold]Step 4:[/] Rendering ({len(a2ui_files)} specs → {fmt})")
        import httpx

        for a2ui_file in a2ui_files:
            stem = a2ui_file.stem.replace(".a2ui", "")
            try:
                with open(a2ui_file) as f:
                    spec = json.load(f)
                resp = httpx.post(
                    f"{renderer}/render",
                    params={"format": fmt},
                    json=spec,
                    headers={"Content-Type": "application/json"},
                    timeout=120.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    render_results.append({"group": stem, "url": data.get("url", ""), "ok": True})
                    console.print(f"  [green]✓[/] {stem} → {data.get('url', 'rendered')}")
                else:
                    render_results.append({"group": stem, "error": resp.text[:100], "ok": False})
                    console.print(f"  [yellow]⚠[/] {stem} → HTTP {resp.status_code}")
            except httpx.ConnectError:
                console.print(f"  [yellow]⚠[/] Renderer at {renderer} not reachable — skipping remaining renders")
                # Record all remaining as skipped so summary is accurate
                remaining = a2ui_files[a2ui_files.index(a2ui_file):]
                for skip in remaining:
                    render_results.append({"group": skip.stem.replace(".a2ui", ""), "error": "renderer unreachable", "ok": False})
                break
            except Exception as e:
                render_results.append({"group": stem, "error": str(e)[:100], "ok": False})
                console.print(f"  [red]✗[/] {stem} → {e}")

    # ── Summary ──────────────────────────────────────────────────────────
    _print_summary(target_groups, cgp_files, a2ui_files, render_results, output_dir)


@app.command()
def status():
    """[bold]Show current pipeline state — cached data, groups, outputs.[/bold]"""
    table = Table(title="Beats Pipeline State", border_style="cyan")
    table.add_column("Asset", style="bold")
    table.add_column("Path")
    table.add_column("Status")

    fp_exists = DEFAULT_FP.exists()
    table.add_row(
        "Fingerprints",
        str(DEFAULT_FP.relative_to(TOOLS_DIR.parent.parent)),
        "[green]cached[/]" if fp_exists else "[dim]missing[/]",
    )

    summary_exists = DEFAULT_SUMMARY.exists()
    n_groups = 0
    if summary_exists:
        with open(DEFAULT_SUMMARY) as f:
            n_groups = len(json.load(f))
    table.add_row(
        "Groups Summary",
        str(DEFAULT_SUMMARY.relative_to(TOOLS_DIR.parent.parent)),
        f"[green]{n_groups} groups[/]" if summary_exists else "[dim]missing[/]",
    )

    cgp_dir = DEFAULT_PLAYLISTS / "cgp"
    n_cgp = len(list(cgp_dir.glob("*.cgp.json"))) if cgp_dir.exists() else 0
    table.add_row(
        "CGP Packets",
        str(cgp_dir.relative_to(TOOLS_DIR.parent.parent)) if cgp_dir.exists() else "—",
        f"[green]{n_cgp} files[/]" if n_cgp else "[dim]none[/]",
    )

    a2ui_dir = DEFAULT_PLAYLISTS / "a2ui"
    n_a2ui = len(list(a2ui_dir.glob("*.a2ui.json"))) if a2ui_dir.exists() else 0
    table.add_row(
        "A2UI Specs",
        str(a2ui_dir.relative_to(TOOLS_DIR.parent.parent)) if a2ui_dir.exists() else "—",
        f"[green]{n_a2ui} files[/]" if n_a2ui else "[dim]none[/]",
    )

    # Playlist M3U8 files
    n_m3u8 = len(list(DEFAULT_PLAYLISTS.glob("*.m3u8")))
    table.add_row(
        "Playlists",
        str(DEFAULT_PLAYLISTS.relative_to(TOOLS_DIR.parent.parent)),
        f"[green]{n_m3u8} M3U8[/]" if n_m3u8 else "[dim]none[/]",
    )

    # Audio tracks
    n_tracks = 0
    if DEFAULT_INPUT.exists():
        suffixes = {".mp3", ".m4a", ".opus", ".flac", ".wav", ".ogg", ".aac"}
        n_tracks = len([p for p in DEFAULT_INPUT.rglob("*") if p.suffix.lower() in suffixes])
    table.add_row(
        "Audio Tracks",
        str(DEFAULT_INPUT.relative_to(TOOLS_DIR.parent.parent)),
        f"[green]{n_tracks} files[/]" if n_tracks else "[dim]none[/]",
    )

    console.print(table)


def _print_plan(input_dir, output_dir, group, cache, render, fmt):
    """Print what would happen without executing."""
    steps = [
        f"1. Analyze: {input_dir} → fingerprints + groups" + (" (cached)" if cache else ""),
        f"2. CGP: groups → {output_dir}/cgp/*.cgp.json" + (f" (group: {group})" if group else " (all groups)"),
        f"3. A2UI: CGP → {output_dir}/a2ui/*.a2ui.json",
    ]
    if render:
        steps.append(f"4. Render: A2UI → a2ui-renderer → {fmt}")

    for step in steps:
        console.print(f"  [dim]{step}[/]")


def _print_summary(groups, cgp_files, a2ui_files, render_results, output_dir):
    """Print final pipeline summary."""
    console.print()
    table = Table(title="Pipeline Summary", border_style="green")
    table.add_column("Stage", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Output")

    table.add_row("Groups Processed", str(len(groups)), str(output_dir / "groups_summary.json"))
    table.add_row("CGP Packets", str(len(cgp_files)), str(output_dir / "cgp/"))
    table.add_row("A2UI Specs", str(len(a2ui_files)), str(output_dir / "a2ui/"))

    if render_results:
        ok = sum(1 for r in render_results if r.get("ok"))
        table.add_row("Renders", f"{ok}/{len(render_results)}", "a2ui-renderer")

    console.print(table)


if __name__ == "__main__":
    app()
