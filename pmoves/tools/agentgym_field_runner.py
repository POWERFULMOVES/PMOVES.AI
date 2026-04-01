#!/usr/bin/env python3
"""AgentGym Field Runner — runs ReAct episodes against AgentGym environment servers.

Loads a hardware-specific YAML profile, health-checks environment servers,
and executes single episodes using a simple ReAct loop (observe -> think -> act).

CLI usage:
    python agentgym_field_runner.py --list-envs
    python agentgym_field_runner.py --run BabyAI --dry-run
    python agentgym_field_runner.py --run BabyAI
    python agentgym_field_runner.py --config field-runner-4090 --run TextCraft
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs" / "agentgym"


def _resolve_env_vars(value: str) -> str:
    """Expand ${VAR:-default} patterns in string values."""
    if not isinstance(value, str) or "${" not in value:
        return value
    import re

    def _sub(m: re.Match) -> str:
        var = m.group(1)
        default = m.group(2)
        return os.environ.get(var, default)

    return re.sub(r"\$\{(\w+):-([^}]*)\}", _sub, value)


def _walk_resolve(obj: Any) -> Any:
    """Recursively resolve env vars in a nested structure."""
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _walk_resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_resolve(v) for v in obj]
    return obj


def load_config(profile: str = "field-runner-4090") -> dict:
    """Load a YAML config by profile name.

    Searches ``pmoves/configs/agentgym/<profile>.yaml``.  Environment variable
    placeholders (``${VAR:-default}``) are expanded after loading.

    Returns:
        Parsed config dict.

    Raises:
        FileNotFoundError: If the profile YAML does not exist.
        ImportError: If PyYAML is not installed.
    """
    path = CONFIGS_DIR / f"{profile}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "PyYAML is required. Install with: uv pip install pyyaml"
        )
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _walk_resolve(raw)


# ---------------------------------------------------------------------------
# Environment listing
# ---------------------------------------------------------------------------


def list_environments(config: dict) -> list[dict]:
    """Return environments grouped by tier.

    Each entry is a dict with keys: ``name``, ``tier``, ``port`` (or ``None``),
    ``server_cmd`` (or ``None``), and ``reason`` (skip tier only).
    """
    envs: list[dict] = []
    env_section = config.get("environments", {})
    for tier, items in env_section.items():
        for item in items:
            entry: dict[str, Any] = {
                "name": item.get("name", "unknown"),
                "tier": tier,
                "port": item.get("port"),
                "server_cmd": item.get("server_cmd"),
                "reason": item.get("reason"),
            }
            envs.append(entry)
    return envs


def _find_env(config: dict, env_name: str) -> dict | None:
    """Look up a single environment entry by name (case-insensitive)."""
    for env in list_environments(config):
        if env["name"].lower() == env_name.lower():
            return env
    return None


# ---------------------------------------------------------------------------
# Health checking
# ---------------------------------------------------------------------------


def check_env_server(host: str, port: int, timeout: float = 3.0) -> bool:
    """Check whether an environment server is reachable via TCP.

    Args:
        host: Hostname or IP.
        port: TCP port number.
        timeout: Connection timeout in seconds.

    Returns:
        ``True`` if a TCP connection succeeds within *timeout*.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def _http_post(url: str, payload: dict, timeout: float = 30.0) -> dict:
    """POST JSON to *url* and return parsed JSON response."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL scheme (expected http/https): {url}")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — validated above
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Episode runner (ReAct loop)
# ---------------------------------------------------------------------------

_REACT_SYSTEM = (
    "You are an agent interacting with an environment. "
    "Given an observation, reason step-by-step (Thought), then output exactly "
    'one action string (Action). Respond in the format:\n'
    "Thought: <your reasoning>\nAction: <action string>"
)


def _parse_action(text: str) -> str:
    """Extract the action string from a ReAct-formatted LLM response."""
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("action:"):
            return stripped[len("action:"):].strip()
    # Fallback: return the last non-empty line
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "noop"


def _publish_nats(subject: str, payload: dict) -> bool:
    """Best-effort NATS publish. Silently skips if nats CLI unavailable."""
    import subprocess
    try:
        proc = subprocess.run(
            ["nats", "pub", subject, json.dumps(payload)],
            capture_output=True, text=True, timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_episode(
    env_name: str,
    config: dict,
    dry_run: bool = False,
) -> dict:
    """Run a single ReAct episode against an AgentGym environment server.

    In *dry_run* mode the function validates the config and checks server
    connectivity without actually running an episode.

    Args:
        env_name: Environment name (e.g. ``"BabyAI"``).
        config: Parsed field-runner config dict.
        dry_run: If ``True``, skip the actual episode loop.

    Returns:
        A result dict with keys: ``env``, ``dry_run``, ``success``, ``score``,
        ``rounds``, ``duration_sec``, ``history``, and ``error`` (if any).
    """
    env = _find_env(config, env_name)
    if env is None:
        return {
            "env": env_name,
            "dry_run": dry_run,
            "success": False,
            "score": 0.0,
            "rounds": 0,
            "duration_sec": 0.0,
            "history": [],
            "error": f"Environment '{env_name}' not found in config",
        }

    if env["tier"] == "skip":
        return {
            "env": env_name,
            "dry_run": dry_run,
            "success": False,
            "score": 0.0,
            "rounds": 0,
            "duration_sec": 0.0,
            "history": [],
            "error": f"Skipped: {env.get('reason', 'unsupported')}",
        }

    port = env["port"]
    host = "localhost"
    env_base = f"http://{host}:{port}"
    agent_cfg = config.get("agent", {})
    agent_mode = agent_cfg.get("mode", "api")
    if agent_mode == "local":
        # Local mode: use Ollama OpenAI-compatible endpoint
        agent_url = "http://localhost:11434/v1/chat/completions"
        model = agent_cfg.get("local_fallback", "qwen3:8b")
    else:
        # API mode: use TensorZero gateway
        agent_url = agent_cfg.get(
            "api_endpoint", "http://localhost:3030/v1/chat/completions"
        )
        model = agent_cfg.get("model", "qwen35_9b")
    max_rounds = config.get("episode", {}).get("max_rounds", 15)
    max_duration = config.get("episode", {}).get("max_duration_sec", 300)

    # --- Connectivity check ---
    env_alive = check_env_server(host, port)
    result: dict[str, Any] = {
        "env": env_name,
        "dry_run": dry_run,
        "success": False,
        "score": 0.0,
        "rounds": 0,
        "duration_sec": 0.0,
        "history": [],
        "error": None,
        "env_server_reachable": env_alive,
    }

    if dry_run:
        result["success"] = True
        if not env_alive:
            result["error"] = (
                f"Env server at {host}:{port} not reachable "
                "(expected in dry-run if server is not started)"
            )
            result["success"] = False
        print(
            f"[dry-run] env={env_name} port={port} "
            f"reachable={env_alive} model={model}"
        )
        return result

    if not env_alive:
        result["error"] = (
            f"Env server at {host}:{port} is not reachable. "
            f"Start it with: {env.get('server_cmd', 'unknown')}"
        )
        return result

    # --- Episode loop ---
    t0 = time.time()
    history: list[dict] = []
    messages: list[dict] = [{"role": "system", "content": _REACT_SYSTEM}]

    try:
        # 1. Create environment
        create_resp = _http_post(
            f"{env_base}/createEnv",
            {"env_name": env_name},
        )
        env_id = create_resp.get("env_id", create_resp.get("id", "default"))

        # 2. Get initial observation
        obs_resp = _http_post(
            f"{env_base}/observation",
            {"env_id": env_id},
        )
        observation = obs_resp.get("observation", obs_resp.get("obs", ""))
        done = obs_resp.get("done", False)

        for round_num in range(1, max_rounds + 1):
            elapsed = time.time() - t0
            if elapsed > max_duration:
                result["error"] = f"Timeout after {elapsed:.1f}s"
                break
            if done:
                break

            # 3. Send observation to agent API
            messages.append(
                {"role": "user", "content": f"Observation: {observation}"}
            )
            agent_resp = _http_post(
                agent_url,
                {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 512,
                },
            )
            assistant_text = (
                agent_resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            action = _parse_action(assistant_text)
            messages.append({"role": "assistant", "content": assistant_text})

            # 4. Execute action in environment
            step_resp = _http_post(
                f"{env_base}/step",
                {"env_id": env_id, "action": action},
            )
            observation = step_resp.get("observation", step_resp.get("obs", ""))
            reward = step_resp.get("reward", 0.0)
            done = step_resp.get("done", False)

            history.append(
                {
                    "round": round_num,
                    "observation": observation[:200],
                    "action": action,
                    "reward": reward,
                    "done": done,
                }
            )
            result["rounds"] = round_num

        # Compute final score from last reward or cumulative
        total_reward = sum(h.get("reward", 0.0) for h in history)
        result["score"] = total_reward
        result["success"] = done and total_reward > 0
        result["history"] = history

    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        result["error"] = str(exc)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        result["error"] = f"Unexpected response format: {exc}"

    result["duration_sec"] = round(time.time() - t0, 2)

    # Best-effort NATS publish for observability
    nats_cfg = config.get("nats", {})
    subject = nats_cfg.get("episode_completed", "agentgym.episode.completed.v1")
    _publish_nats(subject, {
        "env": env_name,
        "success": result["success"],
        "score": result["score"],
        "rounds": result["rounds"],
        "duration_sec": result["duration_sec"],
        "model": model,
        "node": config.get("hardware", {}).get("node", "unknown"),
    })
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_env_table(config: dict) -> None:
    """Print a formatted table of environments with tier and status."""
    envs = list_environments(config)
    if not envs:
        print("No environments configured.")
        return

    header = f"{'Name':<14} {'Tier':<14} {'Port':<8} {'Server Cmd':<24} {'Status'}"
    print(header)
    print("-" * len(header))
    for env in envs:
        port = env["port"]
        if env["tier"] == "skip":
            status = f"SKIP ({env.get('reason', '')})"
        elif port is not None:
            alive = check_env_server("localhost", port)
            status = "UP" if alive else "DOWN"
        else:
            status = "N/A"
        print(
            f"{env['name']:<14} {env['tier']:<14} "
            f"{str(port or '-'):<8} "
            f"{str(env.get('server_cmd') or '-'):<24} "
            f"{status}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AgentGym Field Runner — run ReAct episodes against env servers",
    )
    parser.add_argument(
        "--config",
        default="field-runner-4090",
        help="Config profile name (default: field-runner-4090)",
    )
    parser.add_argument(
        "--list-envs",
        action="store_true",
        help="List configured environments with status",
    )
    parser.add_argument(
        "--run",
        metavar="ENV_NAME",
        help="Run a single episode in the named environment",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and check connectivity without running an episode",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.list_envs:
        print(f"Profile: {config.get('id', args.config)}")
        print(
            f"Hardware: {config.get('hardware', {}).get('gpu', 'unknown')} "
            f"({config.get('hardware', {}).get('vram_gb', '?')} GB VRAM)"
        )
        print()
        _print_env_table(config)
        return 0

    if args.run:
        result = run_episode(args.run, config, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return 0 if result.get("success") else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
