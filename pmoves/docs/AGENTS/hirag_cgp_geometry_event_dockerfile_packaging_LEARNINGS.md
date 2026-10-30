# hi-rag-gateway-v2 CGP geometry/event Dockerfile packaging — LEARNINGS

**Lane**: YouTube ingest gap (operator handoff 2026-10-15 "ok you are up MAVIS! lets complete this")
**Branch**: `fix/hi-rag-cgp-geometry-event-handler`
**HEAD at write**: `a7bfdd3e410` (chit-namespace fix) + `5aa894cccb8` (ratchet tests) + `ca9689c74a4` (docs) — the branch was rebuilt onto `origin/main` after the review, so these shas moved with it; match the commits by subject (`fix(hirag): Dockerfile.gpu packages the pmoves.chit namespace`, `test(ratchet): fix the review findings on #3382`, `docs(hirag): RELEASE row + LEARNINGS …`), because a further rebase rewrites the shas again
**Test contract**: `pmoves/tests/test_dockerfile_packages_pmoves_chit.py` 5/5 PASS (2 × `pmoves.chit` + 2 × `pmoves.tools` + 1 × CPU baseline); `pmoves/tests/test_yt_emit_cgp_ok.py` PASSES against the live stack since the 2026-10-30 review-fix round (it SKIPs where `requests` is absent)
**Fix**: `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu` add the `pmoves.chit` namespace copy that the CPU `Dockerfile` has had since `30efedfb77f` (2026-02-26)

## The defect, end-to-end

`POST /geometry/event` on `pmoves-hi-rag-gateway-v2-gpu-1` returns 503. The handler in `pmoves/services/hi-rag-gateway-v2/routes/geometry.py` (the `@router.post("/geometry/event")` route, currently `:141-142`) is correct — it returns 503 because `shape_store is None` (the `from geometry_bus import` of `shape_store`, currently `:25-26`, picks up the `shape_store = None` left behind by a failed init). The init in `geometry_bus.py` (the `try:` block that constructs `ShapeStore`, currently `:55-62`) is wrapped in try/except, and the init failed with:

```
ERROR:hirag.gateway.v2:ShapeStore init failed: No module named 'pmoves'
    from services.common.shape_store import ShapeStore
  File "/app/services/common/shape_store.py", line 17, in <module>
```

Tracing the import: `services.common.shape_store` (the `from pmoves.chit import CGP_SPEC_VERSION` line, currently `:17`) does that import. The container's Python path includes `/app` and `/app/libs` (per the Dockerfile's `PYTHONPATH` env), so Python looks for `pmoves` at `/app/pmoves/`. **The directory does not exist in the running container.**

The CPU `Dockerfile` creates `/app/pmoves/__init__.py` and `COPY chit /app/pmoves/chit` in its `pmoves` namespace block (anchor: the `COPY chit /app/pmoves/chit` line, currently `:28`; whole block `:24-32`). The GPU `Dockerfile.gpu` was missing both. The running GPU container is from `2026-09-05T20:04:20Z` — built from a `Dockerfile.gpu` that never carried the `pmoves.chit` namespace copy at all, because that copy landed with this PR (the CPU `Dockerfile` has had it since `30efedfb77f`). The defect is the packaging diff between the two Dockerfiles.

## Live evidence

```text
# From pmoves-yt container (caller)
$ docker logs pmoves-pmoves-yt-1 --tail 30 | grep -i cgp
WARNING:pmoves-yt:CGP geometry emit failed (non-fatal): 502: Failed to publish geometry event: 500 Server Error: Internal Server Error for url: http://host.docker.internal:8086/geometry/event

# From hi-rag-gateway-v2-gpu-1 (upstream)
$ docker logs pmoves-hi-rag-gateway-v2-gpu-1 --tail 30 | grep -i "503\|ShapeStore"
ERROR:hirag.gateway.v2:ShapeStore init failed: No module named 'pmoves'
    from services.common.shape_store import ShapeStore
INFO:hirag.gateway.v2:ShapeStore unavailable; geometry cache warm skipped
INFO: 172.30.6.5:54096 - "POST /geometry/event HTTP/1.1" 503 Service Unavailable

# Live probe that would have worked end-to-end
$ curl -X POST http://localhost:8077/yt/emit -d '{"video_id":"kJQP7kiw5Fk","topic":"ingest.transcript.ready.v1"}'
{"ok":true,"video_id":"kJQP7kiw5Fk","chunks":17,"upserted":17,"lexical_indexed":false,"cgp_ok":false,"profile":"dialogue"}
```

