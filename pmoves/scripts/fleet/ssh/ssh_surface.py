#!/usr/bin/env python3
"""SSH certificate surface for PMOVES fleet enrollment (CHIT-bundle wrapped).

Design (AGNOTE4482PHI.t1.md CLAIM feat/enrollment-ssh-surface 2026-10-11):
- One fleet SSH CA (ed25519). Private key NEVER committed: generated on first
  use, gitignored, delivered to nodes via the secrets funnel only.
- Short-TTL SSH certificates issued per enrollment; cert validity never
  exceeds the enrollment token TTL. Principals derive from the existing ROLES
  table (no new role taxonomy).
- Issued cert + CA fingerprint are wrapped into the existing CHIT-signed
  enrollment bundle (HMAC-SHA256 via generate-enrollment's sign_enrollment).
- Revocation = KRL driven by the enrollment ledger serials; the node-side
  installer drops TrustedUserCAKeys + RevokedKeys into sshd_config.d.

All ssh-keygen subprocess calls are isolated in generate_ca/issue_cert/gen_krl
so bundle logic is testable without spawning processes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import time
from pathlib import Path
from typing import Any

_MODULE_DIR = Path(__file__).resolve().parent
_SPECS = importlib.util.spec_from_file_location(
    "pmoves_generate_enrollment",
    _MODULE_DIR.parent / "generate-enrollment.py",
)
_gen = importlib.util.module_from_spec(_SPECS)
_SPECS.loader.exec_module(_gen)

CA_KEY_NAME = "pmoves-fleet-ca_ed25519"

# ROLES -> ssh principals, so sshd Match blocks can restrict shells per role.
ROLE_PRINCIPALS = {
    "owner": ["owner", "fleet-admin"],
    "partner": ["partner"],
    "guest": ["guest-demo"],
}

# Hard ceiling: no cert outlives its token by even a second.
MAX_CERT_TTL_SECONDS = 24 * 3600


class SshSurfaceError(RuntimeError):
    pass


def ca_paths(base_dir: Path) -> dict[str, Path]:
    return {
        "private": base_dir / CA_KEY_NAME,
        "public": base_dir / (CA_KEY_NAME + ".pub"),
    }


def generate_ca(base_dir: Path) -> dict[str, str]:
    """Generate the fleet CA keypair if absent. Returns fingerprint + pubkey.

    Private key is written 0600 and must be treated as a funnel secret.
    Never print or log private key material.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    paths = ca_paths(base_dir)
    if not paths["public"].exists():
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-f", str(paths["private"]),
             "-N", "", "-C", "pmoves-fleet-ssh-ca"],
            check=True, capture_output=True,
        )
        paths["private"].chmod(0o600)
    fp = subprocess.run(
        ["ssh-keygen", "-lf", str(paths["public"])],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {"fingerprint": fp, "public": paths["public"].read_text().strip()}


def issue_cert(
    token_payload: dict[str, Any],
    ca_key_path: Path,
    pubkey_text: str,
) -> dict[str, Any]:
    """Issue a short-TTL user cert for the enrollee's OpenSSH public key.

    pubkey_text: one-line OpenSSH public key material.
    Validity = min(token remaining validity, MAX_CERT_TTL_SECONDS).
    Serial aligns with the enrollment ledger for KRL revocation.
    """
    role = token_payload.get("role")
    if role not in ROLE_PRINCIPALS:
        raise SshSurfaceError(f"unknown role: {role}")
    expires_at = float(token_payload.get("expires_at", 0))
    remaining = expires_at - time.time()
    if remaining <= 0:
        raise SshSurfaceError("token already expired - refusing to issue cert")
    ttl = int(min(remaining, MAX_CERT_TTL_SECONDS))
    serial = int(token_payload.get("serial", 0))
    if serial <= 0:
        raise SshSurfaceError("token serial missing - KRL revocation requires serials")
    principals = ROLE_PRINCIPALS[role]

    import tempfile
    tmpdir = Path(tempfile.mkdtemp(prefix="pmoves-enroll-"))
    tmp_pub = tmpdir / "enrollee.pub"
    tmp_pub.write_text(pubkey_text.strip() + "\n")
    out = tmpdir / "enrollee-cert.pub"
    try:
        subprocess.run(
            ["ssh-keygen", "-q", "-s", str(ca_key_path),
             "-I", f"pmoves-{role}-{serial}",
             "-n", ",".join(principals),
             "-V", f"+{ttl}s",
             "-z", str(serial),
             str(tmp_pub)],
            check=True, capture_output=True,
        )
        cert_pub = out.read_text().strip()
    finally:
        tmp_pub.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        tmpdir.rmdir()
    return {
        "cert": cert_pub,
        "principals": principals,
        "serial": serial,
        "ttl_seconds": ttl,
    }


def wrap_bundle(
    base_payload: dict[str, Any],
    ssh_info: dict[str, Any],
    passphrase: str,
) -> dict[str, Any]:
    """Wrap ssh surface info into the CHIT-signed enrollment bundle."""
    doc = json.loads(json.dumps(base_payload))
    doc["ssh"] = {
        "cert": ssh_info["cert"],
        "principals": ssh_info["principals"],
        "serial": ssh_info["serial"],
        "ttl_seconds": ssh_info["ttl_seconds"],
    }
    return _gen.sign_enrollment(doc, passphrase)


def gen_krl(serials: list[int], out_path: Path, ca_pub_path: Path) -> Path:
    """Generate a KRL revoking cert serials, scoped to the fleet CA pubkey."""
    if not serials:
        raise SshSurfaceError("refusing to generate empty KRL")
    tmp = out_path.with_suffix(".serials.tmp")
    tmp.write_text("\n".join(f"serial: {s}" for s in serials) + "\n")
    try:
        subprocess.run(
            ["ssh-keygen", "-q", "-k", "-f", str(out_path), "-s", str(ca_pub_path), str(tmp)],
            check=True, capture_output=True,
        )
    finally:
        tmp.unlink(missing_ok=True)
    return out_path


def ca_trusted_line(ca_public: str) -> str:
    """Return the raw CA public key line for TrustedUserCAKeys.

    TrustedUserCAKeys takes plain CA public keys (one per line), NOT the
    @cert-authority format (that is for authorized_keys host-cert trust).
    """
    return ca_public.strip()
