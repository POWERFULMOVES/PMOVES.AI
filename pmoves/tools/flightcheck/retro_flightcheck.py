#!/usr/bin/env python3
"""
PMOVES Retro Flight Check
- Retro console vibes with Rich
- Validates tools, ports, repo shape, and .env keys

Run:
  python tools/flightcheck/retro_flightcheck.py
  python tools/flightcheck/retro_flightcheck.py --quick
  python tools/flightcheck/retro_flightcheck.py --json
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

import psutil
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
console = Console()

TOOLS = [
    ("docker", ["docker", "--version"]),
    ("git", ["git", "--version"]),
    ("node", ["node", "--version"]),
    ("npm", ["npm", "--version"]),
    ("python", ["python", "--version"]),
    ("uv", ["uv", "--version"]),
    ("jq", ["jq", "--version"]),
    ("rg", ["rg", "--version"]),
    ("make", ["make", "--version"]),
]

PORTS = [6333, 7474, 7700, 8088, 8085, 3000, 8087, 8084, 8077, 8078, 8092, 8093]
PORT_MAP = {
    6333: "qdrant",
    7474: "neo4j-ui",
    7700: "meilisearch",
    8088: "presign",
    8085: "render-webhook",
    3000: "postgrest",
    8087: "hi-rag-gateway-v2",
    8084: "langextract",
    8077: "pmoves-yt",
    8078: "ffmpeg-whisper",
    8092: "publisher-discord",
    8093: "jellyfin-bridge",
}

ENV_FILES = [ROOT / ".env", ROOT / ".env.example"]
CONTRACTS = ROOT / "contracts" / "topics.json"

HTTP_HEALTH = [
    ("qdrant", "http://localhost:6333/ready", "json_ok_or_200"),
    ("meilisearch", "http://localhost:7700/health", "json_ok_or_200"),
    ("postgrest", "http://localhost:3000", "http_200"),
    ("neo4j-ui", "http://localhost:7474", "http_200"),
    ("presign", "http://localhost:8088/healthz", "ok_true"),
    ("render-webhook", "http://localhost:8085/healthz", "ok_true"),
    ("hi-rag-gateway-v2", "http://localhost:8087/", "ok_true"),
    ("pmoves-yt", "http://localhost:8077/healthz", "ok_true"),
    ("ffmpeg-whisper", "http://localhost:8078/healthz", "ok_true"),
    ("publisher-discord", "http://localhost:8092/healthz", "ok_true"),
    ("jellyfin-bridge", "http://localhost:8093/healthz", "ok_true"),
]

THEMES = {
    "green": {
        "title_style": "bold black on bright_green",
        "border": "green",
        "accent": "bright_green",
    },
    "amber": {
        "title_style": "bold black on yellow",
        "border": "yellow",
        "accent": "bright_yellow",
    },
    "cb": {
        # colorblind-safe, high contrast palette
        "title_style": "bold white on blue",
        "border": "white",
        "accent": "white",
    },
    "neon": {
        # blue/purple neon arcade vibe
        "title_style": "bold white on #3b0a57",
        "border": "#8a2be2",  # blueviolet
        "accent": "#00e5ff",  # neon cyan
        "accent2": "#8a2be2", # purple
    },
    "galaxy": {
        # deep space purple/blue
        "title_style": "bold white on #1b1f3b",
        "border": "#7f5af0",
        "accent": "#00d1ff",
        "accent2": "#ff00a0",
    },
}

RETRO_SUB = Text("> initial diagnostic boot sequence", style="bold cyan")


def run_cmd(args: list[str]) -> tuple[bool, str]:
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=5)
        if cp.returncode == 0:
            out = (cp.stdout or cp.stderr).strip().splitlines()[0]
            return True, out
        return False, (cp.stdout + cp.stderr).strip()
    except FileNotFoundError:
        return False, "not installed"
    except Exception as e:
        return False, str(e)


def test_port(p: int) -> str:
    # Prefer psutil for speed
    for c in psutil.net_connections(kind="tcp"):
        if c.laddr and c.laddr.port == p and c.status == psutil.CONN_LISTEN:
            return "LISTENING"
    # Fallback socket bind check
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", p))
            return "free"
        except OSError:
            return "in use"


def who_uses_port(p: int) -> tuple[str | None, int | None]:
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.laddr and c.laddr.port == p and c.status == psutil.CONN_LISTEN and c.pid:
                try:
                    proc = psutil.Process(c.pid)
                    return proc.name(), c.pid
                except Exception:
                    return None, c.pid
    except Exception:
        pass
    return None, None


def read_env_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        if "=" in t:
            keys.add(t.split("=", 1)[0].strip())
    return keys


def retro_header(theme: str = "green"):
    t = THEMES.get(theme, THEMES["green"])
    title = Text("PMOVES: SYSTEMS CHECK", style=t["title_style"])
    console.print(Panel(title, box=box.SQUARE, border_style=t["border"]))
    console.print(RETRO_SUB)


PMOVES_BANNER = """
██████╗ ███╗   ███╗ ██████╗ ██╗   ██╗███████╗███████╗
██╔══██╗████╗ ████║██╔═══██╗██║   ██║██╔════╝██╔════╝
██████╔╝██╔████╔██║██║   ██║██║   ██║█████╗  ███████╗
██╔══██╗██║╚██╔╝██║██║   ██║██║   ██║██╔══╝  ╚════██║
██████╔╝██║ ╚═╝ ██║╚██████╔╝╚██████╔╝███████╗███████║
╚═════╝ ╚═╝     ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝╚══════╝
"""


def _banner_text_for_theme(theme: str) -> Text:
    t = THEMES.get(theme, THEMES["green"])
    if theme in ("neon", "galaxy") and "accent2" in t:
        # alternate lines between accent and accent2 for a quick retro gradient vibe
        lines = PMOVES_BANNER.strip("\n").splitlines()
        out = Text()
        for i, ln in enumerate(lines):
            color = t["accent"] if i % 2 == 0 else t["accent2"]
            out.append(ln + "\n", style=color)
        return out
    return Text(PMOVES_BANNER, style=t["accent"])


def boot_animation(theme: str = "green"):
    """CRT-like flicker followed by a big PMOVES banner."""
    t = THEMES.get(theme, THEMES["green"])
    noise_chars = [" ", "░", "▒", "▓", "░", " "]
    width = 60
    height = 6
    for i in range(8):
        lines = []
        for r in range(height):
            line = "".join(noise_chars[(i + r) % len(noise_chars)] for _ in range(width))
            lines.append(line)
        # tint the noise panel border with the theme border color
        console.print(Panel("\n".join(lines), border_style=t["border"], box=box.SQUARE), highlight=False)
        time.sleep(0.05)
    console.print(Panel(_banner_text_for_theme(theme), border_style=t["border"], box=box.HEAVY))


def section(title: str, body: str | None = None, border: str = "cyan"):
    console.print(Panel(Text(f"{title}", style="bold bright_cyan"), border_style=border, box=box.MINIMAL))
    if body:
        console.print(Text(body, style="bright_black"))


def check_tools():
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold green")
    table.add_column("tool", style="cyan")
    table.add_column("status")
    table.add_column("version")
    for name, args in TOOLS:
        ok, out = run_cmd(args)
        status = "OK" if ok else "--"
        version = out if ok else ""
        table.add_row(name, status, version)
    console.print(table)


def check_compose():
    ok, out = run_cmd(["docker", "compose", "version"])  # plugin
    if not ok:
        ok, out = run_cmd(["docker-compose", "--version"])  # v1 fallback
    msg = out if ok else "compose not detected"
    console.print(Panel(Text(msg, style="yellow" if ok else "red"), title="compose", border_style="yellow" if ok else "red"))


def parse_compose_ps_json() -> list[dict]:
    """Try docker compose ps --format json; fallback to docker ps."""
    ok, out = run_cmd(["docker", "compose", "ps", "--format", "json"])
    if ok:
        try:
            return json.loads(out)
        except Exception:
            pass
    # Fallback: docker ps --format "{{json .}}" per line
    ok, out = run_cmd(["docker", "ps", "--format", "{{json .}}"])
    if ok and out:
        lines = out.splitlines()
        items = []
        for ln in lines:
            try:
                items.append(json.loads(ln))
            except Exception:
                pass
        return items
    return []


def docker_container_health(container_name: str) -> str | None:
    ok, out = run_cmd(["docker", "inspect", container_name, "--format", "{{json .State.Health}}"])
    if not ok or not out:
        return None
    try:
        data = json.loads(out)
        if isinstance(data, dict) and "Status" in data:
            return data.get("Status")
    except Exception:
        return None
    return None


def check_docker_services():
    rows = parse_compose_ps_json()
    if not rows:
        console.print(Panel("no containers detected (is compose up?)", border_style="red", title="docker"))
        return
    table = Table(box=box.SIMPLE)
    table.add_column("name", style="magenta")
    table.add_column("state")
    table.add_column("health")
    for item in rows:
        # docker compose json has Service, Name, State; docker ps fallback has Names, Status
        name = item.get("Name") or item.get("Names") or item.get("Service") or "?"
        state = item.get("State") or item.get("Status") or "?"
        health = docker_container_health(name)
        table.add_row(name, state, health or "-")
    console.print(Panel(table, title="docker services", border_style="green"))


def check_repo_shape():
    wanted = ["services", "contracts", "schemas", "supabase", "neo4j", "n8n", "comfyui", "datasets", "docs"]
    table = Table(box=box.SIMPLE)
    table.add_column("path", style="magenta")
    table.add_column("exists")
    for d in wanted:
        exists = (ROOT / d).exists()
        table.add_row(d, "yes" if exists else "no")
    console.print(table)


def check_contracts():
    if not CONTRACTS.exists():
        console.print(Panel("contracts/topics.json: missing", border_style="red"))
        return
    try:
        json.loads(CONTRACTS.read_text(encoding="utf-8"))
        console.print(Panel("contracts/topics.json: valid", border_style="green"))
    except Exception as e:
        console.print(Panel(f"contracts/topics.json: invalid ({e})", border_style="red"))


def check_ports():
    table = Table(box=box.SIMPLE)
    table.add_column("port", style="bright_white")
    table.add_column("service", style="cyan")
    table.add_column("status")
    table.add_column("owner/hint", style="bright_black")
    for p in PORTS:
        st = test_port(p)
        name = PORT_MAP.get(p, "?")
        owner, pid = (None, None)
        if st != "free":
            owner, pid = who_uses_port(p)
            hint = f"{owner or 'unknown'} (pid {pid})" if pid else "occupied"
        else:
            hint = "ready"
        table.add_row(str(p), name, st, hint)
    console.print(table)


def _http_get(url: str, timeout: float = 4.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            ct = resp.headers.get("content-type", "")
            data = resp.read()
            body = data.decode("utf-8", errors="ignore")
            return resp.status, ct, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return e.code, "", body
    except Exception as e:
        return None, "", str(e)


def check_http():
    table = Table(box=box.SIMPLE)
    table.add_column("service", style="cyan")
    table.add_column("url", style="bright_white")
    table.add_column("status")
    table.add_column("detail", style="bright_black")
    for name, url, kind in HTTP_HEALTH:
        code, ct, body = _http_get(url)
        ok = False
        detail = ""
        if code is None:
            detail = body
        else:
            detail = f"{code}"
            if kind == "ok_true":
                try:
                    j = json.loads(body)
                    ok = bool(j.get("ok")) and code == 200
                except Exception:
                    ok = False
            elif kind == "json_ok_or_200":
                if code == 200:
                    ok = True
                else:
                    try:
                        json.loads(body)
                        ok = code == 200
                    except Exception:
                        ok = False
            elif kind == "http_200":
                ok = code == 200
        table.add_row(name, url, "PASS" if ok else "FAIL", detail)
    console.print(table)


def check_env():
    env_path, example_path = ENV_FILES
    env_keys = read_env_keys(env_path)
    ex_keys = read_env_keys(example_path)
    missing = sorted(list(ex_keys - env_keys))
    # duplicates in .env
    dups: dict[str, int] = {}
    if env_path.exists():
        seen = {}
        idx = 0
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            idx += 1
            t = line.strip()
            if not t or t.startswith("#") or "=" not in t:
                continue
            k = t.split("=", 1)[0].strip()
            if k in seen:
                dups[k] = dups.get(k, 1) + 1
            else:
                seen[k] = idx
    lines = [f".env present:     {env_path.exists()}", f".env.example:     {example_path.exists()}" ]
    if missing:
        lines.append("missing keys:")
        lines.extend([f"- {k}" for k in missing])
    if dups:
        lines.append("duplicate keys in .env (last one wins):")
        for k, n in sorted(dups.items()):
            lines.append(f"- {k} (x{n})")
    console.print(Panel("\n".join(lines), border_style="yellow" if missing else "green", title=".env"))


def run_quick(json_out: bool=False, theme: str = "green"):
    data = {
        "cwd": str(ROOT),
        "tools": {name: run_cmd(args)[0] for name, args in TOOLS},
        "compose": run_cmd(["docker", "compose", "version"])[0] or run_cmd(["docker-compose", "--version"])[0],
        "ports": {str(p): test_port(p) for p in PORTS},
        "env_missing": sorted(list(read_env_keys(ENV_FILES[1]) - read_env_keys(ENV_FILES[0]))),
    }
    if json_out:
        print(json.dumps(data, indent=2))
        return
    retro_header(theme=theme)
    section("quick scan")
    console.print(json.dumps(data, indent=2))


def chiptune_beep():
    # Windows refined beep; cross-platform fallback
    try:
        if os.name == 'nt':
            import winsound
            seq = [(880, 80), (988, 80), (1319, 90), (988, 80), (1760, 140)]
            for freq, dur in seq:
                winsound.Beep(freq, dur)
            return
    except Exception:
        pass
    for _ in range(2):
        print("\a", end="", flush=True)
        time.sleep(0.08)
    time.sleep(0.15)
    for _ in range(3):
        print("\a", end="", flush=True)
        time.sleep(0.06)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--theme", choices=["green", "amber", "cb", "neon", "galaxy"], default="green")
    parser.add_argument("--beep", action="store_true")
    parser.add_argument("--no-boot", action="store_true", help="skip CRT boot animation in full mode")
    args = parser.parse_args()

    if args.quick:
        run_quick(json_out=args.json, theme=args.theme)
        return

    retro_header(theme=args.theme)
    if not args.no_boot:
        boot_animation(theme=args.theme)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="booting diagnostics...", total=None)
        check_tools()
        check_compose()
        section("repo shape"); check_repo_shape()
        section("contracts"); check_contracts()
        section("ports"); check_ports()
        section("http health"); check_http()
        section("environment"); check_env()
        section("docker", body=None); check_docker_services()

    console.print(Panel(Text("ALL SYSTEMS READY", style="bold green"), border_style="green"))
    if args.beep:
        chiptune_beep()


if __name__ == "__main__":
    main()
