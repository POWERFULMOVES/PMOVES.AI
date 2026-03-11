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
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: uv pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Shell metacharacters disallowed in command targets to prevent injection
_DISALLOWED_SHELL_CHARS = {";", "|", "&&", "||", "`", "$("}


def _check_file_exists(target: str) -> tuple[str, str]:
    path = REPO_ROOT / target
    if path.exists():
        return "pass", f"exists: {target}"
    return "fail", f"missing: {target}"


def _check_grep(target: str, pattern: str) -> tuple[str, str]:
    path = REPO_ROOT / target
    if not path.exists():
        return "fail", f"target not found: {target}"

    # Validate regex before use
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return "fail", f"invalid regex pattern '{pattern}': {e}"

    if path.is_dir():
        found = []
        skipped = []
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    if compiled.search(text):
                        found.append(str(f.relative_to(REPO_ROOT)))
                except PermissionError:
                    skipped.append(str(f.relative_to(REPO_ROOT)))
                except OSError as e:
                    skipped.append(f"{f.relative_to(REPO_ROOT)}: {e}")
        detail_suffix = ""
        if skipped:
            detail_suffix = f" (skipped {len(skipped)} files: {', '.join(skipped[:3])})"
        if found:
            return "pass", f"pattern found in: {', '.join(found[:3])}{detail_suffix}"
        return "fail", f"pattern '{pattern}' not found in {target}{detail_suffix}"

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if compiled.search(text):
            return "pass", f"pattern found in {target}"
        return "fail", f"pattern '{pattern}' not found in {target}"
    except PermissionError:
        return "fail", f"permission denied: {target}"
    except OSError as e:
        return "fail", f"error reading {target}: {e}"


def _check_command(target: str) -> tuple[str, str]:
    # Validate against shell injection
    for char in _DISALLOWED_SHELL_CHARS:
        if char in target:
            return "fail", f"command contains disallowed shell metacharacter: {char}"

    try:
        result = subprocess.run(
            target,
            shell=True,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return "pass", result.stdout.strip()[:200]
        return "fail", result.stderr.strip()[:200]
    except subprocess.TimeoutExpired:
        return "fail", "command timed out (30s)"
    except OSError as e:
        return "fail", str(e)


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
        if not isinstance(action, dict):
            result["status"] = "fail"
            result["detail"] = f"action must be a dict, got {type(action).__name__}"
        else:
            action_type = action.get("type", "manual")
            target = action.get("target", "")
            pattern = action.get("pattern", "")

            if action_type == "file_exists":
                result["status"], result["detail"] = _check_file_exists(target)
            elif action_type == "grep":
                status, detail = _check_grep(target, pattern)
                # Explicit invert field for negative grep checks
                if action.get("invert", False):
                    result["status"] = "fail" if status == "pass" else "pass"
                else:
                    result["status"] = status
                result["detail"] = detail
            elif action_type == "command":
                result["status"], result["detail"] = _check_command(target)
            elif action_type == "manual":
                result["status"] = "pending"
                result["detail"] = "requires manual review"
            else:
                result["status"] = "fail"
                result["detail"] = f"unknown action type: {action_type}"

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
    """Count pass/fail/pending across all leaf nodes."""
    counts: dict[str, int] = {"pass": 0, "fail": 0, "pending": 0}
    status = node.get("status", "pending")
    if node.get("action") or not node.get("children"):
        counts[status] = counts.get(status, 0) + 1
    for child in node.get("children", []):
        for k, v in count_statuses(child).items():
            counts[k] = counts.get(k, 0) + v
    return counts


def format_text(node: dict, indent: int = 0) -> str:
    """Format result as indented text for human reading."""
    icons = {"pass": "[PASS]", "fail": "[FAIL]", "pending": "[....]"}
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

    if not isinstance(tree, dict) or "root" not in tree:
        print(f"Invalid TAC tree: must be a YAML dict with 'root' key", file=sys.stderr)
        return 1

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
            f"{counts['pending']} pending"
        )

    return 1 if counts["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
