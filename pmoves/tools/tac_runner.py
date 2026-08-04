#!/usr/bin/env python3
"""TAC (Task-Action-Context) tree runner.

Loads a TAC tree YAML file, performs depth-first traversal, and checks
each node's action (file_exists, grep, command, http, manual). Outputs a JSON
summary suitable for agent consumption.

Usage:
    python pmoves/tools/tac_runner.py pmoves/configs/tac_trees/health-wger.tac.yaml
    python pmoves/tools/tac_runner.py --format text pmoves/configs/tac_trees/n8n.tac.yaml
"""

import argparse
import json
import re
import ipaddress
import shlex
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
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


def _check_grep(target: str, pattern: str, multiline: bool = False) -> tuple[str, str, bool]:
    """Returns (status, detail, is_error).

    `multiline` is OPT-IN and enables re.DOTALL so `.` spans newlines.

    It is not the default, and must not become the default. Assertions like
    `channel-monitor.*healthcheck` read as "this service has a healthcheck", but
    under DOTALL over a whole compose file they mean "the string channel-monitor
    appears somewhere, and healthcheck appears somewhere after it" — which
    matches when the healthcheck belongs to an entirely different service 400
    lines away. Enabling it globally would convert the current false negatives
    into false positives, which is strictly worse for a gate: a wrong PASS is
    invisible, a wrong FAIL is at least loud.

    So authors opt in per assertion and accept the scoping weakness. For
    structural questions about YAML ("does service X define a healthcheck") a
    regex over raw text is the wrong instrument regardless of flags; that wants
    a parsed-YAML action type, which is not implemented here.
    """
    flags = re.DOTALL if multiline else 0
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
                    if re.search(pattern, text, flags):
                        found.append(str(f.relative_to(REPO_ROOT)))
                except Exception:
                    continue
        if found:
            return "pass", f"pattern found in: {', '.join(found[:3])}", False
        return "fail", f"pattern '{pattern}' not found in {target}", False

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(pattern, text, flags):
            return "pass", f"pattern found in {target}", False
        return "fail", f"pattern '{pattern}' not found in {target}", False
    except Exception as e:
        return "fail", f"error reading {target}: {e}", True


# Keys that change the request this probe would send, or assert on content it
# never reads. Declaring any of them makes the node unsupported (see the http
# branch in evaluate_node) rather than silently probed a different way.
#
# `expect` is deliberately NOT here: it is free-form prose present on the
# existing 38 nodes ("200 OK", "Prometheus metrics for ..."), documentation
# rather than a machine-readable predicate. Listing it would fail-close every
# node this PR set out to wire up. The numeric assertion is `expect_status`,
# which IS honoured.
_HTTP_UNSUPPORTED_KEYS = (
    # request shape
    "method",
    "headers",
    "body",
    "json",
    "data",
    "auth",
    # content predicates
    "expect_body",
    "expect_json",
    "expect_contains",
    "expect_match",
    "expect_jsonpath",
    "assert",
)


def _check_http(url: str, expect_status: int = 200, timeout: int = 10) -> tuple[str, str, bool]:
    """Returns (status, detail, is_error).

    38 nodes across the trees already declare `type: http` with an `url` — they
    were the single largest block of assertions that silently asserted nothing.
    They are liveness probes of local services, and one of them
    (node-5090-powerfulmoves.tac.yaml, localhost:8077/healthz) is precisely the
    check that would have surfaced the yt-dlp extraction outage.

    Constraints:
      * http/https only, so a tree cannot be used to read file:// off the runner
      * link-local blocked — see _http_host_allowed (cloud metadata / IMDS)
      * no redirect following, so a permitted host cannot bounce the request to
        a blocked one
      * connection failure is a FAIL, not an error — "the service is down" is a
        real assertion result, which is the whole point of a liveness probe
      * GET only, and the response body is never read; these are liveness probes
        and nothing here should be able to pull data into the report
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "fail", f"unsupported scheme '{parsed.scheme}' (http/https only)", True
    if not _http_host_allowed(parsed.hostname or ""):
        return (
            "fail",
            f"host '{parsed.hostname}' not allowed — TAC http probes are limited to "
            f"loopback, private ranges and the tailnet",
            True,
        )
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "pmoves-tac-runner"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        return "fail", f"{url}: {type(e).__name__}: {e}", False
    if code == expect_status:
        return "pass", f"{url} -> {code}", False
    return "fail", f"{url} -> {code} (expected {expect_status})", False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: an allowed host must not be able to bounce us elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _addr_blocked(ip: ipaddress._BaseAddress) -> bool:
    """True if this resolved address must not be probed.

    Link-local only — see _http_host_allowed for why the block is deliberately
    this narrow. IPv4-mapped IPv6 (::ffff:169.254.169.254) is unwrapped first:
    IPv6Address.is_link_local tests fe80::/10, so a mapped v4 link-local address
    answers False and would otherwise sail straight through.
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_link_local


def _numeric_host_to_ip(host: str) -> ipaddress.IPv4Address | None:
    """Parse inet_aton-style numeric hosts that `ipaddress` rejects but libc accepts.

    169.254.169.254 is also spelled 2852039166 (decimal) and 0xa9fea9fe (hex).
    `ipaddress.ip_address` raises ValueError on both, so treating a parse failure
    as "must be a hostname" hands IMDS straight to the caller. glibc's resolver
    accepts these forms, so on Linux — where this runner actually executes — they
    resolve and connect. Parse them here so the block does not depend on whether
    the local resolver happens to expand them.
    """
    for base in (10, 16, 8):
        try:
            value = int(host, base)
        except ValueError:
            continue
        if 0 <= value <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(value)
    return None


