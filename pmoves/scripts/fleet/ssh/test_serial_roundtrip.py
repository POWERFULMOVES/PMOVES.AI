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


def test_mint_serial_never_reuses_a_ledger_serial(tmp_path, monkeypatch):
    """Expired ledger rows still own their serial: their KRL entries persist.

    The previous scheme bucketed serials by the count of ACTIVE tokens, so a
    bucket was replayed once tokens expired.
    """
    gen = _load_gen()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps({"token_id": "old", "serial": 7, "expires_at": 1}) + "\n"
        + json.dumps({"token_id": "legacy-no-serial", "expires_at": 1}) + "\n"
    )
    monkeypatch.setattr(gen, "LEDGER_PATH", ledger)
    draws = iter([7, 0, 9])  # collision, then the invalid zero, then free
    monkeypatch.setattr(gen.secrets, "randbits", lambda bits: next(draws))
    assert gen.mint_serial() == 9


def test_torn_ledger_line_does_not_brick_minting(tmp_path, monkeypatch, capsys):
    """A crash mid-append leaves a partial last line. Minting continues, and
    a serial the fragment still names stays reserved."""
    gen = _load_gen()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps({"token_id": "ok", "serial": 7, "expires_at": 1}) + "\n"
        + '{"token_id": "torn", "serial": 11, "expi\n'
    )
    monkeypatch.setattr(gen, "LEDGER_PATH", ledger)
    assert gen.ledger_serials() == {7, 11}
    assert "ledger.jsonl:2 is not valid JSON" in capsys.readouterr().err
    draws = iter([11, 12])
    monkeypatch.setattr(gen.secrets, "randbits", lambda bits: next(draws))
    assert gen.mint_serial() == 12


def test_minted_serials_are_distinct_and_json_safe(tmp_path, monkeypatch):
    gen = _load_gen()
    monkeypatch.setattr(gen, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    serials = {gen.mint_serial() for _ in range(2000)}
    assert len(serials) == 2000
    assert all(0 < s < 2**53 for s in serials)


def test_full_width_serial_is_revocable(tmp_path):
    """A max-width serial survives cert issue -> KRL -> ssh-keygen -Q."""
    import time

    from ssh_surface import gen_krl, generate_ca, issue_cert

    serial = 2 ** _load_gen().SERIAL_BITS - 1
    ca_dir = tmp_path / "ca"
    generate_ca(ca_dir)
    key = tmp_path / "enrollee_ed25519"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-f", str(key), "-N", "", "-C", "w"],
        check=True, capture_output=True,
    )
    payload = {"role": "guest", "expires_at": time.time() + 600, "serial": serial}
    out = issue_cert(payload, ca_dir / "pmoves-fleet-ca_ed25519",
                     key.with_suffix(".pub").read_text())
    cert = tmp_path / "enrollee-cert.pub"
    cert.write_text(out["cert"] + "\n")
    krl = gen_krl([serial], tmp_path / "revoked.krl",
                  ca_dir / "pmoves-fleet-ca_ed25519.pub")
    # ssh-keygen -Q: 0 = not revoked, 1 = revoked, 255 = unreadable KRL
    check = subprocess.run(["ssh-keygen", "-Q", "-f", str(krl), str(cert)],
                           capture_output=True, text=True)
    assert check.returncode == 1, check.stdout + check.stderr
