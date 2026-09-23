"""Fleet PR review fallback chain (.github/scripts/review_chain.py).

Drives the real chain end-to-end as a subprocess with STUBBED reviewers:

* the two Kilo tiers run a stub command in place of kilo_review_tier.sh (the
  chain's REVIEW_KILO_CMD seam), scripted per tier;
* the Spark tier talks real HTTP to a stub server on 127.0.0.1, so the health
  probe, the ready/contract parsing, auth and the timeout path are the shipped
  code, not a mock of it.

Plus: the in-container model selector (kilo_review_in_container.sh) with
`npm` and `kilo` stubbed on PATH, and structural checks on the workflow.
"""
from __future__ import annotations

import json
import re
import os
import socket
import stat
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO_ROOT / ".github" / "scripts"
_CHAIN = _SCRIPTS / "review_chain.py"
_IN_CONTAINER = _SCRIPTS / "kilo_review_in_container.sh"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "kilocode-review.yml"

STUB_KILO = r'''
import os, sys
out, meta = sys.argv[1], sys.argv[2]
fallback = bool(os.environ.get("KILO_IGNORE_OVERRIDE"))
spec = os.environ["STUB_ALT" if fallback else "STUB_PRIMARY"]
with open(os.environ["STUB_KILO_LOG"], "a") as log:
    log.write(("alt" if fallback else "primary") + "|" + os.environ.get("KILO_EXCLUDE_MODELS", "") + "\n")
kind, _, model = spec.partition(":")
with open(meta, "w") as m:
    if model:
        m.write("model=" + model + "\n")
if kind == "ok":
    open(out, "w").write("1. CORRECTNESS\n- fine\n3. VERDICT: APPROVE - reviewed by " + model + "\n")
    sys.exit(0)
if kind == "empty":
    open(out, "w").write("   \n")
    sys.exit(0)
if kind == "catalog-empty":
    sys.exit(3)
if kind == "no-candidate":
    sys.exit(4)
sys.exit(1)
'''


