#!/usr/bin/env python3
"""Fleet PR review fallback chain (kilocode-review.yml).

Tries reviewers in order and stops at the first one that produces a non-empty
review:

  tier 1  kilo-primary    Kilo CLI, model resolved against the live catalog
  tier 2  spark-local     Spark local-model reviewer, ONLY if its health probe
                          answers ready (endpoint from the SPARK_REVIEW_URL
                          secret -- never a literal host in this repo)
  tier 3  kilo-alternate  Kilo CLI again, with the next untried catalog-valid
                          model from the preference list

Outputs (all written, whatever happens):
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
is `failed` (reachable, but the review call broke) or `empty` (the reviewer
answered with nothing).

Spark contract (pmoves.review.v1) -- implemented on Spark by the Crush-Spark
lane, NOT here:
  GET  {SPARK_REVIEW_URL}/healthz
       200 {"status": "ready", "contract": "pmoves.review.v1", "model": "<id>"}
       Anything else (timeout, non-200, non-JSON, status != ready, other
       contract) is `offline`.
  POST {SPARK_REVIEW_URL}/v1/review   Authorization: Bearer <SPARK_REVIEW_TOKEN>
       {"contract": "pmoves.review.v1", "repo": "o/r", "pr": 123,
        "head_sha": "<sha>", "prompt": "<text>", "diff": "<unified diff>"}
       200 {"review": "<markdown>", "model": "<id actually used>",
            "verdict": "APPROVE" | "REQUEST_CHANGES" | "UNKNOWN"}
       A response without `model` is a contract violation (`failed`): the
       posted header must name the model, and we do not guess it.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

CONTRACT = "pmoves.review.v1"
NO_REVIEWER = "NO-REVIEWER-AVAILABLE"
TIER_COUNT = 3
MAX_REVIEW_CHARS = 60000  # GitHub caps a comment body at 65536 chars

OK = "ok"
EMPTY = "empty"
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
    rc: int | None = None


class Redactor:
    """Keep the Spark endpoint and token out of every string we emit."""

    def __init__(self, *secrets: str) -> None:
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)

    def __call__(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "<redacted>")
        return text


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
    timeout = _env_float("KILO_TIER_TIMEOUT", 900) + 60
    with tempfile.TemporaryDirectory(prefix="review-chain-") as td:
        out, meta_path = Path(td) / "review.md", Path(td) / "meta.txt"
        try:
            proc = subprocess.run(cmd + [str(out), str(meta_path)], env=env, timeout=timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = 124
        except OSError as exc:
            result.outcome, result.detail = FAILED, f"could not start kilo tier: {type(exc).__name__}"
            return result
        meta = _read_meta(meta_path)
        review = out.read_text(errors="replace") if out.exists() else ""
    result.rc = rc
    result.model = meta.get("model", "")
    reason = meta.get("reason", "")
    if rc == 0 and review.strip():
        result.outcome, result.review = OK, review
        result.detail = "review produced"
    elif rc == 0:
        result.outcome = EMPTY
        result.detail = f"exited 0 but produced no review output (model '{result.model or 'unresolved'}')"
    elif rc == 3:
        result.outcome = UNAVAILABLE
        result.detail = reason or "kilo catalog returned 0 ids (could-not-measure)"
    elif rc == 4:
        result.outcome = UNAVAILABLE
        result.detail = reason or "no untried catalog-valid model left"
    elif rc == 124:
        result.outcome = FAILED
        result.detail = reason or "timed out"
    else:
        result.outcome = FAILED
        result.detail = reason or f"kilo run failed (exit {rc})"
    return result


# -------------------------------------------------------------------- spark --


def _http_json(req: urllib.request.Request, timeout: float) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, None
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, None


def run_spark_tier(result: TierResult, *, prompt: str, diff: str) -> TierResult:
    url = os.environ.get("SPARK_REVIEW_URL", "").strip()
    token = os.environ.get("SPARK_REVIEW_TOKEN", "").strip()
    redact = Redactor(url, url.rstrip("/"), token)
    if not url:
        result.outcome, result.detail = NOT_CONFIGURED, "SPARK_REVIEW_URL is not set"
        return result
    if not url.startswith(("http://", "https://")):
        result.outcome, result.detail = MISCONFIGURED, "SPARK_REVIEW_URL is not an http(s) URL"
        return result
    base = url.rstrip("/")

    # Probe: a real health route, a parseable ready status, a short timeout.
    probe_timeout = _env_float("SPARK_PROBE_TIMEOUT", 5)
    try:
        status, body = _http_json(urllib.request.Request(f"{base}/healthz"), probe_timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        result.outcome = OFFLINE
        result.detail = redact(f"health probe did not answer within {probe_timeout:g}s ({type(exc).__name__}: {reason})")
        return result
    if status != 200:
        result.outcome, result.detail = OFFLINE, f"health probe returned HTTP {status}"
        return result
    if not isinstance(body, dict):
        result.outcome, result.detail = OFFLINE, "health probe returned a non-JSON body"
        return result
    if body.get("contract") != CONTRACT:
        result.outcome = OFFLINE
        result.detail = redact(f"health probe contract is {body.get('contract')!r}, expected {CONTRACT!r}")
        return result
    if body.get("status") != "ready":
        result.outcome = OFFLINE
        result.detail = redact(f"health probe status is {body.get('status')!r}, not 'ready'")
        return result
    health_model = str(body.get("model") or "")
    if not token:
        result.outcome = MISCONFIGURED
        result.detail = "Spark answered ready but SPARK_REVIEW_TOKEN is not set"
        result.model = health_model
        return result

    payload = {
        "contract": CONTRACT,
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "pr": int(os.environ["PR_NUMBER"]) if os.environ.get("PR_NUMBER", "").isdigit() else None,
        "head_sha": os.environ.get("PR_HEAD_SHA", ""),
        "prompt": prompt,
        "diff": diff,
    }
    req = urllib.request.Request(
        f"{base}/v1/review",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    review_timeout = _env_float("SPARK_REVIEW_TIMEOUT", 600)
    try:
        status, resp = _http_json(req, review_timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        result.outcome = FAILED
        result.detail = redact(f"review call failed ({type(exc).__name__}: {reason})")
        result.model = health_model
        return result
    if status != 200 or not isinstance(resp, dict):
        result.outcome = FAILED
        result.detail = f"review call returned HTTP {status}" + ("" if isinstance(resp, dict) else " with a non-JSON body")
        result.model = health_model
        return result
    result.model = str(resp.get("model") or "")
    review = resp.get("review")
    if not result.model:
        result.outcome = FAILED
        result.detail = "contract violation: review response carries no `model`"
        result.model = health_model
        return result
    if not isinstance(review, str) or not review.strip():
        result.outcome = EMPTY
        result.detail = f"answered but produced no review text (model '{result.model}')"
        return result
    result.outcome, result.review, result.detail = OK, review, "review produced"
    return result


# ------------------------------------------------------------------ outputs --


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
            fh.write(text)


def run_chain(prompt: str, diff: str) -> tuple[list[TierResult], TierResult | None]:
    results = [
        TierResult(1, "kilo-primary", "kilocode"),
        TierResult(2, "spark-local", "spark-local"),
        TierResult(3, "kilo-alternate", "kilocode-alternate"),
    ]
    primary, spark, alternate = results

    run_kilo_tier(primary, exclude=[], fallback=False)
    if primary.outcome == OK:
        return results, primary
    print(f"::warning::review tier 1 kilo-primary: {primary.outcome} - {primary.detail}; trying spark-local")

    run_spark_tier(spark, prompt=prompt, diff=diff)
    if spark.outcome == OK:
        return results, spark
    print(f"::warning::review tier 2 spark-local: {spark.outcome} - {spark.detail}; trying kilo-alternate")

    if primary.rc == 3:
        alternate.outcome = UNAVAILABLE
        alternate.detail = "skipped: the kilo catalog was unavailable in tier 1"
    else:
        run_kilo_tier(alternate, exclude=[primary.model] if primary.model else [], fallback=True)
    if alternate.outcome == OK:
        return results, alternate
    return results, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prompt", default="/tmp/kilo-review-prompt.md")
    ap.add_argument("--diff", default="/tmp/kilo-review.diff")
    ap.add_argument("--comment", default="/tmp/review-comment.md")
    args = ap.parse_args(argv)

    try:
        prompt = Path(args.prompt).read_text(errors="replace")
        diff = Path(args.diff).read_text(errors="replace")
    except OSError as exc:
        print(f"::error::review chain: cannot read inputs ({exc})")
        return 2

    results, winner = run_chain(prompt, diff)
    Path(args.comment).write_text(render_comment(results, winner), encoding="utf-8")

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
        print(f"review tier {r.index} {r.name}: {r.outcome}" + (f" [{r.model}]" if r.model else "") + f" - {r.detail}")
    if winner:
        if winner.index > 1:
            print(f"::warning::fleet review produced by FALLBACK tier {winner.index} {winner.name} ({winner.model})")
        else:
            print(f"::notice::fleet review produced by tier 1 kilo-primary ({winner.model})")
    else:
        print(f"::error::{NO_REVIEWER}: every review tier failed or was unavailable - see the job summary")
    return rc


if __name__ == "__main__":
    sys.exit(main())
