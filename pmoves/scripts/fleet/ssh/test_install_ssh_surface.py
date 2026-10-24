"""install_ssh_surface.sh: validate-before-write, effective-config check, rollback.

Runs the real installer against a scratch PMOVES_SSH_ETC tree with stub
`sshd` / `systemctl` on PATH. The stub `sshd -T` emulates the two ways a
drop-in can be silently ignored: sshd_config without an Include for
sshd_config.d (STUB_SSHD_INCLUDES=0), and `sshd -t` failing (STUB_SSHD_T_RC).
"""
import os
import subprocess
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import find_bash  # noqa: E402  never the WSL stub

from ssh_surface import gen_krl, generate_ca

_INSTALLER = Path(__file__).resolve().parent / "install_ssh_surface.sh"
_BASH = find_bash()

# On Windows this suite runs under Git Bash (or any non-WSL bash) and passes
# there -- Z890 measured 6/6. The hazard is the WSL stub `shutil.which("bash")`
# returns, which would run a different OS against a different filesystem view
# (/mnt/d vs D:). `find_bash()` rejects that stub and returns None when no
# POSIX bash exists, so a single skip on `_BASH is None` covers every host.
# pytest reads only the module attribute named `pytestmark`; an earlier
# `pytestmark_win32` here was never applied (review of #3359).
pytestmark = pytest.mark.skipif(
    _BASH is None,
    reason=(
        "install_ssh_surface.sh needs a POSIX bash (Git for Windows or a POSIX "
        "host); find_bash() found none and refuses the WSL stub."
    ),
)

_STUB_SSHD = """#!/usr/bin/env bash
mode=""; cfg=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|-T) mode="$1"; shift ;;
    -f) cfg="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ "$mode" == "-t" ]]; then exit "${STUB_SSHD_T_RC:-0}"; fi
seen=""
if [[ "${STUB_SSHD_INCLUDES:-1}" == 1 ]]; then
  for f in "$(dirname "$cfg")"/sshd_config.d/*.conf; do
    [[ -e "$f" ]] || continue
    while read -r k v; do
      k="$(tr '[:upper:]' '[:lower:]' <<<"$k")"; echo "$k $v"; seen="$seen $k"
    done < "$f"
  done
fi
[[ "$seen" == *trustedusercakeys* ]] || echo "trustedusercakeys none"
[[ "$seen" == *revokedkeys* ]] || echo "revokedkeys none"
"""

_STUB_SYSTEMCTL = """#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB_RESTART_LOG"
exit "${STUB_RESTART_RC:-0}"
"""

# Shadows the host's real `service` so the installer's last fallback can
# never touch the runner's own sshd.
_STUB_SERVICE = """#!/usr/bin/env bash
echo "service $*" >> "$STUB_RESTART_LOG"
exit "${STUB_RESTART_RC:-0}"
"""


@pytest.fixture()
def env(tmp_path):
    etc = tmp_path / "etc-ssh"
    etc.mkdir()
    (etc / "sshd_config").write_text("Include sshd_config.d/*.conf\n")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in (("sshd", _STUB_SSHD), ("systemctl", _STUB_SYSTEMCTL),
                       ("service", _STUB_SERVICE)):
        p = stubs / name
        p.write_text(body, newline="\n")
        p.chmod(0o755)
    ca_dir = tmp_path / "ca"
    generate_ca(ca_dir)
    krl = gen_krl([101, 202], tmp_path / "revoked.krl",
                  ca_dir / "pmoves-fleet-ca_ed25519.pub")
    restart_log = tmp_path / "restarts.log"
    return {
        "tmp": tmp_path,
        "etc": etc,
        "ca_pub": ca_dir / "pmoves-fleet-ca_ed25519.pub",
        "krl": krl,
        "restart_log": restart_log,
        "env": {
            **os.environ,
            "PATH": str(stubs) + os.pathsep + os.environ.get("PATH", ""),
            "PMOVES_SSH_ETC": etc.as_posix(),
            "STUB_RESTART_LOG": restart_log.as_posix(),
        },
    }


def _run(env, *args, **overrides):
    return subprocess.run(
        [_BASH, _INSTALLER.as_posix(), *[str(a) for a in args]],
        env={**env["env"], **overrides},
        capture_output=True, text=True,
    )


