I'll review the PR diff. Let me start by reading it.
Let me read the rest of the diff.
I have the full diff. Let me verify one exception-hierarchy assumption that determines a correctness finding before finalizing.
No Python in this environment to execute-verify, but the CPython hierarchy is standard: `http.client.IncompleteRead`/`BadStatusLine`/`LineTooLong`/`InvalidURL` subclass `HTTPException` (an `Exception`, not `URLError`/`OSError`/`ValueError`); only `RemoteDisconnected` also rides `ConnectionResetError`. Review follows.

---

## 1. CORRECTNESS

- **BUG (blocks the PR's purpose):** `_http_json`/`run_spark_tier` catch only `(urllib.error.URLError, OSError, ValueError)`. `http.client.HTTPException` subclasses that are *not* also `OSError` — `IncompleteRead` (truncated `200` body) and `BadStatusLine` (garbage status line) — propagate uncaught, crash the chain, and SKIP tier 3 (`kilo-alternate`). That is exactly the fallback this PR exists to guarantee, and Spark is unfinished/unmeasured so malformed HTTP is the likely failure during bring-up. It is fail-safe (job goes red, no false pass) but defeats the chain. Fix: `import http.client` and add `http.client.HTTPException` to the `except` tuple at both Spark HTTP call sites (or in `_http_json`). (`RemoteDisconnected` is already caught via `OSError`.)
- **Alternate is bounded by `KILO_REVIEW_MODEL_PREFERENCES` only.** A short list exhausts to `unavailable` (rc 4) even when other catalog models exist. By design, but an operator footgun — tier 3 won't reach the broader catalog.
- **Docstring/doctrine mismatch:** the chain's documented exit `2` (usage error, missing inputs) is re-mapped by the workflow's `Fail on NO-REVIEWER-AVAILABLE` step to job exit `3` (no `state` → `!= REVIEWED`). Fail-safe, but diverges from the stated `0 clean / 1 findings / 3 could-not-measure` doctrine.
- **Spark `verdict` field is defined by the contract but never read.** A review whose text says `REQUEST_CHANGES` still yields chain rc `0` / state `REVIEWED` (fail step passes). Consistent with the docstring ("0 = a review was produced"), but confirm that's intended vs. a findings-blocking signal.
- **`"pr": None`** is sent to Spark when `PR_NUMBER` is non-digit (never in `pull_request` runs); contract says int. Graceful, but the Spark-side handler must tolerate null.
- **Tier wrapper mktemp/docker cleanup leaks on the outer timeout:** if `review_chain.py`'s 960 s `subprocess.run` timeout fires (inner `timeout` at 900 s should fire first), the kilo_review_tier.sh `rm -f`/`docker rm -f` tail is skipped → tmp files leak in `/tmp` and a container can linger. Edge case (ephemeral runner `/tmp`); minor.
- **`printf '{"model": "%s"}' "${MODEL}"`** builds `kilo.json` by string interpolation, not JSON encoding. Safe for current catalog ids, but a catalog id containing `"`/`\` would produce invalid JSON and an odd resolution error. Low risk (trusted catalog source).

## 2. SECURITY / TOPOLOGY

- **Clean for new topology.** No literal endpoints, tailnet/LAN IPs, bridge IPs, hostnames, internal ports, or plaintext secrets/tokens in the repo. `SPARK_REVIEW_URL`/`SPARK_REVIEW_TOKEN` are **secrets** (not `vars`) — correct for a public repo where variables print in logs. `Redactor` scrubs url + url-without-slash + token from every emitted string; `test_spark_endpoint_never_leaks_into_outputs` asserts the path/host and token never appear in comment/summary/stdout/stderr. `spark/local-model` and tier labels are identifiers, not topology.
- **Pre-existing, not a regression:** the new comment footer string `"self-hosted kvm4"` repeats the runner label, but `kvm4` is already public via `runs-on: [self-hosted, kvm4]` (required config, not a leak).
- **Pre-existing, not a regression:** `KILOCODE_API_KEY`/`KILO_API_KEY` are passed into the container via `-e KEY="$KEY"` (value lands on the `docker` argv / `/proc/<pid>/cmdline`, visible to co-tenants on the host). The original lane did the same; consider `--env-file` or `-e KEY` (no `=`) for least-exposure. SPARK creds are correctly NOT forwarded into the kilo container (the tier wrapper only passes `KILO_*`). No SPARK secret touches the kilo tier.
- **Hardening (no current leak):** `Redactor` does full-string matches only; it does not scrub scheme/host/port/path components. It is safe today because non-http(s) URLs are rejected up front (no `ValueError("unknown url type: …")` leak) and `URLError.reason`/socket errors don't carry the host. If a future code path ever embeds a bare `host:port` in an exception, add component-wise redaction.
- **Scope:** all 5 touched files (`kilo_review_in_container.sh`, `kilo_review_tier.sh`, `review_chain.py`, `kilocode-review.yml`, `test_review_chain.py`) are CI-review-lane files; the "replaces broken claude-review lane" footer correction and header rewrite are in the same file. No scope creep.
- **YAML/anchors:** none used; env values quoted as strings; `if: always() && steps.chain.outcome != 'skipped'` and the `runs-on` label are valid. Shell: `set -uo pipefail` (no `-e`, by design — chain step always exits 0), `set -euo pipefail` + `set -f` in-container; quoting/globbing are handled.

## 3. VERDICT

**REQUEST_CHANGES** — uncaught `http.client.HTTPException` (`IncompleteRead`/`BadStatusLine`) from a malformed Spark response aborts the chain and skips the tier-3 fallback the PR exists to provide (fail-safe but defeats the design); trivial one-line fix (catch `HTTPException` at the two Spark HTTP sites). Everything else is non-blocking hardening/design notes; topology/secrets handling is clean.