def _resolve_all(host: str) -> list[ipaddress._BaseAddress]:
    """Every address `host` resolves to. Empty list if resolution fails."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    out: list[ipaddress._BaseAddress] = []
    for info in infos:
        try:
            out.append(ipaddress.ip_address(info[4][0]))
        except (ValueError, IndexError):
            continue
    return out


def _http_host_allowed(host: str) -> bool:
    """Block link-local; allow everything else.

    The one hard rule is link-local (169.254.0.0/16), which contains
    169.254.169.254 — the cloud instance-metadata endpoint and the canonical SSRF
    target for stealing instance credentials. A TAC tree is YAML an agent is told
    to run, so a careless or hostile tree must not be able to reach IMDS from a
    runner. No fleet probe legitimately needs link-local.

    Everything else is permitted, and that is deliberate rather than lax. An
    earlier draft restricted probes to loopback/RFC1918/bare names; checked
    against the 38 real http nodes it would have broken legitimate targets —
    `headscale.pmoves.ai` (public DNS, own infrastructure), `7860.localhost`
    (a loopback subdomain), and the `*.ts` tailnet shorthands. Probing internal
    services across the mesh is the entire purpose of these nodes, so a
    private-only allowlist fights the feature. Trees are repo-controlled and
    PR-reviewed, which is a materially different threat model from user input.

    The block must hold for every *spelling* of a blocked address, not just the
    canonical one. An earlier version of this function checked only the dotted
    quad, so `2852039166`, `0xa9fea9fe` and `::ffff:169.254.169.254` all reached
    IMDS. Three layers now: numeric literal, IP literal, then resolution — and a
    hostname is rejected if ANY address it resolves to is blocked.

    Known limitation: resolution here and connection in urllib are two separate
    lookups, so a DNS-rebinding responder could answer differently for each.
    Closing that needs connecting to a pinned address, which urllib does not
    expose; it is out of scope while trees are repo-controlled and PR-reviewed.
    """
    if not host:
        return False
    host = host.strip("[]").casefold()

    numeric = _numeric_host_to_ip(host)
    if numeric is not None:
        return not _addr_blocked(numeric)

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return not _addr_blocked(literal)

    # A hostname. Reject if any address it maps to is blocked. Resolution
    # failure yields an empty list and is allowed through — the probe itself
    # then fails to connect, which is a truthful FAIL rather than a fake block.
    return not any(_addr_blocked(ip) for ip in _resolve_all(host))


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
            status, detail, is_error = _check_grep(
                target, pattern, multiline=bool(action.get("multiline", False))
            )
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
        elif action_type == "http":
            # http nodes carry the endpoint in `url`, not `target` — that key
            # mismatch is part of why they were never wired up.
            # Trees use BOTH conventions: 16 nodes carry the endpoint in `url`,
            # 22 in `target`. Accept either. Note `expect` is free-form prose
            # ("200 OK", "Prometheus metrics for ...") and is NOT a status code —
            # the numeric override is the separate `expect_status` key.
            #
            # FAIL CLOSED on anything this probe cannot actually perform. The
            # probe sends an unauthenticated GET and reads only the status code,
            # so a node declaring a method/body/headers or a content assertion
            # would have its request quietly replaced by a different one and
            # then be reported PASS on the strength of the status alone:
            #   * pinokio-p8.tac.yaml   POSTs a body to assert 401/503 on an
            #     unauthenticated write, and separately requires `cycles: []`
            #   * voice-agents.tac.yaml POSTs a synthesis request
            #   * public-tunnel.tac.yaml sends auth headers and requires a
            #     recent reconciliation timestamp
            # Green on an assertion that was never evaluated is precisely the
            # fail-open this runner exists to remove, so refuse the node instead.
            unsupported = [k for k in _HTTP_UNSUPPORTED_KEYS if action.get(k)]
            if unsupported:
                result["status"] = "fail"
                result["detail"] = (
                    f"http probe cannot honour {sorted(unsupported)} — it sends an "
                    f"unauthenticated GET and asserts on the status code only. "
                    f"Node is unsupported rather than passing; implement these "
                    f"fields or convert the node to `command`."
                )
            else:
                status, detail, is_error = _check_http(
                    action.get("url") or action.get("target") or "",
                    int(action.get("expect_status", 200) or 200),
                )
                result["status"] = status
                result["detail"] = detail
        elif action_type == "manual":
            result["status"] = "pending"
            result["detail"] = "requires manual review"
        else:
            # Unknown action type — was silently staying at "pending" with no
            # detail, hiding every mis-typed / mis-named / future action in the
            # same bucket as legitimate "manual" review items. Surface as FAIL
            # so the operator sees the gap and can either (a) add the new type
            # to this runner or (b) correct the YAML. This is what made the
            # 141 inert assertions invisible — they counted as pending and
            # the operator trusted the pending count.
            result["status"] = "fail"
            result["detail"] = (
                f"unknown action.type: '{action_type}' "
                f"(allowed: file_exists, grep, command, http, manual)"
            )

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
