#!/usr/bin/env python3
"""CHIT Credential Lifecycle Demo Tool.

Demonstrates the full CHIT credential lifecycle:
  encode  — env file -> hex CGP + HMAC sign
  verify  — decode CGP back, verify HMAC, print round-trip diff
  rotate  — selective key update using --keys filter
  report  — scan directory for credential patterns, report redaction status
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pmoves.chit import encode_secret_map, decode_secret_map, load_cgp, save_cgp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env_file(path: Path, keys: set[str] | None = None) -> Dict[str, str]:
    """Load key=value pairs from an env file, optionally filtering by keys."""
    if not path.exists():
        raise FileNotFoundError(path)
    secrets: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if keys and key not in keys:
            continue
        secrets[key] = value
    return secrets


# Known credential patterns (prefix / regex fragments)
CREDENTIAL_PATTERNS = [
    (re.compile(r"(?:sk|pk)-lf-[0-9a-f]{8}"), "Langfuse API key"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"), "JWT token"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style secret key"),
    (re.compile(r"xoxb-[0-9]{10,}"), "Slack bot token"),
    (re.compile(r"hooks\.slack\.com/services/T[A-Z0-9]+"), "Slack webhook URL"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub PAT"),
    (re.compile(r"ghs_[A-Za-z0-9]{36}"), "GitHub App token"),
]


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_encode(args: argparse.Namespace) -> int:
    """Encode an env file into a hex CGP archive with optional HMAC signing."""
    env_path = Path(args.env_file)
    key_filter = set(args.keys) if args.keys else None
    secrets = load_env_file(env_path, key_filter)

    if not secrets:
        print(f"ERROR: No key=value pairs found in {env_path}", file=sys.stderr)
        return 1

    cgp = encode_secret_map(
        secrets,
        namespace=args.namespace,
        description=args.description or f"Encoded from {env_path.name}",
        include_cleartext=False,
    )

    # Optional HMAC signing
    if args.passphrase:
        from pmoves.tools.chit_security import sign_cgp
        cgp = sign_cgp(cgp, args.passphrase)
        print(f"HMAC-signed with kid={cgp['sig']['kid']}")

    out_path = Path(args.out)
    save_cgp(cgp, out_path)
    print(f"CGP written to {out_path} ({len(secrets)} keys, encoding=hex)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a CGP archive: decode, optionally verify HMAC, print contents."""
    cgp_path = Path(args.cgp)
    cgp = load_cgp(cgp_path)

    # HMAC verification
    if "sig" in cgp:
        if not args.passphrase:
            print("WARNING: CGP is signed but no --passphrase provided, skipping HMAC check",
                  file=sys.stderr)
        else:
            from pmoves.tools.chit_security import verify_cgp
            if verify_cgp(cgp, args.passphrase):
                print("HMAC verification: PASS")
            else:
                print("HMAC verification: FAIL", file=sys.stderr)
                return 1

    # Decode
    secrets = decode_secret_map(cgp)
    print(f"\nArchive: {cgp_path.name}")
    print(f"Version: {cgp.get('version', 'unknown')}")
    print(f"Namespace: {cgp.get('namespace', 'unknown')}")
    print(f"Description: {cgp.get('description', '')}")
    print(f"Points: {len(cgp.get('points', []))}")
    print(f"\nDecoded keys ({len(secrets)}):")
    for key in sorted(secrets):
        val = secrets[key]
        # Truncate long values
        display = val[:40] + "..." if len(val) > 40 else val
        print(f"  {key} = {display}")

    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    """Selective key rotation: update specific keys in an existing CGP archive."""
    cgp_path = Path(args.cgp)
    cgp = load_cgp(cgp_path)
    existing = decode_secret_map(cgp)

    if not args.keys:
        print("ERROR: --keys is required for rotate subcommand", file=sys.stderr)
        return 1

    env_path = Path(args.env_file) if args.env_file else None
    if env_path:
        new_values = load_env_file(env_path, set(args.keys))
    else:
        # Interactive: prompt for new values
        new_values = {}
        for key in args.keys:
            old = existing.get(key, "<not present>")
            old_display = old[:20] + "..." if len(old) > 20 else old
            val = input(f"  {key} (current: {old_display}): ")
            if val:
                new_values[key] = val

    if not new_values:
        print("No keys to update.")
        return 0

    # Merge
    existing.update(new_values)
    new_cgp = encode_secret_map(
        existing,
        namespace=cgp.get("namespace", "pmoves.secrets"),
        description=cgp.get("description", ""),
        include_cleartext=False,
    )

    save_cgp(new_cgp, cgp_path)
    print(f"Rotated {len(new_values)} keys in {cgp_path.name}: {', '.join(sorted(new_values))}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Scan a directory for credential patterns and report redaction status."""
    scan_path = Path(args.path)
    if not scan_path.exists():
        print(f"ERROR: Path does not exist: {scan_path}", file=sys.stderr)
        return 1

    # Collect files to scan
    extensions = {".env", ".md", ".yaml", ".yml", ".json", ".py", ".ts", ".js", ".txt"}
    files_to_scan: List[Path] = []
    if scan_path.is_file():
        files_to_scan.append(scan_path)
    else:
        for root, _dirs, filenames in os.walk(scan_path):
            # Skip common non-code directories
            root_path = Path(root)
            if any(part.startswith(".") or part in ("node_modules", "__pycache__", "venv", "env")
                   for part in root_path.parts):
                continue
            for fn in filenames:
                if Path(fn).suffix in extensions or fn.endswith(".env"):
                    files_to_scan.append(root_path / fn)

    findings: List[tuple[str, int, str, str]] = []
    redacted_count = 0
    clean_count = 0

    for fpath in sorted(files_to_scan):
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError):
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            for pattern, desc in CREDENTIAL_PATTERNS:
                if pattern.search(line):
                    rel = fpath.relative_to(scan_path) if fpath.is_relative_to(scan_path) else fpath
                    # Check if it's a redacted placeholder
                    if "ROTATED" in line or "CHANGE_ME" in line or "placeholder" in line.lower():
                        redacted_count += 1
                    else:
                        findings.append((str(rel), line_no, desc, line.strip()[:80]))

    # Check for CGP archives
    cgp_files: List[Path] = []
    if scan_path.is_dir():
        for cgp in scan_path.rglob("*.cgp.json"):
            cgp_files.append(cgp)

    # Report
    print(f"Credential Scan Report: {scan_path}")
    print(f"{'=' * 60}")
    print(f"Files scanned: {len(files_to_scan)}")
    print(f"CGP archives found: {len(cgp_files)}")
    for cgp_f in cgp_files:
        rel = cgp_f.relative_to(scan_path) if cgp_f.is_relative_to(scan_path) else cgp_f
        try:
            data = json.loads(cgp_f.read_text())
            pts = len(data.get("points", []))
            ns = data.get("namespace", "?")
            print(f"  {rel}: {pts} keys, namespace={ns}")
        except Exception:
            print(f"  {rel}: <invalid JSON>")

    print(f"Redacted references: {redacted_count}")

    if findings:
        print(f"\nPLAINTEXT CREDENTIALS FOUND: {len(findings)}")
        for rel_path, line_no, desc, snippet in findings:
            print(f"  {rel_path}:{line_no} [{desc}] {snippet}")
        return 1
    else:
        print(f"\nNo plaintext credentials found.")
        return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CHIT Credential Lifecycle Demo Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # encode
    p_enc = sub.add_parser("encode", help="Encode env file into hex CGP archive")
    p_enc.add_argument("--env-file", required=True, help="Path to env file")
    p_enc.add_argument("--out", required=True, help="Output CGP JSON path")
    p_enc.add_argument("--namespace", default="pmoves.secrets")
    p_enc.add_argument("--description", default=None)
    p_enc.add_argument("--keys", nargs="*", default=None, help="Subset of keys to encode")
    p_enc.add_argument("--passphrase", default=None, help="HMAC passphrase for signing")

    # verify
    p_ver = sub.add_parser("verify", help="Verify and decode a CGP archive")
    p_ver.add_argument("--cgp", required=True, help="Path to CGP JSON file")
    p_ver.add_argument("--passphrase", default=None, help="HMAC passphrase for verification")

    # rotate
    p_rot = sub.add_parser("rotate", help="Selective key rotation in CGP archive")
    p_rot.add_argument("--cgp", required=True, help="Path to CGP JSON file")
    p_rot.add_argument("--keys", nargs="+", required=True, help="Keys to rotate")
    p_rot.add_argument("--env-file", default=None, help="Source env file for new values")

    # report
    p_rep = sub.add_parser("report", help="Scan directory for credential patterns")
    p_rep.add_argument("--path", required=True, help="Directory or file to scan")

    args = parser.parse_args(argv)

    commands = {
        "encode": cmd_encode,
        "verify": cmd_verify,
        "rotate": cmd_rotate,
        "report": cmd_report,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
