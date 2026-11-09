"""Tests for the one definition of a manifest `github_secret` target.

Two forms: the bare string (unrouted -- repo and scope are the caller's choice
at push time) and the mapping ``{name, repo, env}`` (routed -- the manifest pins
the repo, and the environment or the repository scope). Every reader goes
through `normalize`, so these pin the format itself; the readers' own tests
cover what each does with it.

Also covers `apply_manifest_v2`, the one reader outside `pmoves/tools/`: it used
the target as a dict key, so a mapping target raised TypeError (unhashable)
and took the whole funnel apply down with it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "github_secret_targets.py"

spec = importlib.util.spec_from_file_location("github_secret_targets", MODULE)
assert spec and spec.loader
gst = importlib.util.module_from_spec(spec)
sys.modules["github_secret_targets"] = gst
spec.loader.exec_module(gst)


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------


def test_the_string_form_is_unrouted_on_the_default_repo():
    assert gst.normalize({"github_secret": "N8N_API_KEY"}) == {
        "name": "N8N_API_KEY",
        "repo": "POWERFULMOVES/PMOVES.AI",
        "env": None,
        "routed": False,
    }


def test_a_mapping_without_env_is_routed_to_the_repository_scope():
    got = gst.normalize(
        {"github_secret": {"name": "N8N_API_KEY", "repo": "POWERFULMOVES/PMOVES-N8N"}}
    )
    assert got == {
        "name": "N8N_API_KEY",
        "repo": "POWERFULMOVES/PMOVES-N8N",
        "env": None,
        "routed": True,
    }


def test_a_mapping_with_env_is_routed_to_that_environment():
    got = gst.normalize(
        {"github_secret": {"name": "N8N_API_KEY", "repo": "POWERFULMOVES/PMOVES-N8N", "env": "Prod"}}
    )
    assert got["repo"] == "POWERFULMOVES/PMOVES-N8N" and got["env"] == "Prod"


def test_a_mapping_without_repo_is_malformed():
    """Fail closed. A repo-less mapping used to default to PMOVES.AI while the
    push ran with the operator's --repo, so a fork run overwrote canonical
    secrets. Only the bare name may follow the caller's repo."""
    with pytest.raises(gst.MalformedTarget, match="repo"):
        gst.normalize({"github_secret": {"name": "A_KEY", "env": "Prod"}})
    with pytest.raises(gst.MalformedTarget, match="repo"):
        gst.normalize({"github_secret": {"name": "A_KEY"}})


@pytest.mark.parametrize(
    "target",
    [{"file": ".env.generated", "key": "A"}, {"docker_secret": "a"}, {"github_secret": ""}, "not-a-dict"],
)
def test_non_github_targets_are_none(target):
    assert gst.normalize(target) is None


@pytest.mark.parametrize(
    "value, needle",
    [
        ({"repo": "POWERFULMOVES/PMOVES-N8N"}, "name"),
        ({"name": "A", "repo": "PMOVES-N8N"}, "OWNER/REPO"),
        ({"name": "A", "repository": "POWERFULMOVES/X"}, "unknown key"),
        ({"name": "A", "repo": "O/R", "env": "Prod/../secrets"}, "env"),
        ({"name": "has space"}, "name"),
        ({"name": "A", "repo": "O/R", "env": ".."}, "env"),
        ({"name": "A", "repo": "O/R", "env": "Prod.v2"}, "env"),
        ({"name": "A", "repo": "O/R", "env": "a%2Fb"}, "env"),
        ({"name": "A", "repo": "O/R", "env": "Prod env"}, "env"),
        (["A"], "name or a mapping"),
    ],
)
def test_malformed_targets_raise_with_a_clear_error(value, needle):
    with pytest.raises(gst.MalformedTarget, match=needle):
        gst.normalize({"github_secret": value})


@pytest.mark.parametrize("value", [42, 1.5, True])
def test_bare_non_string_scalars_pass_through_unchanged(value):
    """As before this module: the readers took `github_secret: 42` as it came.
    No new raise outside the emitter."""
    assert gst.normalize({"github_secret": value}) == {
        "name": value, "repo": "POWERFULMOVES/PMOVES.AI", "env": None, "routed": False,
    }


def test_strict_mode_rejects_non_string_scalars():
    with pytest.raises(gst.MalformedTarget, match="name or a mapping"):
        gst.normalize({"github_secret": 42}, strict=True)


def test_the_emitter_rejects_a_non_string_name(tmp_path, capsys):
    m = _manifest(tmp_path, [[{"github_secret": 42}]])
    assert gst.main(["routes", "--manifest", str(m)]) == 2
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# routes (the push script's emitter)
# ---------------------------------------------------------------------------


def _manifest(tmp_path: Path, targets_per_entry) -> Path:
    path = tmp_path / "m.yaml"
    path.write_text(
        yaml.safe_dump(
            {"secrets": [{"id": f"e{i}", "targets": t} for i, t in enumerate(targets_per_entry)]}
        ),
        encoding="utf-8",
    )
    return path


def test_unrouted_names_take_the_callers_repo_and_env_routed_keep_their_own(tmp_path, capsys):
    m = _manifest(
        tmp_path,
        [
            [{"github_secret": "PLAIN"}],
            [
                {"github_secret": "N8N_API_KEY"},
                {"github_secret": {"name": "N8N_API_KEY", "repo": "POWERFULMOVES/PMOVES-N8N", "env": "Prod"}},
            ],
            [{"github_secret": {"name": "REPO_ONLY", "repo": "POWERFULMOVES/PMOVES-N8N"}}],
        ],
    )
    rc = gst.main(["routes", "--manifest", str(m), "--default-repo", "O/R", "--default-env", "Dev"])
    assert rc == 0
    assert capsys.readouterr().out.splitlines() == [
        "PLAIN\tO/R\tDev",
        "N8N_API_KEY\tO/R\tDev",
        "N8N_API_KEY\tPOWERFULMOVES/PMOVES-N8N\tProd",
        "REPO_ONLY\tPOWERFULMOVES/PMOVES-N8N\t",
    ]


