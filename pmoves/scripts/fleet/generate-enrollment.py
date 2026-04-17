#!/usr/bin/env python3
"""
PMOVES Fleet Enrollment Generator

Generates time-limited, role-based enrollment payloads for RustDesk + Tailscale.
Enrollment tokens are CHIT-signed (HMAC-SHA256) and expire after TTL.

Usage:
    python generate-enrollment.py --role owner --ttl 5m --device "Pixel 10"
    python generate-enrollment.py --role partner --ttl 24h --device "Partner-Laptop-1"
    python generate-enrollment.py --role guest --ttl 1h
    python generate-enrollment.py --verify <token-json-file>
    python generate-enrollment.py --list  # show all unexpired tokens

Outputs:
    - QR code PNG (stdout path)
    - Enrollment JSON (stdout)
    - CLI paste command for manual config
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROLES = {
    "owner": {
        "description": "Full fleet access — all nodes, all ports",
        "tailscale_tags": ["tag:pmoves"],
        "allowed_nodes": "*",
    },
    "partner": {
        "description": "Partner access — GPU nodes, agent + inference ports only",
        "tailscale_tags": ["tag:partner"],
        "allowed_nodes": ["pmoves-5090", "pmoves-z890"],
        "allowed_ports": [3030, 8080, 8081],
    },
    "guest": {
        "description": "Guest demo access — single demo node only",
        "tailscale_tags": ["tag:guest"],
        "allowed_nodes": ["pmoves-z890"],
        "allowed_ports": [8081],
    },
}

TTL_MAP = {
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 3600,
    "4h": 4 * 3600,
    "24h": 24 * 3600,
}

# RustDesk server config (placeholders — real values injected at runtime)
RUSTDESK_HOST_ENV = "RUSTDESK_RELAY_HOST"
RUSTDESK_KEY_ENV = "RUSTDESK_PUBLIC_KEY"

# CHIT signing
CHIT_PASSPHRASE_ENV = "CHIT_PASSPHRASE"

# Output directory for QR codes (gitignored)
QR_OUTPUT_DIR = Path(__file__).parent.parent.parent / "docs" / "operations"

# Token ledger (gitignored, local only)
LEDGER_PATH = Path(__file__).parent / ".enrollment-ledger.jsonl"


# ---------------------------------------------------------------------------
# HMAC signing (inline, no dependency on pmoves.chit at script level)
# ---------------------------------------------------------------------------

import sys
from pathlib import Path
_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
if str(_TOOLS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR.parent))
from tools.chit_common import canon as _canon


def sign_enrollment(payload: dict[str, Any], passphrase: str) -> dict[str, Any]:
    """Sign an enrollment payload with HMAC-SHA256."""
    doc = json.loads(json.dumps(payload))
    kid = hashlib.sha256(passphrase.encode()).hexdigest()[:16]
    doc_nosig = json.loads(json.dumps(doc))
    doc_nosig.pop("sig", None)
    mac = hmac.new(
        passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256
    ).digest()
    doc["sig"] = {
        "alg": "HMAC-SHA256",
        "kid": kid,
        "hmac": base64.b64encode(mac).decode("ascii"),
    }
    return doc


def verify_enrollment(payload: dict[str, Any], passphrase: str) -> tuple[bool, str]:
    """Verify enrollment token signature and TTL. Returns (valid, reason)."""
    if "sig" not in payload:
        return False, "missing signature"

    # Check expiry first (fail-closed)
    expires_at = payload.get("expires_at", 0)
    if time.time() > expires_at:
        return False, f"expired at {datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()}"

    sig = payload["sig"]
    mac_b64 = sig.get("hmac", "")
    doc_nosig = json.loads(json.dumps(payload))
    doc_nosig.pop("sig", None)
    mac2 = hmac.new(
        passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256
    ).digest()
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return False, "invalid HMAC encoding"

    if not hmac.compare_digest(mac1, mac2):
        return False, "HMAC mismatch — token tampered or wrong passphrase"

    return True, "valid"


# ---------------------------------------------------------------------------
# QR Generation
# ---------------------------------------------------------------------------

def generate_qr(data: str, output_path: Path) -> Path:
    """Generate a QR code PNG. Requires `qrcode` and `pillow`."""
    try:
        import qrcode
    except ImportError:
        print("ERROR: qrcode package not installed. Run: uv pip install qrcode pillow", file=sys.stderr)
        sys.exit(1)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# Ledger (local audit trail for generated tokens)
# ---------------------------------------------------------------------------

def append_ledger(entry: dict[str, Any]) -> None:
    """Append enrollment event to local ledger (gitignored)."""
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def list_active_tokens() -> list[dict[str, Any]]:
    """List all unexpired enrollment tokens from ledger."""
    if not LEDGER_PATH.exists():
        return []
    now = time.time()
    active = []
    for line in LEDGER_PATH.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("expires_at", 0) > now:
            active.append(entry)
    return active


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(args: argparse.Namespace) -> None:
    role = args.role
    if role not in ROLES:
        print(f"ERROR: Unknown role '{role}'. Choose from: {', '.join(ROLES)}", file=sys.stderr)
        sys.exit(1)

    ttl_seconds = TTL_MAP.get(args.ttl)
    if ttl_seconds is None:
        print(f"ERROR: Unknown TTL '{args.ttl}'. Choose from: {', '.join(TTL_MAP)}", file=sys.stderr)
        sys.exit(1)

    # Load secrets from environment
    rustdesk_host = os.environ.get(RUSTDESK_HOST_ENV)
    rustdesk_key = os.environ.get(RUSTDESK_KEY_ENV)
    passphrase = os.environ.get(CHIT_PASSPHRASE_ENV)

    if not rustdesk_host or not rustdesk_key:
        print(
            f"ERROR: Set {RUSTDESK_HOST_ENV} and {RUSTDESK_KEY_ENV} environment variables.\n"
            f"These contain the RustDesk server IP and public key.",
            file=sys.stderr,
        )
        sys.exit(1)

    role_config = ROLES[role]
    now = time.time()
    expires_at = now + ttl_seconds

    # Build enrollment payload
    enrollment = {
        "version": "fleet.enrollment.v1",
        "token_id": secrets.token_urlsafe(16),
        "role": role,
        "device_name": args.device or f"enrollment-{role}-{int(now)}",
        "issued_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "expires_at": expires_at,
        "ttl_seconds": ttl_seconds,
        "issuer": "z890-claude",
        "rustdesk": {
            "host": rustdesk_host,
            "key": rustdesk_key,
            "api": "",
            "relay": rustdesk_host,
        },
        "access": {
            "tailscale_tags": role_config["tailscale_tags"],
            "allowed_nodes": role_config["allowed_nodes"],
            "allowed_ports": role_config.get("allowed_ports", "*"),
        },
    }

    # Sign with CHIT HMAC if passphrase available
    if passphrase:
        enrollment = sign_enrollment(enrollment, passphrase)
        print(f"Token signed with CHIT HMAC (kid: {enrollment['sig']['kid']})", file=sys.stderr)
    else:
        print("ERROR: CHIT_PASSPHRASE env var is required — refusing to issue unsigned tokens.", file=sys.stderr)
        sys.exit(1)

    # Generate RustDesk-only QR (for mobile app import)
    rustdesk_qr_data = json.dumps(enrollment["rustdesk"], separators=(",", ":"))

    # Generate QR code
    device_slug = (args.device or role).lower().replace(" ", "-")
    qr_filename = f"rustdesk-{device_slug}-qr.png"
    qr_path = QR_OUTPUT_DIR / qr_filename
    generate_qr(rustdesk_qr_data, qr_path)

    # Log to ledger
    ledger_entry = {
        "token_id": enrollment["token_id"],
        "role": role,
        "device_name": enrollment["device_name"],
        "issued_at": enrollment["issued_at"],
        "expires_at": expires_at,
        "signed": "sig" in enrollment,
    }
    append_ledger(ledger_entry)

    # Output
    expires_str = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"\n{'=' * 60}")
    print(f"  PMOVES Fleet Enrollment — {role.upper()}")
    print(f"{'=' * 60}")
    print(f"  Role:        {role} — {role_config['description']}")
    print(f"  Device:      {enrollment['device_name']}")
    print(f"  Token ID:    {enrollment['token_id']}")
    print(f"  Expires:     {expires_str} ({args.ttl})")
    print(f"  Signed:      {'YES (CHIT HMAC)' if 'sig' in enrollment else 'NO (unsigned)'}")
    print(f"  QR Code:     {qr_path}")
    print(f"{'=' * 60}")
    print(f"\n  RustDesk manual config:")
    print(f"    ID Server:    {rustdesk_host}")
    print(f"    Relay Server: {rustdesk_host}")
    print(f"    Key:          {rustdesk_key}")
    print(f"\n  RustDesk paste (for mobile Settings > Import):")
    print(f"    {rustdesk_qr_data}")
    if role_config["tailscale_tags"]:
        print(f"\n  Tailscale tags to assign: {', '.join(role_config['tailscale_tags'])}")
    if role_config.get("allowed_ports") and role_config["allowed_ports"] != "*":
        print(f"  Allowed ports: {role_config['allowed_ports']}")
    print(f"\n  Full enrollment token (save for verification):")
    print(f"  {json.dumps(enrollment, separators=(',', ':'))}")
    print()


def verify(args: argparse.Namespace) -> None:
    passphrase = os.environ.get(CHIT_PASSPHRASE_ENV)
    if not passphrase:
        print("ERROR: Set CHIT_PASSPHRASE to verify tokens.", file=sys.stderr)
        sys.exit(1)

    token_path = Path(args.verify)
    if token_path.exists():
        payload = json.loads(token_path.read_text())
    else:
        # Try parsing as inline JSON
        try:
            payload = json.loads(args.verify)
        except json.JSONDecodeError:
            print(f"ERROR: Cannot parse '{args.verify}' as JSON file or inline JSON.", file=sys.stderr)
            sys.exit(1)

    valid, reason = verify_enrollment(payload, passphrase)
    if valid:
        print(f"VALID — role={payload['role']}, device={payload.get('device_name', '?')}, "
              f"expires={datetime.fromtimestamp(payload['expires_at'], tz=timezone.utc).isoformat()}")
    else:
        print(f"INVALID — {reason}")
        sys.exit(1)


def list_tokens(_args: argparse.Namespace) -> None:
    active = list_active_tokens()
    if not active:
        print("No active enrollment tokens.")
        return
    print(f"{'Token ID':<24s} {'Role':<8s} {'Device':<20s} {'Expires':<24s} {'Signed'}")
    print("-" * 90)
    for t in active:
        exp = datetime.fromtimestamp(t["expires_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"{t['token_id']:<24s} {t['role']:<8s} {t['device_name']:<20s} {exp:<24s} {'YES' if t['signed'] else 'NO'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PMOVES Fleet Enrollment Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # generate
    gen = sub.add_parser("generate", aliases=["gen"], help="Generate enrollment token + QR")
    gen.add_argument("--role", required=True, choices=ROLES.keys(), help="Access role")
    gen.add_argument("--ttl", default="5m", choices=TTL_MAP.keys(), help="Token TTL (default: 5m)")
    gen.add_argument("--device", help="Device display name")

    # verify
    ver = sub.add_parser("verify", help="Verify an enrollment token")
    ver.add_argument("token", metavar="TOKEN", help="Token JSON file or inline JSON string")

    # list
    sub.add_parser("list", help="List active (unexpired) enrollment tokens")

    args = parser.parse_args()

    if args.command in ("generate", "gen"):
        generate(args)
    elif args.command == "verify":
        args.verify = args.token
        verify(args)
    elif args.command == "list":
        list_tokens(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
