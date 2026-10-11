import json
import subprocess
import time
from pathlib import Path

import pytest

from ssh_surface import (
    MAX_CERT_TTL_SECONDS,
    ROLE_PRINCIPALS,
    SshSurfaceError,
    ca_paths,
    ca_trusted_line,
    gen_krl,
    generate_ca,
    issue_cert,
    wrap_bundle,
)


@pytest.fixture(scope="module")
def ca(tmp_path_factory):
    base = tmp_path_factory.mktemp("ca")
    info = generate_ca(base)
    paths = ca_paths(base)
    return info, paths["private"]


@pytest.fixture(scope="module")
def enrollee_pub(tmp_path_factory):
    d = tmp_path_factory.mktemp("enrollee")
    key = d / "test_user_ed25519"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-f", str(key), "-N", "",
         "-C", "test-enrollee"], check=True, capture_output=True,
    )
    return key.with_suffix(".pub").read_text().strip()


def test_ca_generated_once(ca):
    info, priv = ca
    assert priv.exists()
    assert info["fingerprint"].startswith("256 SHA256:")
    assert "pmoves-fleet-ssh-ca" in info["public"]


def test_principal_map_covers_roles():
    assert set(ROLE_PRINCIPALS) == {"owner", "partner", "guest"}


def test_issue_cert_ttl_never_exceeds_token(ca, enrollee_pub):
    _, priv = ca
    tok = {"role": "guest", "expires_at": time.time() + 600, "serial": 42}
    out = issue_cert(tok, priv, enrollee_pub)
    assert out["ttl_seconds"] <= 600
    assert out["principals"] == ["guest-demo"]
    assert out["serial"] == 42


def test_issue_cert_rejects_expired(ca, enrollee_pub):
    _, priv = ca
    tok = {"role": "guest", "expires_at": time.time() - 10, "serial": 43}
    with pytest.raises(SshSurfaceError):
        issue_cert(tok, priv, enrollee_pub)


def test_issue_cert_rejects_unknown_role(ca, enrollee_pub):
    _, priv = ca
    tok = {"role": "superuser", "expires_at": time.time() + 600, "serial": 44}
    with pytest.raises(SshSurfaceError):
        issue_cert(tok, priv, enrollee_pub)


def test_bundle_roundtrip(ca, enrollee_pub):
    _, priv = ca
    tok = {"role": "partner", "expires_at": time.time() + 3600,
           "serial": 77, "device": "test-laptop"}
    ssh_info = issue_cert(tok, priv, enrollee_pub)
    bundle = wrap_bundle(tok, ssh_info, "test-passphrase")
    assert "sig" in bundle
    assert bundle["ssh"]["serial"] == 77
    ok, reason = _gen_verify(bundle, "test-passphrase")
    assert ok, reason


def test_bundle_tamper_rejected(ca, enrollee_pub):
    _, priv = ca
    tok = {"role": "owner", "expires_at": time.time() + 3600, "serial": 78}
    ssh_info = issue_cert(tok, priv, enrollee_pub)
    bundle = wrap_bundle(tok, ssh_info, "test-passphrase")
    bundle["role"] = "guest"  # tamper
    ok, reason = _gen_verify(bundle, "test-passphrase")
    assert not ok


def test_krl_revokes_serial(ca, tmp_path):
    info, _ = ca
    capub = tmp_path / "ca.pub"
    capub.write_text(info["public"])
    krl = gen_krl([42, 77], tmp_path / "revoked.krl", capub)
    assert krl.exists() and krl.stat().st_size > 0


def test_ca_trusted_line_shape(ca):
    info, _ = ca
    line = ca_trusted_line(info["public"])
    assert line.startswith("ssh-ed25519 ")  # raw key, no @cert-authority prefix


def _gen_verify(payload, passphrase):
    import importlib.util
    from pathlib import Path as P
    spec = importlib.util.spec_from_file_location(
        "pmoves_generate_enrollment",
        P(__file__).parent.parent / "generate-enrollment.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.verify_enrollment(payload, passphrase)
