#!/usr/bin/env python3
"""Probe ACP registry launchers by speaking the Agent Client Protocol.

The ACP registry fork (POWERFULMOVES/PMOVES-registry, sibling checkout of
this repo) stores one ``<id>/agent.json`` per agent. Three launcher shapes
exist (FORMAT.md): ``npx``, ``uvx``, and platform ``binary`` archives. A
launcher "works" when the process it defines starts and answers an ACP
``initialize`` request with a JSON-RPC response on stdout.

The handshake shape, the sanitized environment, and the authMethods
criterion mirror the upstream registry's own CI harness
(``.github/workflows/client.py``), with three deliberate divergences:

  1. stdout/stderr reads use threads, not ``select`` — upstream's client
     only runs on their Linux CI; ``select`` cannot wait on Windows pipes.
  2. stderr is drained continuously. ``npx`` cold-installs write progress
     to stderr; an undrained pipe fills its OS buffer and the agent blocks
     forever mid-handshake (measured: the first probe of glm-acp-agent
     hung exactly this way before the drain existed).
  3. Windows termination kills the process tree (``taskkill /T``). ``npx``
     on Windows is a cmd shim over node children; killing only the shim
     orphans the children holding the pipes.

PASS here means "launcher starts and speaks ACP" (``result`` received);
the count of ``authMethods`` is reported alongside. Upstream's stricter
curation gate (at least one auth method of type agent/terminal) is
available behind ``--auth-required``.

Usage:
  python pmoves/tools/acp_launcher_probe.py --registry ../PMOVES-registry \
      --entries kilo,glm-acp-agent,minimax-code,qwen-code,codex-acp,claude-acp
  python pmoves/tools/acp_launcher_probe.py --entries kilo --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT.parent / "PMOVES-registry"

# Mirrors AGENT_ENV_PASSTHROUGH in the upstream registry CI client, plus
# the Windows resolver vars npm/node need (SYSTEMDRIVE, PROGRAMFILES...).
# Everything else — including every session credential — stays out of the
# agent environment on purpose.
ENV_PASSTHROUGH = {
    "CI", "COMSPEC", "NPM_CONFIG_CACHE", "NODE_EXTRA_CA_CERTS", "PATH",
    "PATHEXT", "PYTHON_KEYRING_BACKEND", "PYTHON_KEYRING_DISABLED",
    "REQUESTS_CA_BUNDLE", "SSL_CERT_DIR", "SSL_CERT_FILE", "SystemRoot",
    "TMP", "TMPDIR", "TEMP", "UV_CACHE_DIR", "WINDIR", "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMDATA",
    "APPDATA", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
}

INITIALIZE_PARAMS = {
    "protocolVersion": 1,
    "clientInfo": {"name": "PMOVES ACP Launcher Probe", "version": "1.0.0"},
    "clientCapabilities": {
        "terminal": True,
        "fs": {"readTextFile": True, "writeTextFile": True},
        "_meta": {"terminal_output": True, "terminal-auth": True},
    },
}

DEFAULT_TIMEOUT_S = 180  # cold npx/uvx installs are slow on first run


def _platform_key() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    system = platform.system().lower()
    if system.startswith("win"):
        return f"windows-{arch}"
    return f"{system}-{arch}" if system in ("linux", "darwin") else system


def _extract(archive: Path, dest: Path) -> None:
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar")):
        with tarfile.open(archive) as tf:
            tf.extractall(dest)
    else:
        # FORMAT.md: raw binaries are a supported distribution shape
        shutil.copy2(archive, dest / archive.name)
        dest_child = dest / archive.name
        dest_child.chmod(dest_child.stat().st_mode | 0o755)


def _npm_bin_name(package_spec: str, install_prefix: Path) -> str | None:
    """Resolve the bin name of an installed npm package (upstream parity).

    Mirrors verify_agents.npm_package_bin_name: read the installed
    package.json's ``bin`` field; fall back to the unscoped package
    basename, then to a single-entry .bin directory.
    """
    unscoped = package_spec.split("@", 1)[0] or package_spec
    name = ("@" + package_spec[1:].split("@")[0]) if package_spec.startswith("@") else unscoped
    pkg_json = install_prefix / "node_modules" / name / "package.json"
    if pkg_json.is_file():
        try:
            bin_field = json.loads(pkg_json.read_text(encoding="utf-8")).get("bin")
        except (OSError, json.JSONDecodeError):
            bin_field = None
        # npm bin semantics: "bin": "path.js" names the bin after the
        # package itself; "bin": {"name": "path.js"} keys are the names.
        if isinstance(bin_field, str):
            return name.rsplit("/", 1)[-1].lstrip("@")
        if isinstance(bin_field, dict) and bin_field:
            return next(iter(bin_field.keys()))
        if isinstance(bin_field, dict):
            return name.rsplit("/", 1)[-1].lstrip("@")
    bin_dir = install_prefix / "node_modules" / ".bin"
    if bin_dir.is_dir():
        children = sorted(p.name for p in bin_dir.iterdir())
        children = [c for c in children if not c.endswith((".ps1", ".npm", ".cmd", ".cmd."))]
        if name.rsplit("/", 1)[-1].lstrip("@") in children:
            return name.rsplit("/", 1)[-1].lstrip("@")
        if len(children) == 1:
            return children[0]
    return None


def _preinstall_npx(package_spec: str, cache_dir: Path, timeout_s: int) -> tuple[list[str] | None, str | None]:
    """Install the package like upstream prepare_npx_package, return (argv, error).

    Upstream installs before the handshake so postinstall hooks can run
    outside the ACP conversation; cold ``npx`` runs hang some agents
    (measured: minimax-code, 2026-09-16). Returns the installed bin argv.
    """
    npm_exe = shutil.which("npm")
    if not npm_exe:
        return None, "npm not on PATH"
    safe = package_spec.replace("@", "_").replace("/", "_").rstrip("_")
    prefix = cache_dir / "installs" / safe
    prefix.mkdir(parents=True, exist_ok=True)
    if not (prefix / "node_modules").is_dir():
        env = {k: v for k, v in os.environ.items() if k in ENV_PASSTHROUGH}
        env["NPM_CONFIG_CACHE"] = str(cache_dir / "npm")
        try:
            result = subprocess.run(
                [npm_exe, "install", "--no-audit", "--no-fund",
                 "--prefix", str(prefix), package_spec],
                capture_output=True, text=True, timeout=timeout_s, env=env,
            )
        except subprocess.TimeoutExpired:
            return None, f"npm install timed out after {timeout_s}s"
        except OSError as exc:
            return None, f"npm install failed: {exc}"
        if result.returncode != 0:
            tail = ((result.stderr or "") + (result.stdout or ""))[-400:]
            return None, f"npm install rc={result.returncode}: {tail}"
    bin_name = _npm_bin_name(package_spec, prefix)
    if not bin_name:
        return None, "could not resolve bin name after install"
    bin_path = prefix / "node_modules" / ".bin" / bin_name
    if os.name == "nt":
        cmd_path = bin_path.with_suffix(".cmd")
        if cmd_path.exists():
            bin_path = cmd_path
    if not bin_path.exists():
        return None, f"bin {bin_name!r} missing from node_modules/.bin"
    return [str(bin_path)], None


def resolve_command(entry: dict, cache_dir: Path, platform_key: str,
                     prefer: str = "auto", preinstall_npx: bool = True) -> tuple[list[str], str, dict]:
    """Return (argv, launcher_kind, extra_env) for an agent.json entry.

    Raises ValueError with a human-readable reason when the entry has no
    usable launcher for this platform.
    """
    dist = entry.get("distribution") or {}
    extra_env: dict = {}

    npx = dist.get("npx")
    if npx and npx.get("package") and prefer in ("auto", "npx"):
        pkg = str(npx["package"])
        args = [str(a) for a in npx.get("args", [])]
        if preinstall_npx:
            argv, err = _preinstall_npx(pkg, cache_dir, 600)
            if argv:
                return argv + args, "npx-installed", extra_env
            # fall through to cold npx; the error is reported via stderr note
            print(f"note: pre-install failed ({err}); using cold npx", file=sys.stderr)
        npx_exe = shutil.which("npx")
        if not npx_exe:
            raise ValueError("npx distribution but npx is not on PATH")
        return [npx_exe, "-y", pkg] + args, "npx", extra_env

    uvx = dist.get("uvx")
    if uvx and uvx.get("package") and prefer in ("auto", "uvx"):
        uvx_exe = shutil.which("uvx")
        if not uvx_exe:
            raise ValueError("uvx distribution but uvx is not on PATH")
        argv = [uvx_exe, str(uvx["package"])] + [str(a) for a in uvx.get("args", [])]
        return argv, "uvx", extra_env

    binary = dist.get("binary") or {}
    plat = binary.get(platform_key)
    if not plat and prefer in ("auto", "binary"):
        raise ValueError(
            f"binary distribution has no target for {platform_key} "
            f"(has: {sorted(binary) or 'none'})"
        )
    url = plat["archive"]
    name = url.rsplit("/", 1)[-1]
    archive = cache_dir / "archives" / name
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as resp, archive.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    want = plat.get("sha256")
    if want:
        got = hashlib.sha256(archive.read_bytes()).hexdigest()
        if got != want:
            archive.unlink(missing_ok=True)
            raise ValueError(f"sha256 mismatch: want {want}, got {got}")
    extract_dir = cache_dir / "extracted" / (name + ".d")
    cmd_rel = str(plat["cmd"]).lstrip("./")
    if not (extract_dir / cmd_rel).exists():
        extract_dir.mkdir(parents=True, exist_ok=True)
        _extract(archive, extract_dir)
    exe = extract_dir / cmd_rel
    if not exe.exists():
        raise ValueError(f"cmd {cmd_rel!r} not found after extract")
    exe.chmod(exe.stat().st_mode | 0o755)
    extra_env = {k: str(v) for k, v in (plat.get("env") or {}).items()}
    return [str(exe)] + [str(a) for a in plat.get("args", [])], "binary", extra_env


def _build_env(extra_env: dict, home_dir: Path) -> dict[str, str]:
    env = {name: value for name in ENV_PASSTHROUGH
           if (value := os.environ.get(name)) not in (None, "")}
    env["TERM"] = "dumb"
    env["HOME"] = str(home_dir)
    # Windows resolvers/npm want USERPROFILE; isolated like HOME so the
    # agent cannot read the operator's real profile.
    env["USERPROFILE"] = str(home_dir)
    env.update(extra_env)
    return env


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        # /T walks the tree: the npx.cmd shim's node children die too.
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
        )
        return
    try:
        import signal
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        proc.kill()


def probe(argv: list[str], timeout_s: int, extra_env: dict | None = None) -> dict:
    """Spawn the launcher, send ACP initialize, wait for the JSON-RPC reply."""
    home_dir = Path(tempfile.mkdtemp(prefix="pmoves-acp-probe-"))
    env = _build_env(extra_env or {}, home_dir)
    group_kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                    if os.name == "nt" else {"start_new_session": True})
    t0 = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=0,
            env=env,
            **group_kwargs,
        )
    except OSError as exc:
        return {"ok": False, "stage": "spawn", "error": str(exc)}

    stdout_lines: list[str] = []
    stderr_chunks: list[str] = []
    threading.Thread(
        target=lambda: stdout_lines.append(proc.stdout.readline()),
        daemon=True,
    ).start()
    threading.Thread(
        target=lambda: stderr_chunks.append(proc.stderr.read()),
        daemon=True,
    ).start()

    request = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": INITIALIZE_PARAMS}
    ) + "\n"
    try:
        proc.stdin.write(request)
        proc.stdin.flush()
    except OSError as exc:
        _kill_tree(proc)
        return {"ok": False, "stage": "write", "error": str(exc)}

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and not stdout_lines and proc.poll() is None:
        time.sleep(0.2)

    _kill_tree(proc)
    duration = round(time.monotonic() - t0, 1)
    stderr_tail = "".join(stderr_chunks)[-800:] if stderr_chunks else ""

    if proc.poll() is not None and not stdout_lines:
        return {
            "ok": False,
            "stage": "initialize",
            "error": f"process exited rc={proc.returncode} before replying",
            "stderr_tail": stderr_tail,
            "duration_s": duration,
        }
    if not stdout_lines or not stdout_lines[0]:
        return {
            "ok": False,
            "stage": "initialize",
            "error": f"no response within {timeout_s}s",
            "stderr_tail": stderr_tail,
            "duration_s": duration,
        }
    line = stdout_lines[0].strip()
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "stage": "parse",
            "error": f"non-JSON on stdout (ACP spec violation): {line[:200]}",
            "stderr_tail": stderr_tail,
            "duration_s": duration,
        }
    if msg.get("id") == 1 and isinstance(msg.get("result"), dict):
        result = msg["result"]
        methods = result.get("authMethods") or []
        return {
            "ok": True,
            "stage": "initialize",
            "agent": (result.get("agent") or {}).get("name"),
            "auth_methods": [
                {"id": m.get("id"), "type": m.get("type", "agent")}
                for m in methods
            ],
            "duration_s": duration,
        }
    if msg.get("id") == 1 and msg.get("error"):
        return {
            "ok": False,
            "stage": "initialize",
            "error": str(msg["error"]),
            "stderr_tail": stderr_tail,
            "duration_s": duration,
        }
    return {
        "ok": False,
        "stage": "initialize",
        "error": f"unexpected reply: {line[:200]}",
        "stderr_tail": stderr_tail,
        "duration_s": duration,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--entries", default="kilo,glm-acp-agent,minimax-code,qwen-code,codex-acp,claude-acp",
                    help="comma-separated ACP entry ids (default: fleet-relevant set)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "pmoves-acp-probe-cache")
    ap.add_argument("--auth-required", action="store_true",
                    help="adopt the upstream curation gate: PASS needs >=1 authMethod (agent|terminal)")
    ap.add_argument("--distribution", choices=["auto", "npx", "uvx", "binary"], default="auto",
                    help="force a distribution path when an entry carries several (kilo has npx+binary)")
    ap.add_argument("--no-preinstall", action="store_true",
                    help="skip the upstream-parity npm pre-install (keep cold npx semantics)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.registry.is_dir():
        print(f"error: registry not found at {args.registry} "
              "(clone POWERFULMOVES/PMOVES-registry as a repo sibling)", file=sys.stderr)
        return 2

    args.cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NPM_CONFIG_CACHE", str(args.cache / "npm"))

    plat = _platform_key()
    results: dict[str, dict] = {}
    failures = 0
    for entry_id in [e.strip() for e in args.entries.split(",") if e.strip()]:
        agent_json = args.registry / entry_id / "agent.json"
        if not agent_json.is_file():
            results[entry_id] = {"ok": False, "stage": "entry", "error": "no agent.json in registry"}
            failures += 1
            continue
        entry = json.loads(agent_json.read_text(encoding="utf-8"))
        try:
            argv, kind, extra_env = resolve_command(
                entry, args.cache, plat,
                prefer=args.distribution,
                preinstall_npx=not args.no_preinstall,
            )
        except ValueError as exc:
            results[entry_id] = {"ok": False, "stage": "resolve", "error": str(exc)}
            failures += 1
            continue
        outcome = probe(argv, args.timeout, extra_env)
        outcome["launcher"] = kind
        outcome["platform"] = plat
        if args.auth_required and outcome.get("ok") and not outcome.get("auth_methods"):
            outcome["ok"] = False
            outcome["error"] = "no authMethods in initialize result (upstream gate)"
        results[entry_id] = outcome
        if not outcome["ok"]:
            failures += 1

    if args.json:
        print(json.dumps({"platform": plat, "results": results}, indent=2))
    else:
        print(f"platform: {plat}")
        for eid, r in results.items():
            status = "PASS" if r["ok"] else "FAIL"
            bits = [r.get("agent") or "", f"auth={len(r.get('auth_methods', []))}"] if r["ok"] else [str(r.get("error", ""))]
            print(f"  {status}  {eid:16s} [{r.get('launcher', r.get('stage'))}] {' '.join(b for b in bits if b)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