class _SparkStub:
    """A configurable pmoves.review.v1 server on an ephemeral loopback port."""

    def __init__(self) -> None:
        self.health = (200, {"status": "ready", "contract": "pmoves.review.v1", "model": "spark/local-model"})
        self.review = (200, {"review": "SPARK REVIEW BODY\n3. VERDICT: APPROVE", "model": "spark/local-model", "verdict": "APPROVE"})
        self.requests: list[tuple[str, str, dict | None, str]] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # keep pytest quiet
                pass

            def _send(self, status, body):
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                stub.requests.append(("GET", self.path, None, self.headers.get("Authorization", "")))
                if self.path == "/healthz":
                    self._send(*stub.health)
                else:
                    self._send(404, {"error": "no route"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                stub.requests.append(("POST", self.path, body, self.headers.get("Authorization", "")))
                if self.path == "/v1/review":
                    self._send(*stub.review)
                else:
                    self._send(404, {"error": "no route"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def spark():
    s = _SparkStub()
    yield s
    s.close()


def _closed_port_url() -> str:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


def _run_chain(tmp_path: Path, *, primary: str, alt: str, spark_url: str | None,
               spark_token: str | None = "test-token", extra_env: dict | None = None) -> dict:
    stub = tmp_path / "stub_kilo.py"
    stub.write_text(STUB_KILO)
    (tmp_path / "prompt.md").write_text("review this")
    (tmp_path / "pr.diff").write_text("diff --git a/x b/x\n+hello\n")
    summary, output, log = tmp_path / "summary.md", tmp_path / "output.txt", tmp_path / "kilo.log"
    for p in (summary, output, log):
        p.write_text("")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SPARK_", "KILO_", "GITHUB_"))}
    env.update({
        "REVIEW_KILO_CMD": f"{sys.executable} {stub}",
        "STUB_PRIMARY": primary,
        "STUB_ALT": alt,
        "STUB_KILO_LOG": str(log),
        "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "42",
        "PR_HEAD_SHA": "abc123",
        "SPARK_PROBE_TIMEOUT": "2",
        "SPARK_REVIEW_TIMEOUT": "5",
    })
    if spark_url is not None:
        env["SPARK_REVIEW_URL"] = spark_url
    if spark_token is not None:
        env["SPARK_REVIEW_TOKEN"] = spark_token
    env.update(extra_env or {})
    comment = tmp_path / "comment.md"
    proc = subprocess.run(
        [sys.executable, str(_CHAIN), "--prompt", str(tmp_path / "prompt.md"),
         "--diff", str(tmp_path / "pr.diff"), "--comment", str(comment)],
        env=env, capture_output=True, text=True, timeout=60,
    )
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)
    return {
        "rc": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "comment": comment.read_text() if comment.exists() else "",
        "summary": summary.read_text(),
        "outputs": outputs,
        "kilo_calls": [line.split("|", 1) for line in log.read_text().splitlines()],
    }


def _header(comment: str) -> str:
    return next(line for line in comment.splitlines() if line.startswith("## "))


# ------------------------------------------------------------------ chain --


def test_primary_ok_stops_at_tier_1(tmp_path, spark):
    r = _run_chain(tmp_path, primary="ok:kilo/z-ai/glm-5.2", alt="ok:kilo/z-ai/glm-5.3", spark_url=spark.url)
    assert r["rc"] == 0, r["stdout"] + r["stderr"]
    assert _header(r["comment"]) == "## Fleet review: kilocode (kilo/z-ai/glm-5.2)"
    assert "tier 1/3 `kilo-primary`" in r["comment"]
    assert "reviewed by kilo/z-ai/glm-5.2" in r["comment"]
    assert r["outputs"]["state"] == "REVIEWED" and r["outputs"]["tier"] == "1"
    assert spark.requests == [], "spark must not be probed when the primary reviewed"
    assert [c[0] for c in r["kilo_calls"]] == ["primary"]
    assert "| 2 | `spark-local` | - | **not-reached** |" in r["summary"]


def test_primary_empty_falls_to_spark(tmp_path, spark):
    r = _run_chain(tmp_path, primary="empty:kilo/z-ai/glm-5.2", alt="ok:kilo/z-ai/glm-5.3", spark_url=spark.url)
    assert r["rc"] == 0, r["stdout"] + r["stderr"]
    assert _header(r["comment"]) == "## Fleet review: spark-local (spark/local-model)"
    assert "tier 2/3 `spark-local`" in r["comment"]
    assert "fell back after tier 1 `kilo-primary`: empty" in r["comment"]
    assert "SPARK REVIEW BODY" in r["comment"]
    assert r["outputs"]["reviewer"] == "spark-local" and r["outputs"]["model"] == "spark/local-model"
    assert [c[0] for c in r["kilo_calls"]] == ["primary"], "tier 3 must not run once spark reviewed"
    # health probe first, then an authenticated review call carrying the contract
    assert [(m, p) for m, p, _, _ in spark.requests] == [("GET", "/healthz"), ("POST", "/v1/review")]
    _, _, body, auth = spark.requests[1]
    assert auth == "Bearer test-token"
    assert body["contract"] == "pmoves.review.v1"
    assert body["pr"] == 42 and body["repo"] == "owner/repo" and body["head_sha"] == "abc123"
    assert body["prompt"] == "review this" and "+hello" in body["diff"]
    assert "| 1 | `kilo-primary` | `kilo/z-ai/glm-5.2` | **empty** |" in r["summary"]


def test_primary_empty_spark_offline_falls_to_alternate(tmp_path):
    r = _run_chain(tmp_path, primary="empty:kilo/z-ai/glm-5.2", alt="ok:kilo/z-ai/glm-5.3",
                   spark_url=_closed_port_url())
    assert r["rc"] == 0, r["stdout"] + r["stderr"]
    assert _header(r["comment"]) == "## Fleet review: kilocode-alternate (kilo/z-ai/glm-5.3)"
    assert "tier 3/3 `kilo-alternate`" in r["comment"]
    assert "tier 2 `spark-local`: offline" in r["comment"]
    # the alternate tier ran in fallback mode and was told which model was already tried
    assert r["kilo_calls"] == [["primary", ""], ["alt", "kilo/z-ai/glm-5.2"]]
    assert "**offline**" in r["summary"]


def test_spark_not_configured_is_distinct_from_offline(tmp_path):
    r = _run_chain(tmp_path, primary="fail:kilo/z-ai/glm-5.2", alt="ok:kilo/z-ai/glm-5.3", spark_url=None)
    assert r["rc"] == 0
    assert "| 2 | `spark-local` | - | **not-configured** | SPARK_REVIEW_URL is not set |" in r["summary"]
    assert "offline" not in r["summary"]
    assert _header(r["comment"]) == "## Fleet review: kilocode-alternate (kilo/z-ai/glm-5.3)"


def test_spark_not_ready_is_offline(tmp_path, spark):
    spark.health = (200, {"status": "loading", "contract": "pmoves.review.v1", "model": "m"})
    r = _run_chain(tmp_path, primary="empty:a", alt="ok:b", spark_url=spark.url)
    assert "**offline** | health probe status is 'loading', not 'ready' |" in r["summary"]
    assert [m for m, *_ in spark.requests] == ["GET"], "no review call when not ready"


@pytest.mark.parametrize("health", [
    (503, {"status": "ready", "contract": "pmoves.review.v1"}),
    (200, b"<html>not json</html>"),
    (200, {"status": "ready", "contract": "something.else.v9"}),
])
def test_spark_unparseable_or_wrong_health_is_offline(tmp_path, spark, health):
    spark.health = health
    r = _run_chain(tmp_path, primary="empty:a", alt="ok:b", spark_url=spark.url)
    assert "| 2 | `spark-local` | - | **offline** |" in r["summary"]


def test_spark_ready_without_token_is_misconfigured(tmp_path, spark):
    r = _run_chain(tmp_path, primary="empty:a", alt="ok:b", spark_url=spark.url, spark_token=None)
    assert "**misconfigured** | Spark answered ready but SPARK_REVIEW_TOKEN is not set |" in r["summary"]
    assert [m for m, *_ in spark.requests] == ["GET"]


def test_spark_response_without_model_is_a_contract_failure(tmp_path, spark):
    spark.review = (200, {"review": "text but no model"})
    r = _run_chain(tmp_path, primary="empty:a", alt="ok:b", spark_url=spark.url)
    assert "**failed** | contract violation: review response carries no `model` |" in r["summary"]
    assert _header(r["comment"]) == "## Fleet review: kilocode-alternate (b)"


def test_spark_empty_review_is_empty(tmp_path, spark):
    spark.review = (200, {"review": "  ", "model": "spark/local-model"})
    r = _run_chain(tmp_path, primary="empty:a", alt="ok:b", spark_url=spark.url)
    assert "| 2 | `spark-local` | `spark/local-model` | **empty** |" in r["summary"]


def test_all_fail_is_no_reviewer_available_nonzero(tmp_path, spark):
    spark.review = (500, {"error": "boom"})
    r = _run_chain(tmp_path, primary="empty:kilo/z-ai/glm-5.2", alt="no-candidate", spark_url=spark.url)
    assert r["rc"] == 3, "no reviewer is could-not-measure (3), never a pass"
    assert r["outputs"]["state"] == "NO-REVIEWER-AVAILABLE"
    assert _header(r["comment"]) == "## Fleet review: NO-REVIEWER-AVAILABLE"
    assert "has NOT been reviewed" in r["comment"]
    for needle in ("| 1 | `kilo-primary` | `kilo/z-ai/glm-5.2` | **empty** |",
                   "| 2 | `spark-local` | `spark/local-model` | **failed** | review call returned HTTP 500 |",
                   "| 3 | `kilo-alternate` | - | **unavailable** |"):
        assert needle in r["comment"] and needle in r["summary"]
    assert "::error::NO-REVIEWER-AVAILABLE" in r["stdout"]


def test_catalog_unavailable_skips_alternate(tmp_path):
    r = _run_chain(tmp_path, primary="catalog-empty", alt="ok:never", spark_url=None)
    assert r["rc"] == 3
    assert [c[0] for c in r["kilo_calls"]] == ["primary"], "no second kilo run against a dead catalog"
    assert "skipped: the kilo catalog was unavailable in tier 1" in r["summary"]


def test_spark_endpoint_never_leaks_into_outputs(tmp_path):
    url = _closed_port_url() + "/secret-path-marker"
    r = _run_chain(tmp_path, primary="empty:a", alt="no-candidate", spark_url=url, spark_token="tok-SECRET-marker")
    blob = r["comment"] + r["summary"] + r["stdout"] + r["stderr"]
    assert "secret-path-marker" not in blob
    assert "tok-SECRET-marker" not in blob
    assert "**offline**" in r["summary"]


def test_chain_survives_stripped_docstrings(tmp_path):
    """`python -OO` / PYTHONOPTIMIZE=2 makes __doc__ None. The chain once built
    its argparse description from __doc__, so under -OO it crashed before any
    tier ran -- and downstream that reads as "no reviewer", not as a bug."""
    r = _run_chain(tmp_path, primary="ok:kilo/z-ai/glm-5.2", alt="ok:b", spark_url=None,
                   extra_env={"PYTHONOPTIMIZE": "2"})
    assert r["rc"] == 0, r["stderr"]
    assert _header(r["comment"]) == "## Fleet review: kilocode (kilo/z-ai/glm-5.2)"


def test_missing_inputs_is_usage_error(tmp_path):
    proc = subprocess.run([sys.executable, str(_CHAIN), "--prompt", str(tmp_path / "nope"),
                           "--diff", str(tmp_path / "nope"), "--comment", str(tmp_path / "c.md")],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2


# --------------------------------------------- in-container model selector --


def _exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def selector_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _exe(bindir / "npm", "#!/usr/bin/env bash\nexit 0\n")
    catalog = tmp_path / "catalog-source.txt"
    catalog.write_text("kilo/z-ai/glm-5.2\nkilo/z-ai/glm-5.3\nkilo/qwen/qwen3-coder-next\n")
    _exe(bindir / "kilo", f"""#!/usr/bin/env bash
if [ "$1" = models ]; then cat "{catalog}"; exit 0; fi
if [ "$1" = run ]; then echo "REVIEW with $(cat "$HOME/.config/kilo/kilo.json")"; exit 0; fi
exit 9
""")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("p")
    home = tmp_path / "home"
    home.mkdir()
    base = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(home),
        "REVIEW_PROMPT": str(prompt),
        "KILO_CATALOG_FILE": str(tmp_path / "catalog.txt"),
        "KILO_REVIEW_MODEL_PREFERENCES": "kilo/z-ai/glm-5.9 kilo/z-ai/glm-5.2 kilo/z-ai/glm-5.3",
    }
    return base, catalog


def _select(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(_IN_CONTAINER)], env=env, capture_output=True, text=True, timeout=30)


def test_selector_primary_takes_first_catalog_hit(selector_env):
    env, _ = selector_env
    p = _select(env)
    assert p.returncode == 0, p.stderr
    assert "KILO_RESOLVED_MODEL=kilo/z-ai/glm-5.2" in p.stderr
    assert '"model": "kilo/z-ai/glm-5.2"' in p.stdout


def test_selector_fallback_skips_tried_model_and_ignores_override(selector_env):
    env, _ = selector_env
    p = _select({**env, "KILO_REVIEW_MODEL": "kilo/z-ai/glm-5.2", "KILO_IGNORE_OVERRIDE": "1",
                 "KILO_EXCLUDE_MODELS": "kilo/z-ai/glm-5.2"})
    assert p.returncode == 0, p.stderr
    assert "KILO_RESOLVED_MODEL=kilo/z-ai/glm-5.3" in p.stderr


def test_selector_fallback_exhausted_exits_4(selector_env):
    env, _ = selector_env
    p = _select({**env, "KILO_IGNORE_OVERRIDE": "1",
                 "KILO_EXCLUDE_MODELS": "kilo/z-ai/glm-5.2 kilo/z-ai/glm-5.3"})
    assert p.returncode == 4, p.stderr


def test_selector_primary_dead_override_still_errors_loudly(selector_env):
    env, _ = selector_env
    p = _select({**env, "KILO_REVIEW_MODEL": "kilo/nope/nope"})
    assert p.returncode == 1
    assert "::error::KILO_REVIEW_MODEL='kilo/nope/nope' is not in the live kilo catalog" in p.stderr


def test_selector_empty_catalog_is_could_not_measure(selector_env):
    env, catalog = selector_env
    catalog.write_text("")
    p = _select(env)
    assert p.returncode == 3


# ------------------------------------------------------------- workflow --


def _job() -> dict:
    wf = yaml.safe_load(_WORKFLOW.read_text())
    return wf["jobs"]["kilo-review"]


def test_workflow_spark_endpoint_is_secret_not_variable_or_literal():
    text = _WORKFLOW.read_text()
    chain = next(s for s in _job()["steps"] if s.get("id") == "chain")
    assert chain["env"]["SPARK_REVIEW_URL"] == "${{ secrets.SPARK_REVIEW_URL }}"
    assert chain["env"]["SPARK_REVIEW_TOKEN"] == "${{ secrets.SPARK_REVIEW_TOKEN }}"
    assert "vars.SPARK_REVIEW_URL" not in text
    # no literal endpoint of any kind in the chain step: the repo is public
    assert not any("://" in str(v) for v in chain["env"].values())
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text), "no IP literals in the workflow"


def test_workflow_runs_chain_then_posts_then_fails_on_no_reviewer():
    steps = _job()["steps"]
    names = [s.get("name", "") for s in steps]
    i_chain = next(i for i, s in enumerate(steps) if s.get("id") == "chain")
    i_post = names.index("Post review comment")
    i_fail = names.index("Fail on NO-REVIEWER-AVAILABLE")
    assert i_chain < i_post < i_fail
    assert ".github/scripts/review_chain.py" in steps[i_chain]["run"]
    # the post + fail steps must run even when the chain reports no reviewer
    assert steps[i_post]["if"].startswith("always()")
    assert steps[i_fail]["if"].startswith("always()")
    assert 'exit 3' in steps[i_fail]["run"] and 'REVIEWED' in steps[i_fail]["run"]


# ------------------------------------------- host-side kilo tier wrapper --

_TIER = _SCRIPTS / "kilo_review_tier.sh"


@pytest.fixture
def tier_env(tmp_path):
    """kilo_review_tier.sh with `sudo` stubbed: `sudo -n docker run ...` plays
    the container per STUB_DOCKER, `sudo -n docker rm -f` is logged."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "sudo.log"
    calls.write_text("")
    _exe(bindir / "sudo", f"""#!/usr/bin/env bash
echo "$*" >> "{calls}"
[ "$3" = rm ] && exit 0
echo "::notice::kilo catalog: 3 ids" >&2
case "$STUB_DOCKER" in
  ok)    echo "KILO_RESOLVED_MODEL=kilo/z-ai/glm-5.2" >&2; echo "THE REVIEW" ;;
  empty) echo "KILO_RESOLVED_MODEL=kilo/z-ai/glm-5.2" >&2 ;;
  fail)  echo "KILO_RESOLVED_MODEL=kilo/z-ai/glm-5.2" >&2; echo "boom" >&2; exit 1 ;;
  hang)  echo "KILO_RESOLVED_MODEL=kilo/z-ai/glm-5.2" >&2; sleep 10 ;;