def _state(etc: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(etc)): p.read_bytes()
        for p in sorted(etc.rglob("*")) if p.is_file()
    }


def _conf(env) -> str:
    return (env["etc"] / "sshd_config.d" / "90-pmoves-fleet-ca.conf").read_text()


def test_installs_ca_and_krl_and_restarts(env):
    r = _run(env, "--ca-pub", env["ca_pub"].as_posix(), "--krl", env["krl"].as_posix())
    assert r.returncode == 0, r.stderr
    conf = _conf(env)
    assert "TrustedUserCAKeys " in conf and "RevokedKeys " in conf
    assert (env["etc"] / "pmoves-fleet-krl").read_bytes() == env["krl"].read_bytes()
    assert env["restart_log"].exists()


@pytest.mark.parametrize("krl_kind", ["missing", "not-a-krl"])
def test_bad_krl_rejected_before_any_write(env, krl_kind):
    before = _state(env["etc"])
    krl = env["tmp"] / "bogus.krl"
    if krl_kind == "not-a-krl":
        krl.write_text("garbage\n")
    r = _run(env, "--ca-pub", env["ca_pub"].as_posix(), "--krl", krl.as_posix())
    assert r.returncode == 2, r.stderr
    assert _state(env["etc"]) == before
    assert not env["restart_log"].exists()


def test_drop_in_not_included_fails_and_rolls_back(env):
    """sshd -t passes, but sshd -T shows the CA is not trusted."""
    before = _state(env["etc"])
    r = _run(env, "--ca-pub", env["ca_pub"].as_posix(), STUB_SSHD_INCLUDES="0")
    assert r.returncode == 1
    assert "not effective" in r.stderr
    assert _state(env["etc"]) == before
    assert not env["restart_log"].exists()


def test_failed_rerun_restores_previous_install(env):
    assert _run(env, "--ca-pub", env["ca_pub"].as_posix(),
                "--krl", env["krl"].as_posix()).returncode == 0
    installed = _state(env["etc"])
    env["restart_log"].unlink()

    new_ca = generate_ca(env["tmp"] / "ca2")
    r = _run(env, "--ca-pub", (env["tmp"] / "ca2" / "pmoves-fleet-ca_ed25519.pub").as_posix(),
             STUB_SSHD_T_RC="1")
    assert r.returncode == 1
    assert _state(env["etc"]) == installed
    assert new_ca["public"].encode() not in (env["etc"] / "pmoves-fleet-ca.pub").read_bytes()
    assert not env["restart_log"].exists()


def test_failed_first_install_leaves_no_drop_in_dir(env):
    assert not (env["etc"] / "sshd_config.d").exists()
    r = _run(env, "--ca-pub", env["ca_pub"].as_posix(), STUB_SSHD_T_RC="1")
    assert r.returncode == 1
    assert not (env["etc"] / "sshd_config.d").exists()


def test_restart_failure_rolls_back(env):
    """Every restart path fails: the previous state is restored, as the
    header promises, and sshd is restarted again on the restored config."""
    assert _run(env, "--ca-pub", env["ca_pub"].as_posix(),
                "--krl", env["krl"].as_posix()).returncode == 0
    installed = _state(env["etc"])
    env["restart_log"].unlink()

    generate_ca(env["tmp"] / "ca2")
    r = _run(env, "--ca-pub", (env["tmp"] / "ca2" / "pmoves-fleet-ca_ed25519.pub").as_posix(),
             STUB_RESTART_RC="1")
    assert r.returncode == 1
    assert "restart FAILED" in r.stderr
    assert _state(env["etc"]) == installed
    attempts = env["restart_log"].read_text().splitlines()
    # three paths for the change, then three again for the restored config
    assert attempts == ["systemctl restart sshd", "systemctl restart ssh",
                        "service ssh restart"] * 2


def test_rerun_without_krl_keeps_revocation(env):
    assert _run(env, "--ca-pub", env["ca_pub"].as_posix(),
                "--krl", env["krl"].as_posix()).returncode == 0
    r = _run(env, "--ca-pub", env["ca_pub"].as_posix())
    assert r.returncode == 0, r.stderr
    assert "RevokedKeys " in _conf(env)