`chunks: 17, upserted: 17` — the chunking + vector upsert steps work. `cgp_ok: false` — the bridge to PMOVES-Creator's geometry bus + H3 Omni conditioning is broken. The content is in MinIO + the vector store, but never reaches the creative substrate.

## 4-bucket × 5-class taxonomy

### 1. Defects

| # | Class | What | Where | Why it hurt |
|---|-------|------|-------|-------------|
| 1.1 | dockerfile-sibling-drift | The CPU `Dockerfile` and the GPU `Dockerfile.gpu` are sibling files maintained in the same directory. A packaging change to one (commit `30efedfb77f` added the `pmoves.chit` namespace) was not mirrored to the other. | `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu` (pre-fix: no `COPY chit /app/pmoves/chit` line; the block was added by `a7bfdd3e410`) | Every GPU image built from this Dockerfile shipped without the `pmoves.chit` namespace, and every ShapeStore init failed at runtime |
| 1.2 | non-fatal-degradation-as-silent-failure | `pmoves-yt` logs the CGP emit failure as a `WARNING` and continues with `cgp_ok: false`. The HTTP 200 to the caller hides the failure. | `pmoves-yt` (the warning is in the operator's container logs) | The 503 from hi-rag-gateway-v2 surfaces only as a non-fatal warning; nothing blocks the request, so the operator does not know the bridge is broken without reading logs |
| 1.3 | handler-returns-503-without-logging-downstream | `/geometry/event` returns 503 ("ShapeStore unavailable") but the log message in `geometry_bus.py` (the `ShapeStore init failed: %s` exception, currently `:61`) is the actual root cause. The 503 response does not surface the import error. | `pmoves/services/hi-rag-gateway-v2/geometry_bus.py` (the `ShapeStore` init `try:` block, currently `:55-62`) | Even an operator who reads the 503 response has to dig into the container logs to find the actual cause; the 503 message is misleadingly generic |
| 1.4 | ratchet-blind-sibling | The existing `pmoves/tests/test_pmoves_chit_*` tests don't gate the Dockerfiles. The packaging regression was 4 months old in the running container before the operator noticed. | (no existing test) | A future sibling Dockerfile (e.g. `Dockerfile.cpu-amd`) following the same shape would re-introduce the same defect silently |

### 2. Decisions

| # | Class | What | Why | Alternative considered | Cost of alternative |
|---|-------|------|-----|------------------------|---------------------|
| 2.1 | fix-the-dockerfile-not-the-code | The actual defect is one missing `RUN mkdir + COPY chit` block in `Dockerfile.gpu`. The Python code is correct. | Docker packaging is the unit of deployment; the runtime can't fix what the build image doesn't carry. | Add a sys.path hack in `services.common.shape_store` | Cross-service hack; the right place is the build image |
| 2.2 | static-ratchet-over-runtime-test | The test is a regex over the Dockerfile source. | The runtime test (the CGP emit) only exercises after a fresh image build + container restart, which the operator doesn't do as a unit test cycle. The static ratchet is 0.01s and runs in CI. | Runtime test that builds a fresh image | 30-60s build, network-bound, brittle in CI |
| 2.3 | integration-test-skips-not-fails | The integration test `test_yt_emit_cgp_ok.py` SKIPs when the live stack is not exercisable (no live container, video in archive, etc.). | The fix is in packaging, not in a code path the test can exercise. The test is the GO/NO-GO signal for a re-deploy. | Hard fail when stack is down | Test fails for unrelated reasons; operator loses the ratchet |
| 2.4 | historic-baseline-pinned | The static ratchet includes `test_pmoves_chit_in_cpu_dockerfile_unchanged` as a SIBLING check on the CPU `Dockerfile`. The fix is in `Dockerfile.gpu`; the CPU file is the historical baseline pinned since `30efedfb77f`. | A future contributor who decides to also remove the namespace copy from the CPU file sees BOTH ratchets fail, with a pointer to `shape_store.py` as the reason not to. | Implicit coverage | A regression in the CPU file slips through silently |

### 3. Operations

| # | Class | What | Measured | Repeatability |
|---|-------|------|----------|---------------|
| 3.1 | sibling-dockerfile-pinning | Parametrized test over `Dockerfile*` glob in the service dir. | `test_dockerfile_packages_pmoves_chit[Dockerfile]` PASS, `[Dockerfile.gpu]` PASS | Adding a new `Dockerfile.cpu-amd` to the dir adds a third ratchet row for free |
| 3.2 | probe-video-archive-aware-skip | The archive skip is decided from the **emit response** (`_emit_declined_for_archived_video(payload, status_code)`), so the test never mutates the archive it measures. *(Before the 2026-10-30 review-fix round this was a `_video_in_archive()` pre-check that POSTed to `POST /yt/download` — itself the defect.)* | Verified: the probe video `0p_1QSUsbsM` is in the archive on this host, so the integration test SKIPs rather than falsely passing | When the operator wants to re-exercise, clear the archive or use a fresh probe |
| 3.3 | localhost-reachability-probe | `_localhost_reachable()` checks `socket.create_connection` to `localhost:8077` before issuing the HTTP call. | Verified: pmoves-yt is reachable, test reached the emit call and read the archive-skip decision off the response | If the operator takes pmoves-yt down, the test SKIPs without flapping |
| 3.4 | live-image-rebuild-required | The integration test can only pass on a freshly rebuilt GPU image. The pre-fix running container from `2026-09-05T20:04:20Z` will not pass the test. | The operator must run `docker compose build hi-rag-gateway-v2-gpu && docker compose up -d hi-rag-gateway-v2-gpu` after merging this PR. | Document the rebuild in the runbook |

### 4. Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.1 | same-shape-as-claude_backend | Both are "default host class behavior + explicit override" defects. | `pmoves/tools/claude_backend.py:_home_settings_path()`, `pmoves/tools/bash_resolver.py:_GIT_BIN_DIRS` (the explicit Windows-root override list, currently `:67`) | The project-wide pattern: never trust the platform default, always have an explicit env / function override |
| 4.2 | same-shape-as-windows_cp1252 | Both are "static ratchet over the file's source, runtime smoke in the test runner's host class". | `pmoves/tests/hardening/test_docker_hardening.py:TestWindowsHostCompat` (the Windows-host ratchet class, currently `:952-1026`) | The project's static-ratchet pattern is consistent across the ratchets I've added |
| 4.3 | cgp-bridge-creator-pipeline | CGP is the bridge from raw MinIO content to PMOVES-Creator's geometry bus + H3 Omni conditioning. | `pmoves/docs/geometry-bus/pipelines/youtube-to-persona.md` (tracked); `pmoves/docs/handoffs/youtube_ingest_gap_analysis_2026-10-15.md` — **not tracked in the repo**: the 2026-10-15 operator handoff was a session artifact that was never committed, so this path resolves on the operator's machine only | The defect is a single point in a 5-step pipeline; the ratchet only pins this step |
| 4.4 | github-organization-fork-pinning | The fix lands in `pmoves/services/hi-rag-gateway-v2/`, which lives in the `PMOVES.AI` repo. The downstream consumer (`PMOVES-Creator`) is a separate fork that does NOT need a change to consume the now-working CGP. | `POWERFULMOVES/PMOVES-Creator` | One PR, one repo, no cross-PR dependency |

## Ratchet pin (the thing that catches the next person)

```python
# pmoves/tests/test_dockerfile_packages_pmoves_chit.py
@pytest.mark.parametrize("dockerfile", _dockerfiles(), ids=lambda p: p.name)
def test_dockerfile_packages_pmoves_chit(dockerfile: Path) -> None:
    source = dockerfile.read_text(encoding="utf-8")

    # 1. Must mkdir the namespace and create __init__.py.
    init_pattern = re.compile(
        r"mkdir\s+-p\s+(\S*/pmoves)\s+"
        r"(?:&&|;|\\\s*\n\s+)\s*"
        r".*?"
        r"(\S*/pmoves)/__init__\.py",
        re.DOTALL,
    )
    assert init_pattern.search(source), (
        f"{dockerfile.name} does not create /app/pmoves/__init__.py. "
        f"ShapeStore init will fail at runtime with 'No module named pmoves'."
    )

    # 2. Must COPY chit into /app/pmoves/chit.
    copy_pattern = re.compile(
        r"^COPY\s+chit\s+(\S*/pmoves)/chit\b",
        re.MULTILINE,
    )
    assert copy_pattern.search(source), (
        f"{dockerfile.name} does not COPY chit /app/pmoves/chit. "
        f"`from pmoves.chit import CGP_SPEC_VERSION` will fail at module import."
    )
```

The ratchet is parametrized over every `Dockerfile*` in the service dir. Adding a new sibling Dockerfile to `pmoves/services/hi-rag-gateway-v2/` adds a new ratchet row for free; the new row is the canary. The pattern generalises: `pmoves/services/<service>/Dockerfile*` should all package whatever the service's Python imports need.

## Provenance (DARKXSIDE 2026-09-16: no workarounds; SDK + doc provenance required)

- **SDK file:line** — `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu` — the `pmoves` namespace block, anchored on the `COPY chit /app/pmoves/chit` line (currently `:74`; the whole block `:70-78`) — the fix. `pmoves/services/hi-rag-gateway-v2/Dockerfile` — the same anchor, `COPY chit /app/pmoves/chit` (currently `:28`; the whole block `:24-32`) — the historical baseline. *Anchored on the `COPY` line rather than a bare range, because the `pmoves.tools` follow-up commit widened both blocks inside this PR and moved every line number in them.*
- **Test contract** — `pmoves/tests/test_dockerfile_packages_pmoves_chit.py` 5/5 PASS (parametrized over both Dockerfiles: 2 × `pmoves.chit` + 2 × `pmoves.tools` + 1 × CPU baseline); `pmoves/tests/test_yt_emit_cgp_ok.py` PASSES against the live stack since the 2026-10-30 review-fix round (it SKIPs where `requests` is absent).
- **AGNOTE** — RELEASE row timestamped `2026-10-15T20:45:00Z` in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (currently `:3533`; the pmoves.tools UPDATE row is `:3535` and the 2026-10-30 review-fix row `:3536` — the three hirag rows sit at the tail of the register). The media-audio and Windows-cp1252 rows from the same operator session are at `:3519-3520`. *Anchored on the row's TIMESTAMP rather than its line number, because the register is append-only — later rows push it down.*
- **LEARNINGS** — this file.
- **PR + branch** — PR #3382, branch `fix/hi-rag-cgp-geometry-event-handler` (this agent, mvs_5d5493b128b640e9aff8d45adcc77a66).
- **Docs cited** — `pmoves/docs/geometry-bus/pipelines/youtube-to-persona.md` (the CGP bridge documentation).
- **Operator handoff** — 2026-10-15 "ok you are up MAVIS! lets complete this"; operator approved the proposed slice 2026-10-15.

---

## Review-fix round (2026-10-30)

Review on PR #3382 raised five findings against this slice. Each was
independently re-verified before acting; **all five were valid — three
code defects (rows 1, 2, 4) and two documentation-accuracy defects
(rows 3, 5)** — and the fixes below close all five.

The `file:line` pointers in the Finding column are positions in the tree
**at the reviewed commit `5eacaa437f`** (the PR head as the reviewer saw
it), not at the current HEAD: the branch was rebuilt onto `origin/main`
afterwards, so those line numbers have since moved. Read them with
`git show 5eacaa437f:<path>`.

| # | Finding | Verdict | Disposition |
|---|---------|---------|-------------|
| 1 | `test_yt_emit_cgp_ok.py` — `_video_in_archive()` (`:62` at the reviewed commit) probes with `POST /yt/download`, which is **state-mutating**: it downloads the video and writes it to the archive when the video is NOT already there. | **VALID** | The probe no longer calls `/yt/download` at all. The archive-skip decision now comes from the **emit response itself** (`_emit_declined_for_archived_video`), which is the authoritative answer to "was the CGP path actually exercised". |
| 2 | `test_yt_emit_cgp_ok.py` — the `"already in download archive" in r.text` substring sniff (`:69` at the reviewed commit) is case-sensitive with no status-code check. | **VALID** | Replaced by `_emit_declined_for_archived_video(payload, status_code)`: case-insensitive, status-code-aware, and it covers the **404 `transcript not found`** shape (yt-dlp refused to re-download an archived video → no CGP was built) that the old substring sniff could never see. |
| 3 | `test_dockerfile_packages_pmoves_chit.py` — the `test_dockerfile_packages_pmoves_tools` docstring (`:96` at the reviewed commit) claims `sign_trail.py` is imported by "shape_store / geometry_decoder / branch_trail / model_fitness". | **VALID — the claim was factually wrong** | Verified: `sign_trail.py` has **exactly ONE** importer in the tree — `pmoves/services/common/branch_trail.py:146` (`from pmoves.tools.sign_trail import build_payload`). The other three import `pmoves.chit` (shape_store), `chit_common` / `chit_security` (geometry_decoder), and `chit_security` (model_fitness) — not `sign_trail`. The docstring now states the real import graph with file:line citations. |
| 4 | `test_dockerfile_packages_pmoves_chit.py` — `test_pmoves_chit_in_cpu_dockerfile_unchanged` (`:141` at the reviewed commit) duplicates the parametrized `test_dockerfile_packages_pmoves_tools`; the docstring claims the CPU tools namespace is "pinned by this single check". | **VALID** | The redundant `assert "/app/pmoves/tools" in source` is **removed**. It was strictly WEAKER than the parametrized test (a bare substring match hits a comment; the parametrized test asserts the exact `COPY tools/<module> ... /app/pmoves/tools/<module>` destination via regex). The docstring now says the CPU tools namespace is covered by the parametrized test — and carries an explicit NOTE that the CPU path is **not** asserted there, so the next reader does not re-add the weaker check. |
| 5 | `AUTH_FLIPON_RUNBOOK_2026-10-11.md:11` — cites `env.shared.example:257` for both `..._CLIENT_ID` and `..._SECRET`. | **VALID** | Verified against the blob at the reviewed commit `5eacaa437f`: the row read `\| SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID/SECRET \| ... \| pmoves/env.shared.example:257 \|` — one line for two keys, where `:257` is `SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID` and `:258` is `..._SECRET`. The finding was **VALID, not a false positive**. The citation reads `257-258` today because #3377 (`6ff853221`) landed on `origin/main` and rewrote the row — it reached this branch through the 2026-10-30 `origin/main` merge, and it was not "already" correct when the finding was raised. No edit to the runbook was needed from this branch; the correction arrived with #3377. |

### Why the sign_trail.py copy stays even though it has one importer

`branch_trail.py` **is** copied into the image (`COPY services/common
/app/services/common`) and its import is **lazy** — it lives inside the
function body (`from pmoves.tools.sign_trail import build_payload`,
currently `branch_trail.py:146`), not at module top. So the failure would
surface at **call** time, not import time. A copy that fails late and
only on one code path is exactly the kind of regression a static ratchet
should keep covered, so `sign_trail.py` remains in the required set —
but the ratchet now states the real reason instead of an invented one.

### Live effect of the fix

Before the fix, on the operator's host the probe video `0p_1QSUsbsM`
was already in the download archive (`youtube 0p_1QSUsbsM` in
`/data/yt-dlp/download-archive.txt`), so the test **SKIPPED**. After the
fix the test **RUNS** and PASSES against the live stack:

```
$ POST http://localhost:8077/yt/emit {"video_id":"0p_1QSUsbsM",...}
{"ok":true,"video_id":"0p_1QSUsbsM","chunks":6,"upserted":6,...,"cgp_ok":true,...}
```

`pmoves/tests/test_yt_emit_cgp_ok.py` → **1 passed** (was SKIP) on the operator's
host. It SKIPs where `requests` is not installed — the live-stack assertion
needs it, so the SKIP is environment-driven, not a regression.
`pmoves/tests/test_dockerfile_packages_pmoves_chit.py` → **5 passed** (3 new
items from the `pmoves.tools` follow-up on top of the original 2 + CPU
baseline).

### New lessons

- **A probe that mutates state cannot establish a precondition.** The
  archive check asked "is this video already downloaded?" using the
  endpoint that downloads videos. On a host where the answer was "no",
  the probe made the answer "yes". The precondition must be observed
  through a read-only channel or through the operation's own response.
- **A substring sniff on response text is not a status-code check.**
  The archived-video skip surfaces as a **404** in one path and a
  **200 with a message** in another; only the former was invisible to
  the old check.
- **A ratchet's docstring is part of its contract.** A justification
  that names the wrong importers is not cosmetic — it teaches the next
  engineer to trust a claim that was never verified. The import graph
  is now cited file:line.
- **The repo's destructive-docker guard is itself a ratchet.**
  `pmoves/tests/_destructive_docker_guard.py` BLOCKED the first attempt
  at a read-only `docker exec` archive probe — correctly, because
  `docker exec` is refused in tests outside `pg_isready`/`psql -c`
  (incident 2026-09-26: a test tore down the live `pmoves` compose
  project). The fix moved to pure HTTP rather than adding an exemption.