esac
""")
    (tmp_path / "d").write_text("diff")
    (tmp_path / "p").write_text("prompt")
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}",
           "REVIEW_DIFF": str(tmp_path / "d"), "REVIEW_PROMPT": str(tmp_path / "p")}
    return env, tmp_path, calls


def _tier(env, tmp_path, mode, **extra):
    out, meta = tmp_path / "out.md", tmp_path / "meta.txt"
    p = subprocess.run(["bash", str(_TIER), str(out), str(meta)], env={**env, "STUB_DOCKER": mode, **extra},
                       capture_output=True, text=True, timeout=60)
    return p, out.read_text(), dict(l.split("=", 1) for l in meta.read_text().splitlines() if "=" in l)


def test_tier_wrapper_ok_records_model(tier_env):
    env, tmp_path, _ = tier_env
    p, out, meta = _tier(env, tmp_path, "ok")
    assert p.returncode == 0 and out.strip() == "THE REVIEW"
    assert meta["model"] == "kilo/z-ai/glm-5.2" and meta["rc"] == "0"
    assert "::notice::kilo catalog: 3 ids" in p.stdout, "annotations must be replayed into the runner log"


def test_tier_wrapper_failure_keeps_rc_and_reason(tier_env):
    env, tmp_path, _ = tier_env
    p, out, meta = _tier(env, tmp_path, "fail")
    assert p.returncode == 1 and meta["reason"] == "kilo run failed (exit 1)"


def test_tier_wrapper_empty_is_rc0_with_empty_output(tier_env):
    env, tmp_path, _ = tier_env
    p, out, meta = _tier(env, tmp_path, "empty")
    assert p.returncode == 0 and out.strip() == ""


def test_tier_wrapper_timeout_kills_the_container(tier_env):
    env, tmp_path, calls = tier_env
    p, out, meta = _tier(env, tmp_path, "hang", KILO_TIER_TIMEOUT="1")
    assert p.returncode == 124
    assert meta["reason"] == "timed out after 1s"
    assert any(line.startswith("-n docker rm -f kilo-review-") for line in calls.read_text().splitlines())
