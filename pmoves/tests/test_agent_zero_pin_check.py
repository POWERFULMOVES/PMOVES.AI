"""Guards for the agent-zero pin check's two silent-pass defects (review on #2676).

Both are the same shape: the gate kept reporting success while measuring
something other than what ships.

1. It compared against the GITLINK, but the image clones the BRANCH TIP
   (Dockerfile:21 `git clone --branch ${AGENT_ZERO_REF}`). Those diverge in this
   repo today, so a fork constraint could conflict with our overlay lock while a
   required check stayed green.
2. `norm()` folded `_` but not `.`, so `zope.interface` and `zope-interface`
   keyed differently and a real override was invisible to both the constraint
   lookup and the duplicate-declaration intersection.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "agent_zero_pin_check.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("agent_zero_pin_check", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "a,b",
    [
        ("zope.interface", "zope-interface"),
        ("zope_interface", "zope.interface"),
        ("ruamel.yaml", "ruamel-yaml"),
        ("backports.zoneinfo", "backports-zoneinfo"),
        ("A__B..C", "a-b-c"),
    ],
)
def test_pep503_equivalent_spellings_collapse_to_one_key(mod, a, b):
    """Runs of -, _ and . are ALL equivalent. Folding only `_` misses overrides."""
    assert mod.norm(a) == mod.norm(b)


def test_norm_lowercases(mod):
    assert mod.norm("Django") == "django"


def test_norm_collapses_runs_not_just_single_separators(mod):
    """PEP 503 normalises RUNS, so `a...b` and `a-b` are the same distribution."""
    assert mod.norm("a...b") == "a-b"
    assert mod.norm("a_-_b") == "a-b"


def test_the_ref_is_read_from_the_published_image_dockerfile(mod):
    """Dockerfile.multiarch builds the PUBLISHED image and is the file the
    auto-bump workflow rewrites, so it is the only authority on the ref."""
    assert mod.PUBLISHED_DOCKERFILE.name == "Dockerfile.multiarch"
    assert mod.dockerfile_ref(mod.PUBLISHED_DOCKERFILE), (
        "ARG AGENT_ZERO_REF must be readable from the published-image Dockerfile"
    )


def test_both_build_definitions_currently_agree(mod):
    """They may legitimately diverge mid-bump, but the tool must NOTICE."""
    assert mod.dockerfile_ref(mod.PUBLISHED_DOCKERFILE) == mod.dockerfile_ref(
        mod.COMPOSE_DOCKERFILE
    )


def test_dockerfile_ref_parses_a_version_tag_not_just_a_branch(mod, tmp_path):
    """The auto-bump workflow writes version TAGS; a branch-only reader breaks."""
    f = tmp_path / "Dockerfile.multiarch"
    f.write_text("FROM x\nARG AGENT_ZERO_REF=v2.10.1\nRUN true\n", encoding="utf-8")
    assert mod.dockerfile_ref(f) == "v2.10.1"


def test_dockerfile_ref_returns_none_for_a_missing_or_refless_file(mod, tmp_path):
    assert mod.dockerfile_ref(tmp_path / "nope") is None
    f = tmp_path / "Dockerfile"
    f.write_text("FROM scratch\n", encoding="utf-8")
    assert mod.dockerfile_ref(f) is None


# --- resolve_ref_sha: mocked, never a real request ---------------------------
#
# The previous version of this test made a live 30s-timeout GitHub call on every
# suite run, so an offline runner paid the full delay and then PASSED because
# None was accepted -- neither success nor failure was actually exercised.
#
# Every test below stubs BOTH transports (`_git` and urlopen). A test that stubs
# only urlopen would now silently make a real `git ls-remote`.

import urllib.error  # noqa: E402

SHA_A, SHA_B, SHA_C, SHA_D = "a" * 40, "b" * 40, "c" * 40, "d" * 40
TOKEN = "ghs_FAKE_TOKEN_must_never_be_printed_0123"


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def read(self):
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def _url(req):
    return req if isinstance(req, str) else req.full_url


def _no_http(req, timeout=None):
    raise AssertionError("must not make an HTTP request: {}".format(_url(req)))


def _no_git(args, cwd=None, timeout=None):
    raise AssertionError("must not run git: {}".format(args))


def _offline(req, timeout=None):
    raise urllib.error.URLError("offline")


def _ls_remote(stdout, rc=0, stderr=""):
    calls = []
    def fake(args, cwd=None, timeout=None):
        calls.append(list(args))
        assert args[0] == "ls-remote", args
        return rc, stdout, stderr
    fake.calls = calls
    return fake


@pytest.fixture
def no_token(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def test_ls_remote_head_hit_uses_no_http(mod, monkeypatch, no_token):
    fake = _ls_remote("{}\trefs/heads/PMOVES.AI-Edition-v2.13\n".format(SHA_A))
    monkeypatch.setattr(mod, "_git", fake)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    causes = []
    assert mod.resolve_ref_sha("PMOVES.AI-Edition-v2.13", causes) == SHA_A
    assert causes == []
    argv = fake.calls[0]
    assert argv[:2] == ["ls-remote", mod.FORK_URL]
    assert "refs/tags/PMOVES.AI-Edition-v2.13^{}" in argv


def test_ls_remote_annotated_tag_is_peeled_to_the_commit(mod, monkeypatch, no_token):
    """`git clone --branch v1` checks out the commit, not the tag object."""
    out = "{}\trefs/tags/v2.10.1\n{}\trefs/tags/v2.10.1^{{}}\n".format(SHA_B, SHA_C)
    monkeypatch.setattr(mod, "_git", _ls_remote(out))
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    assert mod.resolve_ref_sha("v2.10.1") == SHA_C


def test_ls_remote_lightweight_tag(mod, monkeypatch, no_token):
    monkeypatch.setattr(mod, "_git", _ls_remote("{}\trefs/tags/v3\n".format(SHA_B)))
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    assert mod.resolve_ref_sha("v3") == SHA_B


def test_ls_remote_prefers_the_branch_like_git_clone(mod, monkeypatch, no_token):
    out = "{}\trefs/heads/x\n{}\trefs/tags/x\n{}\trefs/tags/x^{{}}\n".format(SHA_A, SHA_B, SHA_C)
    monkeypatch.setattr(mod, "_git", _ls_remote(out))
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    assert mod.resolve_ref_sha("x") == SHA_A


def test_ls_remote_tail_match_on_another_ref_is_not_a_hit(mod, monkeypatch, no_token):
    """ls-remote patterns match the TAIL of a ref name; only exact names count."""
    monkeypatch.setattr(mod, "_git", _ls_remote("{}\trefs/pull/refs/heads/x\n".format(SHA_A)))
    monkeypatch.setattr(mod.urllib.request, "urlopen", _offline)
    causes = []
    assert mod.resolve_ref_sha("x", causes) is None
    assert any("no refs/heads/x" in c for c in causes)


def test_ls_remote_non_sha_output_is_rejected(mod, monkeypatch, no_token):
    monkeypatch.setattr(mod, "_git", _ls_remote("not-a-sha\trefs/heads/x\n"))
    monkeypatch.setattr(mod.urllib.request, "urlopen", _offline)
    causes = []
    assert mod.resolve_ref_sha("x", causes) is None
    assert any("non-sha" in c for c in causes)


def test_ls_remote_fails_and_authenticated_api_succeeds(mod, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setattr(
        mod, "_git", _ls_remote("", rc=128, stderr="fatal: unable to access: Could not resolve host")
    )
    seen = []
    def fake(req, timeout=None):
        seen.append(req)
        return _Resp({"object": {"sha": SHA_D, "type": "commit"}})
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    causes = []
    assert mod.resolve_ref_sha("PMOVES.AI-Edition-v2.13", causes) == SHA_D
    assert "/git/ref/heads/PMOVES.AI-Edition-v2.13" in seen[0].full_url
    assert seen[0].get_header("Authorization") == "Bearer " + TOKEN
    assert any("rc=128" in c and "Could not resolve host" in c for c in causes)
    assert TOKEN not in " ".join(causes)


def test_api_fallback_peels_an_annotated_tag(mod, monkeypatch, no_token):
    monkeypatch.setattr(mod, "_git", _ls_remote("", rc=2, stderr="boom"))
    tag_url = "https://api.github.com/repos/POWERFULMOVES/PMOVES-Agent-Zero/git/tags/" + SHA_B
    def fake(req, timeout=None):
        url = _url(req)
        if "/git/ref/heads/" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if "/git/ref/tags/" in url:
            return _Resp({"object": {"sha": SHA_B, "type": "tag", "url": tag_url}})
        assert url == tag_url
        return _Resp({"object": {"sha": SHA_C, "type": "commit"}})
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    assert mod.resolve_ref_sha("v2.10.1") == SHA_C


def test_both_fail_problem_names_both_causes_and_exit_is_nonzero(mod, monkeypatch, capsys, no_token):
    monkeypatch.setattr(
        mod, "_git",
        _ls_remote("", rc=128, stderr="fatal: unable to access 'https://github.com/': SSL certificate problem"),
    )
    def fake(req, timeout=None):
        raise urllib.error.HTTPError(_url(req), 403, "rate limit exceeded", {}, None)
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(mod, "gitlink_sha", lambda: SHA_A)

    problems = []
    assert mod.read_fork_requirements(None, problems) is None
    text = " ".join(problems)
    assert "Refusing to fall back" in text
    assert "rc=128" in text and "SSL certificate problem" in text
    assert "HTTP 403" in text and "rate limit exceeded" in text
    assert "unauthenticated" in text

    monkeypatch.setattr(mod.sys, "argv", ["agent_zero_pin_check.py"])
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "INPUT MISSING" in out and "HTTP 403" in out and "rc=128" in out


@pytest.mark.parametrize(
    "bad",
    ["-oops", "--upload-pack=x", "a..b", "x@{1}", "a b", "ref;rm", "../x", "x" + ".lock",
     "a:b", "a^{}", "a~1", "x/", "/x", "a//b", "a\nb", "a*"],
)
def test_bad_ref_name_is_refused_before_any_callout(mod, monkeypatch, bad):
    monkeypatch.setattr(mod, "_git", _no_git)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    causes = []
    assert mod.resolve_ref_sha(bad, causes) is None
    assert causes and "refused ref name" in causes[0]


def test_bad_explicit_ref_is_refused(mod, monkeypatch):
    monkeypatch.setattr(mod, "_git", _no_git)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    problems = []
    assert mod.read_fork_requirements("--upload-pack=touch x", problems) is None
    assert "refused --ref" in " ".join(problems)


def test_resolve_ref_sha_handles_an_empty_ref_without_calling_out(mod, monkeypatch):
    monkeypatch.setattr(mod, "_git", _no_git)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    assert mod.resolve_ref_sha(None) is None
    assert mod.resolve_ref_sha("") is None


def test_http_error_text_never_carries_the_token(mod, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    e = urllib.error.URLError("proxy said Bearer " + TOKEN)
    assert TOKEN not in mod._http_error(e)


# --- fetch_fork_requirements: the second network read ------------------------


def test_fetch_uses_depth1_git_fetch_when_submodule_absent(mod, monkeypatch, tmp_path, no_token):
    monkeypatch.setattr(mod, "ROOT", tmp_path)  # no populated submodule here
    def fake(args, cwd=None, timeout=None):
        if args[:1] == ["init"]:
            return 0, "", ""
        if "fetch" in args:
            assert "--depth" in args and args[-2:] == [mod.FORK_URL, SHA_A]
            return 0, "", ""
        if "show" in args:
            return 0, "starlette==1.0.1\n", ""
        raise AssertionError(args)
    monkeypatch.setattr(mod, "_git", fake)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    causes = []
    assert mod.fetch_fork_requirements(SHA_A, causes) == "starlette==1.0.1\n"
    assert any("not populated" in c for c in causes)


def test_fetch_all_paths_fail_records_every_cause(mod, monkeypatch, tmp_path, no_token):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    def fake(args, cwd=None, timeout=None):
        if args[:1] == ["init"]:
            return 0, "", ""
        return 128, "", "fatal: could not read from remote repository"
    monkeypatch.setattr(mod, "_git", fake)
    def boom(req, timeout=None):
        raise urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate")
    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    problems = []
    assert mod.read_fork_requirements(SHA_A, problems) is None
    text = " ".join(problems)
    assert "not populated" in text
    assert "git fetch: rc=128" in text and "could not read from remote" in text
    assert "CERTIFICATE_VERIFY_FAILED" in text


def test_populated_submodule_is_read_without_network(mod, monkeypatch, tmp_path):
    (tmp_path / mod.SUBMODULE / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    def fake(args, cwd=None, timeout=None):
        assert args[:2] == ["-C", str(tmp_path / mod.SUBMODULE)], args
        assert args[2:] == ["show", "{}:requirements.txt".format(SHA_A)]
        return 0, "fastapi\n", ""
    monkeypatch.setattr(mod, "_git", fake)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    assert mod.fetch_fork_requirements(SHA_A, []) == "fastapi\n"


def test_unresolvable_tip_FAILS_rather_than_using_the_gitlink(mod, monkeypatch):
    """The merge gate reads the exit STATUS, not stderr. A quiet downgrade to the
    gitlink under API rate-limiting is indistinguishable from success."""
    monkeypatch.setattr(mod, "resolve_ref_sha", lambda ref, causes=None: None)
    monkeypatch.setattr(mod, "gitlink_sha", lambda: "c" * 40)
    problems = []
    assert mod.read_fork_requirements(None, problems) is None
    assert problems, "an unresolvable tip must be reported as an input failure"
    assert "Refusing to fall back" in " ".join(problems)


def test_disagreeing_build_definitions_are_an_input_failure(mod, monkeypatch):
    monkeypatch.setattr(mod, "dockerfile_ref",
                        lambda p: "v2.10.1" if p is mod.PUBLISHED_DOCKERFILE else "main")
    problems = []
    assert mod.read_fork_requirements(None, problems) is None
    assert "disagree" in " ".join(problems)


# --- review P3s on #3219 -------------------------------------------------------


@pytest.mark.parametrize("body", [b"", b"<!DOCTYPE html><html><body>Rate limited</body></html>\n"])
def test_zero_declarations_is_a_problem_not_clean(mod, monkeypatch, tmp_path, capsys, no_token, body):
    """A 200 with an empty or HTML body must not become 'clean against 0'."""
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_git", lambda args, cwd=None, timeout=None: (128, "", "fatal: offline"))
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda req, timeout=None: _Resp(body))
    problems = []
    assert mod.read_fork_requirements(SHA_A, problems) is None
    assert "0 parseable declarations" in " ".join(problems)

    monkeypatch.setattr(mod.sys, "argv", ["agent_zero_pin_check.py", "--ref", SHA_A])
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "INPUT MISSING" in out and "clean" not in out


def test_zero_declarations_from_git_fetch_falls_through_not_succeeds(mod, monkeypatch, tmp_path, no_token):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    def fake(args, cwd=None, timeout=None):
        return (0, "# only a comment\n", "") if "show" in args else (0, "", "")
    monkeypatch.setattr(mod, "_git", fake)
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda req, timeout=None: _Resp(b"starlette==1.0.1\n"))
    causes = []
    assert mod.fetch_fork_requirements(SHA_A, causes) == "starlette==1.0.1\n"
    assert any(c.startswith("git fetch: 0 parseable") for c in causes)


def test_main_floor_holds_for_any_empty_fork_text(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "read_fork_requirements", lambda ref, problems: "\n# nothing\n")
    monkeypatch.setattr(mod.sys, "argv", ["agent_zero_pin_check.py"])
    assert mod.main() == 1
    assert "0 parseable declarations" in capsys.readouterr().out


def test_git_child_env_scrubs_repository_selectors(mod, monkeypatch):
    """Run from a git hook, GIT_DIR etc. would aim the throwaway fetch at the parent repo."""
    for k in mod._GIT_SCRUB:
        monkeypatch.setenv(k, "/parent/repo/.git")
    monkeypatch.setenv("PMOVES_KEEP_ME", "1")
    seen = {}
    class _P:
        returncode, stdout, stderr = 0, "", ""
    def fake_run(argv, **kw):
        seen.update(kw["env"])
        assert "shell" not in kw
        return _P()
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod._git(["version"])[0] == 0
    assert "GIT_DIR" not in seen
    assert not set(mod._GIT_SCRUB) & set(seen)
    assert set(mod._GIT_SCRUB) >= {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR"}
    assert seen["GIT_TERMINAL_PROMPT"] == "0" and seen["PMOVES_KEEP_ME"] == "1"


@pytest.mark.parametrize(
    "err",
    [urllib.error.HTTPError("u", 403, "rate limit exceeded", {}, None),
     urllib.error.HTTPError("u", 502, "Bad Gateway", {}, None),
     urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED]")],
)
def test_api_non_404_heads_error_stops_without_trying_tags(mod, monkeypatch, no_token, err):
    """Unknown whether the BRANCH exists; clone prefers it, so a tag answer could be the wrong tree."""
    monkeypatch.setattr(mod, "_git", _ls_remote("", rc=2, stderr="offline"))
    seen = []
    def fake(req, timeout=None):
        seen.append(_url(req))
        if "/git/ref/heads/" in _url(req):
            raise err
        return _Resp({"object": {"sha": SHA_C, "type": "commit"}})
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    causes = []
    assert mod.resolve_ref_sha("v2.10.1", causes) is None
    assert not any("/git/ref/tags/" in u for u in seen)
    assert any(c.startswith("api heads") for c in causes)


def test_api_heads_404_moves_on_to_tags(mod, monkeypatch, no_token):
    monkeypatch.setattr(mod, "_git", _ls_remote("", rc=2, stderr="offline"))
    def fake(req, timeout=None):
        if "/git/ref/heads/" in _url(req):
            raise urllib.error.HTTPError(_url(req), 404, "Not Found", {}, None)
        return _Resp({"object": {"sha": SHA_C, "type": "commit"}})
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    assert mod.resolve_ref_sha("v2.10.1") == SHA_C


@pytest.mark.parametrize("bad", ["x\n", "+x", "+refs/heads/x:refs/heads/y"])
def test_ref_regex_is_a_fullmatch_and_refuses_force_marker(mod, monkeypatch, bad):
    monkeypatch.setattr(mod, "_git", _no_git)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_http)
    assert not mod.valid_ref_name(bad)
    assert mod.resolve_ref_sha(bad) is None


def test_sha_check_is_a_fullmatch(mod):
    assert mod._is_sha(SHA_A)
    assert not mod._is_sha(SHA_A + "\n")
    assert not mod._is_sha(SHA_A.upper())
