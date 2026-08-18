"""Pytest suite for the clear-a-key capability in pmoves.scripts.bootstrap_env.

Before this, `rotate_secret` opened with `if not value: raise ValueError(...)`,
so there was no way to set a key in env.shared back to empty. That mattered:
upstream Supabase ships SUPABASE_SECRET_KEY and SUPABASE_PUBLISHABLE_KEY empty
on purpose and its Kong entrypoint strips blank key entries, so a *populated*
one is what breaks the deployment — a duplicate key crash-looped Kong 3,924
times (#2593 / #2595). Empty is a configured state, and the pipeline could not
express it.

Every test writes to a tmp_path env file. None of them touch the real
env.shared, which is zero-access under damage-control.
"""

from pathlib import Path

import pytest

from pmoves.scripts.bootstrap_env import main, rotate_secret

ORIGINAL = (
    "# leading comment\n"
    "OTHER=keepme\n"
    "SUPABASE_SECRET_KEY=eyJhbGciOiJIUzI1NiJ9.LEGACY_JWT\n"
    "TRAILING=yes\n"
)


@pytest.fixture()
def env_file(tmp_path: Path) -> Path:
    p = tmp_path / "env.shared"
    p.write_text(ORIGINAL, encoding="utf-8")
    return p


class TestClear:
    def test_clear_blanks_the_key(self, env_file: Path):
        rotate_secret(
            "SUPABASE_SECRET_KEY", value="", allow_empty=True, env_path=env_file
        )
        assert "SUPABASE_SECRET_KEY=\n" in env_file.read_text(encoding="utf-8")

    def test_clear_is_surgical(self, env_file: Path):
        """Everything except the target line survives byte-for-byte."""
        rotate_secret(
            "SUPABASE_SECRET_KEY", value="", allow_empty=True, env_path=env_file
        )
        lines = env_file.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# leading comment"
        assert "OTHER=keepme" in lines
        assert "TRAILING=yes" in lines
        assert len(lines) == 4  # nothing added, nothing dropped

    def test_clear_is_idempotent(self, env_file: Path):
        for _ in range(2):
            rotate_secret(
                "SUPABASE_SECRET_KEY", value="", allow_empty=True, env_path=env_file
            )
        body = env_file.read_text(encoding="utf-8")
        assert body.count("SUPABASE_SECRET_KEY=") == 1

    def test_clear_appends_when_key_absent(self, env_file: Path):
        rotate_secret("NEVER_SET", value="", allow_empty=True, env_path=env_file)
        assert "NEVER_SET=\n" in env_file.read_text(encoding="utf-8")


class TestEmptyStillGuarded:
    """allow_empty is opt-in. An empty value must never arrive by accident.

    This is the whole reason `--clear` is a separate flag rather than
    `--value ""`: an unset shell variable expands to the empty string, and
    silently blanking a live credential is the failure mode being prevented.
    """

    def test_empty_value_refused_by_default(self, env_file: Path):
        with pytest.raises(ValueError, match="no value to rotate"):
            rotate_secret("OTHER", value="", env_path=env_file)

    def test_refusal_points_at_the_right_flag(self, env_file: Path):
        with pytest.raises(ValueError, match="--clear"):
            rotate_secret("OTHER", value="", env_path=env_file)

    def test_original_untouched_after_refusal(self, env_file: Path):
        with pytest.raises(ValueError):
            rotate_secret("OTHER", value="", env_path=env_file)
        assert env_file.read_text(encoding="utf-8") == ORIGINAL


class TestRotateUnchanged:
    """The pre-existing paths must behave exactly as before."""

    def test_generation_still_works(self, env_file: Path):
        value = rotate_secret("GENERATED", length=48, env_path=env_file)
        assert len(value) >= 32
        assert f"GENERATED={value}" in env_file.read_text(encoding="utf-8")

    def test_explicit_value_still_works(self, env_file: Path):
        rotate_secret("OTHER", value="newvalue", env_path=env_file)
        assert "OTHER=newvalue" in env_file.read_text(encoding="utf-8")

    def test_multiline_still_refused(self, env_file: Path):
        with pytest.raises(ValueError, match="multi-line"):
            rotate_secret("OTHER", value="a\nb", env_path=env_file)

    def test_invalid_key_still_refused(self, env_file: Path):
        with pytest.raises(ValueError, match="invalid env key"):
            rotate_secret("not-a-valid-key", value="x", env_path=env_file)


class TestCli:
    def test_clear_and_rotate_are_mutually_exclusive(self, capsys):
        rc = main(["--clear", "A", "--rotate", "B"])
        assert rc == 2
        assert "mutually exclusive" in capsys.readouterr().err
