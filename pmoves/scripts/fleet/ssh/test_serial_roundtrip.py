"""CRITICAL regression: cert serials must come from the REAL generate() path.

Bot finding (2026-10-11): issue_cert refused 100% of real tokens because
generate-enrollment.py never minted a serial — and the tests passed because
they hand-crafted dicts with serial=42. These tests drive the module's real
generate() flow (QR generation stubbed — the serial contract is the target).
"""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_MODULE_DIR = Path(__file__).resolve().parent
_SCRIPT = _MODULE_DIR.parent / "generate-enrollment.py"


def _load_gen():
    spec = importlib.util.spec_from_file_location(
        "pmoves_generate_enrollment", _SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _generate_token(tmp_path, monkeypatch, role="guest", device="roundtrip-test"):
    """Drive the module's real generate() with isolated ledger + stubbed QR."""
    gen = _load_gen()
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(gen, "LEDGER_PATH", ledger)
    monkeypatch.setattr(
        gen, "generate_qr", lambda data, path: path
    )  # stub: no qrcode dependency in unit tests
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-passphrase-roundtrip")
    monkeypatch.setenv("RUSTDESK_RELAY_HOST", "dummy-relay.example")
    monkeypatch.setenv("RUSTDESK_PUBLIC_KEY", "dummy-public-key")
    args = argparse.Namespace(role=role, ttl="15m", device=device)
    gen.generate(args)
    assert ledger.exists(), "no ledger written by generate()"
    entry = json.loads(ledger.read_text().strip().split("\n")[-1])
    return entry


def test_ledger_entry_carries_serial(tmp_path, monkeypatch):
    entry = _generate_token(tmp_path, monkeypatch, role="guest")
    assert "serial" in entry, "ledger entry missing serial — issue_cert refuses real tokens"
    assert entry["serial"] > 0


def test_issue_cert_accepts_real_serial(tmp_path, monkeypatch):
    """End-to-end: real generate() serial -> issue_cert succeeds (the exact gap)."""
    from ssh_surface import issue_cert, generate_ca

    entry = _generate_token(tmp_path, monkeypatch, role="partner", device="e2e-cert-test")
    payload = {
        "role": entry["role"],
        "expires_at": entry["expires_at"],
        "serial": entry["serial"],
        "device_name": entry["device_name"],
    }
    ca_dir = tmp_path / "ca"
    ca_info = generate_ca(ca_dir)
    key = tmp_path / "enrollee_ed25519"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-f", str(key), "-N", "", "-C", "e2e"],
        check=True, capture_output=True,
    )
    pubkey = key.with_suffix(".pub").read_text().strip()
    out = issue_cert(payload, ca_dir / "pmoves-fleet-ca_ed25519", pubkey)
    assert out["serial"] == entry["serial"]
    assert "-cert-" in out["cert"]
