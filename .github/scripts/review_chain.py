#!/usr/bin/env python3
"""Fleet PR review fallback chain (kilocode-review.yml).

Tries reviewers in order and stops at the first one that produces a VALID
review (see "Review validity" below):

  tier 1  kilo-primary    Kilo CLI, model resolved against the live catalog
  tier 2  spark-local     Spark local-model reviewer, ONLY if its health probe
                          answers ready (endpoint from the SPARK_REVIEW_URL
                          secret -- never a literal host in this repo)
  tier 3  kilo-alternate  Kilo CLI again, with the next untried catalog-valid
                          model from the preference list

Outputs (all written, whatever happens), every one passed through the
redactor (Spark URL, host, port, token; Kilo key):
  --comment FILE   the PR comment body. Its header names the tier and model
                   that ACTUALLY produced the review.
  $GITHUB_STEP_SUMMARY  a table of every tier tried and its outcome.
  $GITHUB_OUTPUT   state=, tier=, reviewer=, model=, rc=

Exit codes (fleet doctrine: 0 clean / 1 findings / 3 could-not-measure):
  0  a review was produced (possibly by a fallback tier)
  3  NO-REVIEWER-AVAILABLE -- every tier failed or was unavailable. This is
     could-not-measure, never a pass. The comment still lists each tier and why.
  2  usage error (missing input files)

Tier outcomes are deliberately distinct: `not-configured` (SPARK_REVIEW_URL
unset) is not `offline` (configured, probe did not answer ready), and neither
is `misconfigured` (http:// without opt-in, a redirect, no token), `failed`
(the review call broke), `empty` (nothing) or `invalid` (text that is not a
review).

Review validity: at least MIN_REVIEW_CHARS of text containing the three
section markers the prompt asks for (CORRECTNESS, SECURITY, VERDICT) and an
allowed verdict (APPROVE / REQUEST_CHANGES) within VERDICT_WINDOW chars after
the last VERDICT marker. The verdict may sit on the marker line
("3. VERDICT: APPROVE") or under a "## 3. VERDICT" heading on the next line --
the live Kilo review on #3169 used the latter, so a strict `VERDICT:` line
match would have rejected a real, good review.

Spark contract (pmoves.review.v1) -- implemented on Spark by the Crush-Spark
lane, NOT here:
  GET  {SPARK_REVIEW_URL}/healthz
       200 {"status": "ready", "contract": "pmoves.review.v1", "model": "<id>"}
       Anything else (timeout, non-200, non-JSON, status != ready, other
       contract) is `offline`. A 3xx is `misconfigured` and is NEVER followed.
  POST {SPARK_REVIEW_URL}/v1/review   Authorization: Bearer <SPARK_REVIEW_TOKEN>
       {"contract": "pmoves.review.v1", "repo": "o/r", "pr": 123,
        "head_sha": "<sha>", "prompt": "<text>", "diff": "<unified diff>"}
       200 {"review": "<markdown>", "model": "<id actually used>",
            "verdict": "APPROVE" | "REQUEST_CHANGES" | "UNKNOWN"}
       A response without `model` is a contract violation (`failed`): the
       posted header must name the model, and we do not guess it.
  SPARK_REVIEW_URL must be https:// unless SPARK_REVIEW_ALLOW_HTTP=1 (then a
  loud warning: the bearer token is sent without TLS). Redirects are refused,
  so the token only ever reaches the configured origin. Each call has a
  WALL-CLOCK deadline covering DNS, connect and body.

Time budget (defaults; the job's timeout-minutes is 45 = 2700s):
  tier 1  KILO_TIER_TIMEOUT 720 + 15 kill-after              =  735s
  tier 2  SPARK_PROBE_TIMEOUT 5 + SPARK_REVIEW_TIMEOUT 480   =  485s
  tier 3  720 + 15                                           =  735s
  worst case                                                 = 1955s (32.6 min)
  REVIEW_CHAIN_BUDGET (2100s) skips tier 3 if it could not finish inside the
  budget, leaving >= 10 min of the job for checkout, posting and cleanup.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONTRACT = "pmoves.review.v1"
NO_REVIEWER = "NO-REVIEWER-AVAILABLE"
TIER_COUNT = 3
MAX_REVIEW_CHARS = 60000  # GitHub caps a comment body at 65536 chars
MIN_REVIEW_CHARS = 80
VERDICT_WINDOW = 200
MODEL_MAX_CHARS = 120

OK = "ok"
EMPTY = "empty"
INVALID = "invalid"
FAILED = "failed"
OFFLINE = "offline"
NOT_CONFIGURED = "not-configured"
MISCONFIGURED = "misconfigured"
UNAVAILABLE = "unavailable"
NOT_REACHED = "not-reached"


@dataclasses.dataclass
class TierResult:
    index: int
    name: str
    label: str
    outcome: str = NOT_REACHED
    model: str = ""
    detail: str = ""
    review: str = ""
    status: str = ""


# ---------------------------------------------------------------- hygiene --


class Redactor:
    """Strip secrets and topology from every string we emit.

    Built from SPARK_REVIEW_URL (full URL, netloc, bare host or IP, the host's
    first DNS label, port) plus secret values (Spark token, Kilo key).
    Case-insensitive; over-redaction is the safe failure.
    """

    def __init__(self, *, url: str = "", secrets: tuple[str, ...] = ()) -> None:
        literals: set[str] = {s for s in secrets if s}
        self._port_re: re.Pattern[str] | None = None
        url = url.strip()
        if url:
            literals |= {url, url.rstrip("/")}
            host, netloc, port = "", "", None
            try:
                parts = urllib.parse.urlsplit(url)
                host, netloc = parts.hostname or "", parts.netloc
                port = parts.port
            except ValueError:
                pass
            if netloc:
                literals.add(netloc)
            if host:
                literals.add(host)
                first = host.split(".")[0]
                if len(first) >= 4 and not first.isdigit():
                    literals.add(first)
            if port:
                self._port_re = re.compile(rf"(?<![\w.]){port}(?!\w)")
        self._literals = sorted(literals, key=len, reverse=True)

    def __call__(self, text: str) -> str:
        for s in self._literals:
            text = re.sub(re.escape(s), "<redacted>", text, flags=re.IGNORECASE)
        if self._port_re is not None:
            text = self._port_re.sub("<redacted>", text)
        return text


def redactor_from_env() -> Redactor:
    return Redactor(
        url=os.environ.get("SPARK_REVIEW_URL", ""),
        secrets=tuple(os.environ.get(k, "").strip() for k in
                      ("SPARK_REVIEW_TOKEN", "KILOCODE_API_KEY", "KILO_API_KEY")),
    )


def sanitize_model(raw: object) -> str:
    """One line, no control/format characters, no backticks, <= 120 chars.

    The model id is echoed into $GITHUB_OUTPUT, a markdown header and a
    ::warning:: line; a newline would inject keys or workflow commands.
    """
    lines = str(raw or "").splitlines()
    text = lines[0] if lines else ""
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))
    return text.replace("`", "'").strip()[:MODEL_MAX_CHARS]


def review_validity(text: str) -> tuple[bool, str]:
    body = (text or "").strip()
    if not body:
        return False, "empty"
    if len(body) < MIN_REVIEW_CHARS:
        return False, f"only {len(body)} chars (minimum {MIN_REVIEW_CHARS})"
    upper = body.upper()
    missing = [m for m in ("CORRECTNESS", "SECURITY", "VERDICT") if m not in upper]
    if missing:
        return False, "missing required section(s): " + ", ".join(missing)
    tail = upper[upper.rindex("VERDICT") + len("VERDICT"):][:VERDICT_WINDOW]
    if not re.search(r"(?<![A-Z_])(APPROVE|REQUEST_CHANGES)(?![A-Z_])", tail):
        return False, "no APPROVE / REQUEST_CHANGES verdict after the VERDICT marker (truncated?)"
    return True, "review produced"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _read_meta(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip()] = v.strip()
    return meta


def _accept(result: TierResult, review: str) -> TierResult:
    ok, why = review_validity(review)
    if ok:
        result.outcome, result.review, result.detail = OK, review, why
    elif why == "empty":
        result.outcome = EMPTY
        result.detail = f"produced no review output (model '{result.model or 'unresolved'}')"
    else:
        result.outcome, result.detail = INVALID, f"output is not a review: {why}"
    return result


# --------------------------------------------------------------------- kilo --


def run_kilo_tier(result: TierResult, *, exclude: list[str], fallback: bool) -> TierResult:
    cmd = shlex.split(
        os.environ.get("REVIEW_KILO_CMD")
        or f"bash {Path(__file__).resolve().parent / 'kilo_review_tier.sh'}"
    )
    env = dict(os.environ)
    env["KILO_EXCLUDE_MODELS"] = " ".join(exclude)
    if fallback:
        env["KILO_IGNORE_OVERRIDE"] = "1"
    else:
        env.pop("KILO_IGNORE_OVERRIDE", None)
    timeout = _env_float("KILO_TIER_TIMEOUT", 720) + 60
    with tempfile.TemporaryDirectory(prefix="review-chain-") as td:
        out, meta_path = Path(td) / "review.md", Path(td) / "meta.txt"
        rc: int | None
        try:
            rc = subprocess.run(cmd + [str(out), str(meta_path)], env=env, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc = None
        except OSError as exc:
            result.outcome, result.detail = FAILED, f"could not start kilo tier: {type(exc).__name__}"
            return result
        meta = _read_meta(meta_path)
        review = out.read_text(errors="replace") if out.exists() else ""
    result.model = sanitize_model(meta.get("model", ""))
    # Tier status travels in the meta file, NOT in reserved exit codes: those
    # would collide with kilo's own exit codes.
    result.status = meta.get("status", "")
    reason = meta.get("reason", "")
    if result.status == "catalog-empty":
        result.outcome = UNAVAILABLE
        result.detail = reason or "kilo catalog returned 0 ids (could-not-measure)"
    elif result.status == "no-candidate":
        result.outcome = UNAVAILABLE
        result.detail = reason or "no untried catalog-valid model left"
    elif result.status == "timeout" or rc is None:
        result.outcome, result.detail = FAILED, reason or "timed out"
    elif rc == 0:
        _accept(result, review)
    else:
        result.outcome, result.detail = FAILED, reason or f"kilo run failed (exit {rc})"
    return result


# -------------------------------------------------------------------- spark --


class _RedirectRefused(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"redirect (HTTP {code}) refused")
        self.code = code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow: a followed redirect would carry Authorization elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise _RedirectRefused(code)


_OPENER = urllib.request.build_opener(_NoRedirect)


def _opener_open(req: urllib.request.Request, timeout: float):
    return _OPENER.open(req, timeout=timeout)


def _http_json(req: urllib.request.Request, deadline: float) -> tuple[int, object]:
    """One request under a WALL-CLOCK deadline (DNS, connect, body).

    Returns (status, parsed-json-or-None). Raises TimeoutError past the
    deadline, _RedirectRefused on any 3xx, and re-raises whatever else the
    request raised (URLError, OSError, http.client.HTTPException, ssl ...).
    """
    box: dict[str, object] = {}

    def work() -> None:
        try:
            try:
                with _opener_open(req, deadline) as resp:
                    box["status"], box["raw"] = resp.status, resp.read()
            except urllib.error.HTTPError as exc:
                if 300 <= exc.code < 400:
                    raise _RedirectRefused(exc.code) from None
                box["status"], box["raw"] = exc.code, b""
        except BaseException as exc:  # handed to the caller, never swallowed
            box["error"] = exc

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(deadline)
    if t.is_alive():
        raise TimeoutError(f"no complete answer within {deadline:g}s")
    err = box.get("error")
    if isinstance(err, BaseException):
        raise err
    status = int(str(box.get("status")))
    raw = box.get("raw")
    if not isinstance(raw, bytes) or not raw:
        return status, None
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, None


def _describe(exc: BaseException) -> str:
    reason = getattr(exc, "reason", None)
    return f"{type(exc).__name__}: {reason if reason is not None else exc}"


def run_spark_tier(result: TierResult, *, prompt: str, diff: str) -> TierResult:
    url = os.environ.get("SPARK_REVIEW_URL", "").strip()
    token = os.environ.get("SPARK_REVIEW_TOKEN", "").strip()
    if not url:
        result.outcome, result.detail = NOT_CONFIGURED, "SPARK_REVIEW_URL is not set"
        return result
    try:
        parts = urllib.parse.urlsplit(url)
        _ = parts.port  # raises ValueError on a malformed port
    except ValueError:
        result.outcome, result.detail = MISCONFIGURED, "SPARK_REVIEW_URL does not parse as a URL"
        return result
    if parts.scheme == "http":
        if os.environ.get("SPARK_REVIEW_ALLOW_HTTP", "") != "1":
            result.outcome = MISCONFIGURED
            result.detail = ("SPARK_REVIEW_URL is http:// - the bearer token would be sent without TLS; "
                             "use https:// or set SPARK_REVIEW_ALLOW_HTTP=1 explicitly")
            return result
        emit("::warning::SPARK_REVIEW_URL is http:// and SPARK_REVIEW_ALLOW_HTTP=1 is set - "
             "the Spark bearer token is sent WITHOUT TLS (acceptable only inside an encrypted tailnet)")
    elif parts.scheme != "https":
        result.outcome, result.detail = MISCONFIGURED, "SPARK_REVIEW_URL is not an http(s) URL"
        return result
    if not parts.hostname:
        result.outcome, result.detail = MISCONFIGURED, "SPARK_REVIEW_URL has no host"
        return result
    base = url.rstrip("/")
    origin = (parts.scheme, parts.netloc)

    def request(path: str, **kw) -> urllib.request.Request:
        req = urllib.request.Request(f"{base}{path}", **kw)
        target = urllib.parse.urlsplit(req.full_url)
        # Authorization only ever goes to the configured origin.
        if (target.scheme, target.netloc) != origin:
            raise RuntimeError("request escaped the configured origin")
        return req

    probe_timeout = _env_float("SPARK_PROBE_TIMEOUT", 5)
    try:
        status, body = _http_json(request("/healthz"), probe_timeout)
    except _RedirectRefused as exc:
        result.outcome = MISCONFIGURED
        result.detail = f"health probe answered a redirect (HTTP {exc.code}); redirects are never followed"
        return result
    except Exception as exc:  # URLError, OSError, HTTPException, ssl, timeout ...
        result.outcome = OFFLINE
        result.detail = f"health probe did not answer ready within {probe_timeout:g}s ({_describe(exc)})"
        return result
    if status != 200:
        result.outcome, result.detail = OFFLINE, f"health probe returned HTTP {status}"
        return result
    if not isinstance(body, dict):
        result.outcome, result.detail = OFFLINE, "health probe returned a non-JSON body"
        return result
    if body.get("contract") != CONTRACT:
        result.outcome = OFFLINE
        result.detail = f"health probe contract is {sanitize_model(body.get('contract'))!r}, expected {CONTRACT!r}"
        return result
    if body.get("status") != "ready":
        result.outcome = OFFLINE
        result.detail = f"health probe status is {sanitize_model(body.get('status'))!r}, not 'ready'"
        return result
    result.model = sanitize_model(body.get("model"))
    if not token:
        result.outcome = MISCONFIGURED
        result.detail = "Spark answered ready but SPARK_REVIEW_TOKEN is not set"
        return result

    pr = os.environ.get("PR_NUMBER", "")
    payload = {
        "contract": CONTRACT,
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "pr": int(pr) if pr.isdigit() else None,
        "head_sha": os.environ.get("PR_HEAD_SHA", ""),
        "prompt": prompt,
        "diff": diff,
    }
    req = request(
        "/v1/review",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    review_timeout = _env_float("SPARK_REVIEW_TIMEOUT", 480)
    try:
        status, resp = _http_json(req, review_timeout)
    except _RedirectRefused as exc:
        result.outcome = MISCONFIGURED
        result.detail = f"review call answered a redirect (HTTP {exc.code}); not followed, token not forwarded"
        return result
    except Exception as exc:
        result.outcome, result.detail = FAILED, f"review call failed ({_describe(exc)})"
        return result
    if status != 200 or not isinstance(resp, dict):
        result.outcome = FAILED
        result.detail = f"review call returned HTTP {status}" + (" with a non-JSON body" if status == 200 else "")
        return result
    model = sanitize_model(resp.get("model"))
    if not model:
        result.outcome = FAILED
        result.detail = "contract violation: review response carries no `model`"
        return result
    result.model = model
    review = resp.get("review")
    return _accept(result, review if isinstance(review, str) else "")


# ------------------------------------------------------------------ outputs --

_REDACT = Redactor()


def emit(line: str) -> None:
    print(_REDACT(line), flush=True)


def _row(r: TierResult) -> str:
    detail = r.detail.replace("|", "\\|").replace("\n", " ")
    return f"| {r.index} | `{r.name}` | {('`' + r.model + '`') if r.model else '-'} | **{r.outcome}** | {detail} |"


def tier_table(results: list[TierResult]) -> str:
    lines = ["| tier | reviewer | model | outcome | detail |", "|---|---|---|---|---|"]
    lines += [_row(r) for r in results]
    return "\n".join(lines)


def render_comment(results: list[TierResult], winner: TierResult | None) -> str:
    table = tier_table(results)
    if winner is None:
        return "\n".join([
            f"<!-- fleet-review-chain state={NO_REVIEWER} -->",
            f"## Fleet review: {NO_REVIEWER}",
            "",
            "Every reviewer tier failed or was unavailable, so **this PR has NOT been reviewed** "
            "by the fleet lane. This is could-not-measure, not a pass.",
            "",
            table,
            "",
            "_ lane: fleet-review chain (self-hosted kvm4) - kilo-primary -> spark-local -> kilo-alternate _",
        ]) + "\n"
    review = winner.review.strip()
    if len(review) > MAX_REVIEW_CHARS:
        review = review[:MAX_REVIEW_CHARS] + "\n\n_[review truncated to fit a GitHub comment]_"
    earlier = [r for r in results if r.index < winner.index]
    fell_back = "; ".join(f"tier {r.index} `{r.name}`: {r.outcome}" for r in earlier)
    provenance = f"reviewer: tier {winner.index}/{TIER_COUNT} `{winner.name}` - model `{winner.model}`"
    if fell_back:
        provenance += f" - fell back after {fell_back}"
    parts = [
        f"<!-- fleet-review-chain state=REVIEWED tier={winner.index} reviewer={winner.name} -->",
        f"## Fleet review: {winner.label} ({winner.model})",
        f"<sub>{provenance}</sub>",
        "",
        review,
        "",
    ]
    if earlier:
        parts += ["<details><summary>reviewer chain</summary>", "", table, "", "</details>", ""]
    parts.append("_ lane: fleet-review chain (self-hosted kvm4) - kilo-primary -> spark-local -> kilo-alternate _")
    return "\n".join(parts) + "\n"


def _append(path_env: str, text: str) -> None:
    path = os.environ.get(path_env)
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_REDACT(text))


def run_chain(prompt: str, diff: str) -> tuple[list[TierResult], TierResult | None]:
    started = time.monotonic()
    budget = _env_float("REVIEW_CHAIN_BUDGET", 2100)
    results = [
        TierResult(1, "kilo-primary", "kilocode"),
        TierResult(2, "spark-local", "spark-local"),
        TierResult(3, "kilo-alternate", "kilocode-alternate"),
    ]
    primary, spark, alternate = results

    run_kilo_tier(primary, exclude=[], fallback=False)
    if primary.outcome == OK:
        return results, primary
    emit(f"::warning::review tier 1 kilo-primary: {primary.outcome} - {primary.detail}; trying spark-local")

    run_spark_tier(spark, prompt=prompt, diff=diff)
    if spark.outcome == OK:
        return results, spark
    emit(f"::warning::review tier 2 spark-local: {spark.outcome} - {spark.detail}; trying kilo-alternate")

    needed = _env_float("KILO_TIER_TIMEOUT", 720) + 15
    elapsed = time.monotonic() - started
    if primary.status == "catalog-empty":
        alternate.outcome = UNAVAILABLE
        alternate.detail = "skipped: the kilo catalog was unavailable in tier 1"
    elif elapsed + needed > budget:
        alternate.outcome = UNAVAILABLE
        alternate.detail = (f"skipped: {elapsed:.0f}s used, the tier needs up to {needed:.0f}s, "
                            f"REVIEW_CHAIN_BUDGET is {budget:.0f}s")
    else:
        run_kilo_tier(alternate, exclude=[primary.model] if primary.model else [], fallback=True)
    if alternate.outcome == OK:
        return results, alternate
    return results, None


def main(argv: list[str] | None = None) -> int:
    global _REDACT
    _REDACT = redactor_from_env()
    # Not __doc__: it is None under `python -OO` / PYTHONOPTIMIZE=2, and a
    # crash here would read downstream as "no reviewer" rather than a bug.
    ap = argparse.ArgumentParser(description="Fleet PR review fallback chain (kilo -> spark -> kilo-alt).")
    ap.add_argument("--prompt", default="/tmp/kilo-review-prompt.md")
    ap.add_argument("--diff", default="/tmp/kilo-review.diff")
    ap.add_argument("--comment", default="/tmp/review-comment.md")
    args = ap.parse_args(argv)

    try:
        prompt = Path(args.prompt).read_text(errors="replace")
        diff = Path(args.diff).read_text(errors="replace")
    except OSError as exc:
        emit(f"::error::review chain: cannot read inputs ({exc})")
        return 2

    results, winner = run_chain(prompt, diff)
    Path(args.comment).write_text(_REDACT(render_comment(results, winner)), encoding="utf-8")

    state = "REVIEWED" if winner else NO_REVIEWER
    rc = 0 if winner else 3
    summary = [f"## Fleet review chain: {state}", ""]
    if winner:
        summary.append(f"Review produced by tier {winner.index} `{winner.name}` with model `{winner.model}`.")
    else:
        summary.append("No tier produced a review. This PR is NOT reviewed by the fleet lane (could-not-measure).")
    summary += ["", tier_table(results), ""]
    _append("GITHUB_STEP_SUMMARY", "\n".join(summary) + "\n")
    _append("GITHUB_OUTPUT", "".join([
        f"state={state}\n",
        f"tier={winner.index if winner else ''}\n",
        f"reviewer={winner.name if winner else ''}\n",
        f"model={winner.model if winner else ''}\n",
        f"rc={rc}\n",
    ]))
    for r in results:
        emit(f"review tier {r.index} {r.name}: {r.outcome}" + (f" [{r.model}]" if r.model else "") + f" - {r.detail}")
    if winner:
        if winner.index > 1:
            emit(f"::warning::fleet review produced by FALLBACK tier {winner.index} {winner.name} ({winner.model})")
        else:
            emit(f"::notice::fleet review produced by tier 1 kilo-primary ({winner.model})")
    else:
        emit(f"::error::{NO_REVIEWER}: every review tier failed or was unavailable - see the job summary")
    return rc


if __name__ == "__main__":
    sys.exit(main())
