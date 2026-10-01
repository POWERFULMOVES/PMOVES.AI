"""`make docker-login` must accept a read-only GHCR token that env files cannot displace.

Knuckles (2026-10-01): pulls from ghcr.io/powerfulmoves returned 403 while
GHCR_TOKEN and GH_PAT_PUBLISH were exported, and with-env.sh lets env files
override exported vars, so an operator-supplied read token had no reliable way
in. GHCR_READ_TOKEN_FILE is read before the env loader and wins when set.

No network and no real login: tokens are fabricated at runtime, and the
"success" case runs against a fake `docker` on PATH that records argv/stdin.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]
SCRIPT = PMOVES / "scripts" / "ghcr_login.sh"
FAKE_TOKEN = "ghp_" + "x" * 36
DECOY = "ghp_" + "d" * 36


def _token_file(tmp_path: Path, content: str = FAKE_TOKEN, mode: int = 0o600, end: str = "\n") -> Path:
    path = tmp_path / "ghcr_read_token"
    path.write_bytes((content + end).encode())
    path.chmod(mode)
    return path


def _run(
    env_extra: dict[str, str], tmp_path: Path, path_prefix: str | None = None, bash_flags: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GHCR_", "GH_PAT", "DRY_RUN", "SHELLOPTS"))}
    env.update(env_extra)
    if path_prefix:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    return subprocess.run(["bash", *bash_flags, str(SCRIPT)], env=env, capture_output=True, text=True, cwd=tmp_path, timeout=30)


def _fake_bin(tmp_path: Path, name: str, body: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / name
    fake.write_text("#!/usr/bin/env bash\n" + body)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def _no_token_leak(proc: subprocess.CompletedProcess[str]) -> None:
    assert FAKE_TOKEN not in proc.stdout + proc.stderr
    assert DECOY not in proc.stdout + proc.stderr


def test_dry_run_prints_user_registry_and_source_only(tmp_path: Path) -> None:
    proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "dry-run: docker login ghcr.io as octo (token source: GHCR_READ_TOKEN_FILE)"
    _no_token_leak(proc)


def test_read_file_beats_exported_publish_tokens(tmp_path: Path) -> None:
    proc = _run(
        {
            "GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path)),
            "GHCR_READ_USERNAME": "octo",
            "GHCR_TOKEN": DECOY,
            "GH_PAT_PUBLISH": DECOY,
            "DRY_RUN": "1",
        },
        tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "token source: GHCR_READ_TOKEN_FILE" in proc.stdout
    _no_token_leak(proc)


def test_refuses_file_not_0600(tmp_path: Path) -> None:
    proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path, mode=0o644)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
    assert proc.returncode == 1
    assert "must be mode exactly 0600 (is 644;" in proc.stderr
    _no_token_leak(proc)


def test_refuses_stricter_0400_and_says_why(tmp_path: Path) -> None:
    proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path, mode=0o400)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
    assert proc.returncode == 1
    assert "exactly 0600" in proc.stderr
    _no_token_leak(proc)


def test_refuses_symlink_without_suggesting_chmod(tmp_path: Path) -> None:
    link = tmp_path / "link"
    link.symlink_to(_token_file(tmp_path))
    proc = _run({"GHCR_READ_TOKEN_FILE": str(link), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
    assert proc.returncode == 1
    assert "not a symlink" in proc.stderr
    assert "chmod" not in proc.stderr
    _no_token_leak(proc)


def test_refuses_file_owned_by_another_uid(tmp_path: Path) -> None:
    # Cannot chown as non-root, so the invoking uid is faked instead: a 0600
    # file owned by someone else is exactly what `sudo` would otherwise accept.
    bin_dir = _fake_bin(tmp_path, "id", 'if [ "${1:-}" = "-u" ]; then echo 4242; else exec /usr/bin/id "$@"; fi\n')
    proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path, str(bin_dir))
    assert proc.returncode == 1
    assert "must be owned by the invoking user" in proc.stderr
    _no_token_leak(proc)


def test_refuses_token_split_across_lines(tmp_path: Path) -> None:
    for content, end in ((FAKE_TOKEN[:20] + "\n" + FAKE_TOKEN[20:], "\n"), (FAKE_TOKEN, "\n\n"), (FAKE_TOKEN, "\r\n\r\n"), (FAKE_TOKEN, "\0junk\n")):
        proc = _run(
            {"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path, content=content, end=end)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"},
            tmp_path,
        )
        assert proc.returncode == 1, repr(content + end)
        assert "exactly one line" in proc.stderr
        _no_token_leak(proc)


def test_accepts_one_line_with_optional_crlf_or_no_newline(tmp_path: Path) -> None:
    for end in ("", "\n", "\r\n"):
        proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path, end=end)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
        assert proc.returncode == 0, (repr(end), proc.stderr)
        _no_token_leak(proc)


def test_bash_xtrace_never_prints_the_token(tmp_path: Path) -> None:
    # Review of 7407a27c: `bash -x` printed the token 3 times (assignment,
    # regex test, printf). Exercise both the dry-run and the docker path.
    bin_dir = _fake_bin(tmp_path, "docker", "cat >/dev/null\n")
    for extra in ({"DRY_RUN": "1"}, {}):
        proc = _run(
            {"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path)), "GHCR_READ_USERNAME": "octo", **extra},
            tmp_path, str(bin_dir), bash_flags=("-x",),
        )
        assert proc.returncode == 0, proc.stderr
        assert (proc.stdout + proc.stderr).count(FAKE_TOKEN) == 0


def test_refuses_non_classic_or_truncated_token(tmp_path: Path) -> None:
    for bad in (FAKE_TOKEN[:-2], "github_pat_" + "x" * 40, "ghs_" + "x" * 36, ""):
        proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path, content=bad)), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
        assert proc.returncode == 1, bad
        assert "does not hold a classic PAT" in proc.stderr
        if bad:
            assert bad not in proc.stdout + proc.stderr


def test_refuses_missing_username(tmp_path: Path) -> None:
    proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path)), "DRY_RUN": "1"}, tmp_path)
    assert proc.returncode == 1
    assert "GHCR_USERNAME" in proc.stderr


def test_refuses_missing_file(tmp_path: Path) -> None:
    proc = _run({"GHCR_READ_TOKEN_FILE": str(tmp_path / "absent"), "GHCR_READ_USERNAME": "octo", "DRY_RUN": "1"}, tmp_path)
    assert proc.returncode == 1
    assert "not a regular file" in proc.stderr


def test_token_goes_to_docker_on_stdin_never_argv(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "docker"
    fake.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{tmp_path}/argv"\ncat > "{tmp_path}/stdin"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    proc = _run({"GHCR_READ_TOKEN_FILE": str(_token_file(tmp_path)), "GHCR_READ_USERNAME": "octo"}, tmp_path, str(bin_dir))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "✔ GHCR login ok as octo (token source: GHCR_READ_TOKEN_FILE)"
    argv = (tmp_path / "argv").read_text().split("\n")
    assert argv[:5] == ["login", "ghcr.io", "-u", "octo", "--password-stdin"]
    assert FAKE_TOKEN not in (tmp_path / "argv").read_text()
    assert (tmp_path / "stdin").read_text() == FAKE_TOKEN
    _no_token_leak(proc)


def test_make_target_forwards_read_file_and_username(stub_docker_path) -> None:
    proc = subprocess.run(
        ["make", "-n", "-C", str(PMOVES), "docker-login", "GHCR_READ_TOKEN_FILE=/x/tok", "GHCR_USERNAME=octo", "DRY_RUN=1"],
        capture_output=True, text=True, timeout=60, env=stub_docker_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert 'GHCR_READ_TOKEN_FILE="/x/tok" GHCR_READ_USERNAME="octo" DRY_RUN="1"' in proc.stdout
    assert "scripts/ghcr_login.sh" in proc.stdout


def test_make_docker_login_under_exported_xtrace_never_prints_the_token(tmp_path: Path, stub_docker_path) -> None:
    # Review of 7407a27c: with SHELLOPTS=xtrace exported, the real recipe
    # (which now runs `bash` explicitly) printed the token twice before the
    # DRY_RUN exit. `-o ensure-env-shared` keeps make from writing env.shared.
    env = {k: v for k, v in stub_docker_path.items() if not k.startswith(("GHCR_", "GH_PAT", "DRY_RUN"))}
    env["SHELLOPTS"] = "xtrace"
    proc = subprocess.run(
        ["make", "-s", "-C", str(PMOVES), "-o", "ensure-env-shared", "docker-login",
         f"GHCR_READ_TOKEN_FILE={_token_file(tmp_path)}", "GHCR_USERNAME=octo", "DRY_RUN=1"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "token source: GHCR_READ_TOKEN_FILE" in proc.stdout
    assert proc.stdout.count(FAKE_TOKEN) == 0
    assert proc.stderr.count(FAKE_TOKEN) == 0


def test_gh_app_token_confirm_reads_the_make_variable(stub_docker_path) -> None:
    # `"$$(CONFIRM)"` reached the shell as command substitution `$(CONFIRM)`,
    # so the documented `ALL=1 CONFIRM=1` always exited 3. Render only (-n);
    # nothing is minted.
    proc = subprocess.run(
        ["make", "-n", "-C", str(PMOVES), "gh-app-token", "ALL=1", "CONFIRM=1"],
        capture_output=True, text=True, timeout=60, env=stub_docker_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert 'if [ "1" != "1" ]' in proc.stdout
    assert "$(CONFIRM)" not in proc.stdout