def test_duplicate_routes_are_emitted_once(tmp_path, capsys):
    m = _manifest(tmp_path, [[{"github_secret": "A"}], [{"github_secret": "A"}]])
    assert gst.main(["routes", "--manifest", str(m)]) == 0
    assert capsys.readouterr().out.splitlines() == ["A\tPOWERFULMOVES/PMOVES.AI\t"]


def test_a_malformed_target_fails_the_emitter(tmp_path, capsys):
    m = _manifest(tmp_path, [[{"github_secret": {"repo": "O/R"}}]])
    assert gst.main(["routes", "--manifest", str(m)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "name" in captured.err


def test_the_emitter_writes_utf8_and_lf_on_every_platform(tmp_path):
    """Run as the push script runs it: a subprocess whose stdout/stderr are
    pipes. On Windows those default to cp1252 + CRLF, so a character outside
    cp1252 in an error message crashed the emitter (exit 1, a traceback)
    instead of reporting it (exit 2)."""
    import subprocess

    m = _manifest(tmp_path, [[{"github_secret": {"name": "\u540d", "repo": "O/R"}}], [{"github_secret": "OK"}]])
    env = {k: v for k, v in __import__("os").environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env["PYTHONUTF8"] = "0"
    bad = subprocess.run(
        [sys.executable, str(MODULE), "routes", "--manifest", str(m)],
        capture_output=True, env=env, timeout=60,
    )
    assert bad.returncode == 2, bad.stderr
    assert "\u540d" in bad.stderr.decode("utf-8")

    ok_manifest = _manifest(tmp_path, [[{"github_secret": "OK"}]])
    good = subprocess.run(
        [sys.executable, str(MODULE), "routes", "--manifest", str(ok_manifest)],
        capture_output=True, env=env, timeout=60,
    )
    assert good.returncode == 0
    assert good.stdout == b"OK\tPOWERFULMOVES/PMOVES.AI\t\n"


def test_an_unreadable_manifest_fails_the_emitter(tmp_path):
    assert gst.main(["routes", "--manifest", str(tmp_path / "absent.yaml")]) == 2


# ---------------------------------------------------------------------------
# apply_manifest_v2 -- the reader in pmoves/chit
# ---------------------------------------------------------------------------


def test_apply_manifest_v2_accepts_a_mapping_target(tmp_path):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from pmoves.chit import apply_manifest_v2

    manifest = tmp_path / "chit" / "m.yaml"
    manifest.parent.mkdir()
    manifest.write_text(
        yaml.safe_dump(
            {
                "entries": [
                    {"source": {"label": "PLAIN_KEY"}, "targets": [{"github_secret": "PLAIN_KEY"}]},
                    {
                        "source": {"label": "N8N_API_KEY"},
                        "targets": [
                            {"github_secret": {"name": "N8N_API_KEY", "repo": "POWERFULMOVES/PMOVES-N8N"}}
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    # Synthetic values only. POSTGRES_PASSWORD keeps the common-credential sync
    # on its explicit branch, off the os.environ fallback (covered by
    # tests/unit/test_chit_sync_common_credentials.py). No env.tier-* file
    # exists under tmp_path to write to.
    result = apply_manifest_v2(
        {"PLAIN_KEY": "synthetic-a", "N8N_API_KEY": "synthetic-b", "POSTGRES_PASSWORD": "synthetic-c"},
        manifest,
        base_dir=tmp_path,
    )
    assert result["github_secrets"] == 2
    written = json.loads((tmp_path / "data" / "chit" / "github_secrets.json").read_text(encoding="utf-8"))
    assert set(written) == {"PMOVES_PLAIN_KEY", "PMOVES_N8N_API_KEY"}


def _two_target_manifest(tmp_path: Path, routed: bool) -> Path:
    manifest = tmp_path / "chit" / "m.yaml"
    manifest.parent.mkdir(exist_ok=True)
    targets = [{"github_secret": "PLAIN_KEY"}]
    if routed:
        targets.append({"github_secret": {"name": "PLAIN_KEY", "repo": "O/R"}})
    manifest.write_text(
        yaml.safe_dump({"entries": [{"source": {"label": "PLAIN_KEY"}, "targets": targets}]}),
        encoding="utf-8",
    )
    return manifest


def test_apply_manifest_v2_without_the_tools_module_keeps_bare_names_working(tmp_path, monkeypatch):
    """Images that copy only chit/ lack pmoves/tools/github_secret_targets.py.
    A module-level or unguarded import made apply_manifest_v2 raise
    ModuleNotFoundError there; bare names must behave exactly as before."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from pmoves.chit import apply_manifest_v2

    monkeypatch.setitem(sys.modules, "pmoves.tools.github_secret_targets", None)  # import -> ImportError
    secrets = {"PLAIN_KEY": "synthetic-a", "POSTGRES_PASSWORD": "synthetic-c"}
    result = apply_manifest_v2(secrets, _two_target_manifest(tmp_path, routed=False), base_dir=tmp_path)
    assert result["github_secrets"] == 1

    with pytest.raises(ValueError, match="github_secret_targets"):
        apply_manifest_v2(secrets, _two_target_manifest(tmp_path, routed=True), base_dir=tmp_path)
