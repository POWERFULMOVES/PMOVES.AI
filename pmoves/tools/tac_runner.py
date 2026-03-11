#!/usr/bin/env python3
"""TAC (Task-Action-Context) tree runner.

Loads a TAC tree YAML file, performs depth-first traversal, and checks
each node's action (file_exists, grep, command, manual). Outputs a JSON
summary suitable for agent consumption.

Usage:
    python pmoves/tools/tac_runner.py pmoves/configs/tac_trees/health-wger.tac.yaml
    python pmoves/tools/tac_runner.py --format text pmoves/configs/tac_trees/n8n.tac.yaml
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: uv pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Only these commands may be executed by TAC command nodes.
_ALLOWED_COMMANDS = frozenset({
    "curl",
    "docker",
    "git",
    "grep",
    "make",
    "nats",
    "python",
    "python3",
    "uv",
})


def _check_file_exists(target: str) -> tuple[str, str, bool]:
    """Returns (status, detail, is_error)."""
    path = REPO_ROOT / target
    if path.exists():
        return "pass", f"exists: {target}", False
    return "fail", f"missing: {target}", False


def _check_grep(target: str, pattern: str) -> tuple[str, str, bool]:
    """Returns (status, detail, is_error)."""
    path = REPO_ROOT / target
    if not path.exists():
        return "fail", f"target not found: {target}", True

    if path.is_dir():
        # Search all files in directory
        found = []
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    if re.search(pattern, text):
                        found.append(str(f.relative_to(REPO_ROOT)))
                except Exception:
                    continue
        if found:
            return "pass", f"pattern found in: {', '.join(found[:3])}", False
        return "fail", f"pattern '{pattern}' not found in {target}", False

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(pattern, text):
            return "pass", f"pattern found in {target}", False
        return "fail", f"pattern '{pattern}' not found in {target}", False
    except Exception as e:
        return "fail", f"error reading {target}: {e}", True


def _check_command(target: str) -> tuple[str, str, bool]:
    """Returns (status, detail, is_error).

    Uses shlex.split + shell=False to prevent shell injection.
    Only commands whose base name is in _ALLOWED_COMMANDS may run.
    """
    try:
        argv = shlex.split(target)
    except ValueError as e:
        return "fail", f"bad command syntax: {e}", True

    if not argv:
        return "fail", "empty command", True

    base = Path(argv[0]).name
    if base not in _ALLOWED_COMMANDS:
        return "fail", f"command not in allowlist: {base}", True

    try:
        result = subprocess.run(
            argv,
            shell=False,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return "pass", result.stdout.strip()[:200], False
        return "fail", result.stderr.strip()[:200], False
    except subprocess.TimeoutExpired:
        return "fail", "command timed out (30s)", True
    except Exception as e:
        return "fail", str(e), True


def evaluate_node(node: dict) -> dict:
    """Evaluate a single TAC node and return result."""
    result = {
        "id": node.get("id", "unknown"),
        "task": node.get("task", ""),
        "agent_hint": node.get("agent_hint", ""),
        "status": "pending",
        "detail": "",
        "children": [],
    }

    action = node.get("action")
    if action:
        action_type = action.get("type", "manual")
        target = action.get("target", "")
        pattern = action.get("pattern", "")

        if action_type == "file_exists":
            status, detail, is_error = _check_file_exists(target)
            result["status"] = status
            result["detail"] = detail
        elif action_type == "grep":
            status, detail, is_error = _check_grep(target, pattern)
            # Explicit invert field: when true, finding the pattern means FAIL.
            # Never invert on errors (missing file, permission denied, etc.)
            if action.get("invert", False) and not is_error:
                result["status"] = "fail" if status == "pass" else "pass"
            else:
                result["status"] = status
            result["detail"] = detail
        elif action_type == "command":
            status, detail, is_error = _check_command(target)
            result["status"] = status
            result["detail"] = detail
        elif action_type == "manual":
            result["status"] = "pending"
            result["detail"] = "requires manual review"

    # Recurse into children
    for child in node.get("children", []):
        result["children"].append(evaluate_node(child))

    # If no action but has children, derive status from children
    if not action and result["children"]:
        child_statuses = [c["status"] for c in result["children"]]
        if all(s == "pass" for s in child_statuses):
            result["status"] = "pass"
        elif any(s == "fail" for s in child_statuses):
            result["status"] = "fail"
        else:
            result["status"] = "pending"

    return result


def count_statuses(node: dict) -> dict[str, int]:
    """Count pass/fail/pending/skip across all nodes."""
    counts: dict[str, int] = {"pass": 0, "fail": 0, "pending": 0, "skip": 0}
    status = node.get("status", "pending")
    if node.get("action") or not node.get("children"):
        counts[status] = counts.get(status, 0) + 1
    for child in node.get("children", []):
        for k, v in count_statuses(child).items():
            counts[k] = counts.get(k, 0) + v
    return counts


def format_text(node: dict, indent: int = 0) -> str:
    """Format result as indented text for human reading."""
    icons = {"pass": "[PASS]", "fail": "[FAIL]", "pending": "[....]", "skip": "[SKIP]"}
    prefix = "  " * indent
    icon = icons.get(node["status"], "[????]")
    lines = [f"{prefix}{icon} {node['id']}: {node['task']}"]
    if node["detail"]:
        lines.append(f"{prefix}       {node['detail']}")
    for child in node.get("children", []):
        lines.append(format_text(child, indent + 1))
    return "\n".join(lines)


def _safe_print(text: str) -> None:
    """Print with fallback encoding for Windows consoles."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a TAC tree audit.")
    parser.add_argument("tree", type=Path, help="Path to TAC tree YAML file")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    if not args.tree.exists():
        print(f"TAC tree not found: {args.tree}", file=sys.stderr)
        return 1

    with open(args.tree, encoding="utf-8") as f:
        tree = yaml.safe_load(f)

    root = tree.get("root", {})
    result = evaluate_node(root)
    counts = count_statuses(result)

    if args.format == "json":
        output = {
            "tree": tree.get("name", "unknown"),
            "version": tree.get("version", "1.0.0"),
            "summary": counts,
            "results": result,
        }
        _safe_print(json.dumps(output, indent=2, ensure_ascii=True))
    else:
        _safe_print(f"TAC Tree: {tree.get('name', 'unknown')}")
        _safe_print("=" * 60)
        _safe_print(format_text(result))
        _safe_print("\n" + "=" * 60)
        _safe_print(
            f"Summary: {counts['pass']} pass, {counts['fail']} fail, "
            f"{counts['pending']} pending, {counts['skip']} skip"
        )

    return 1 if counts["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
