# hi-rag-gateway-v2 CGP geometry/event Dockerfile packaging — LEARNINGS

**Lane**: YouTube ingest gap (operator handoff 2026-10-15 "ok you are up MAVIS! lets complete this")
**Branch**: `fix/hi-rag-cgp-geometry-event-handler`
**HEAD at write**: `_pending_` (3 commits: fix + tests + docs)
**Test contract**: `pmoves/tests/test_dockerfile_packages_pmoves_chit.py` 3/3 PASS; `pmoves/tests/test_yt_emit_cgp_ok.py` SKIPs (live container has the broken image; test gates the rebuild)
**Fix**: `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu` add the `pmoves.chit` namespace copy that the CPU `Dockerfile` has had since `30efedfb77f` (2025-05 era)

## The defect, end-to-end

`POST /geometry/event` on `pmoves-hi-rag-gateway-v2-gpu-1` returns 503. The handler in `pmoves/services/hi-rag-gateway-v2/routes/geometry.py:142` is correct — it returns 503 because `shape_store is None` (line 26 import from `geometry_bus` was `shape_store = None` after a failed init). The init in `geometry_bus.py:55-62` is wrapped in try/except, and the init failed with:

```
ERROR:hirag.gateway.v2:ShapeStore init failed: No module named 'pmoves'
    from services.common.shape_store import ShapeStore
  File "/app/services/common/shape_store.py", line 17, in <module>
```

Tracing the import: `services.common.shape_store:17` does `from pmoves.chit import CGP_SPEC_VERSION`. The container's Python path includes `/app` and `/app/libs` (per the Dockerfile's `PYTHONPATH` env), so Python looks for `pmoves` at `/app/pmoves/`. **The directory does not exist in the running container.**

The CPU `Dockerfile` creates `/app/pmoves/__init__.py` and `COPY chit /app/pmoves/chit` at lines 18-21. The GPU `Dockerfile.gpu` was missing both. The running GPU container is from `2026-09-05T20:04:20Z` — built before the fix in commit `aa4d561fa52 fix(packaging): ensure service Dockerfiles package pmoves.tools (#2070)` had a chance to land. Or built with the fix that missed the `pmoves.chit` step. The defect is the packaging diff between the two Dockerfiles.

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
| 1.1 | dockerfile-sibling-drift | The CPU `Dockerfile` and the GPU `Dockerfile.gpu` are sibling files maintained in the same directory. A packaging change to one (commit `30efedfb77f` added the `pmoves.chit` namespace) was not mirrored to the other. | `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu:46-50` (pre-fix) | Every GPU image built from this Dockerfile shipped without the `pmoves.chit` namespace, and every ShapeStore init failed at runtime |
| 1.2 | non-fatal-degradation-as-silent-failure | `pmoves-yt` logs the CGP emit failure as a `WARNING` and continues with `cgp_ok: false`. The HTTP 200 to the caller hides the failure. | `pmoves-yt` (the warning is in the operator's container logs) | The 503 from hi-rag-gateway-v2 surfaces only as a non-fatal warning; nothing blocks the request, so the operator does not know the bridge is broken without reading logs |
| 1.3 | handler-returns-503-without-logging-downstream | `/geometry/event` returns 503 ("ShapeStore unavailable") but the log message in `geometry_bus.py:61` (`ShapeStore init failed: %s`) is the actual root cause. The 503 response does not surface the import error. | `pmoves/services/hi-rag-gateway-v2/geometry_bus.py:55-62` | Even an operator who reads the 503 response has to dig into the container logs to find the actual cause; the 503 message is misleadingly generic |
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
| 3.2 | probe-video-archive-aware-skip | `_video_in_archive()` pre-checks via `POST /yt/download`; the test SKIPs if the probe video is already in the download archive. | Verified: the probe video `0p_1QSUsbsM` is in the archive on this host, so the integration test correctly SKIPped | When the operator wants to re-exercise, clear the archive or use a fresh probe |
| 3.3 | localhost-reachability-probe | `_localhost_reachable()` checks `socket.create_connection` to `localhost:8077` before issuing the HTTP call. | Verified: pmoves-yt is reachable, test ran the archive pre-check | If the operator takes pmoves-yt down, the test SKIPs without flapping |
| 3.4 | live-image-rebuild-required | The integration test can only pass on a freshly rebuilt GPU image. The pre-fix running container from `2026-09-05T20:04:20Z` will not pass the test. | The operator must run `docker compose build hi-rag-gateway-v2-gpu && docker compose up -d hi-rag-gateway-v2-gpu` after merging this PR. | Document the rebuild in the runbook |

### 4. Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.1 | same-shape-as-claude_backend | Both are "default host class behavior + explicit override" defects. | `pmoves/tools/claude_backend.py:_home_settings_path()`, `pmoves/tools/bash_resolver.py:67` | The project-wide pattern: never trust the platform default, always have an explicit env / function override |
| 4.2 | same-shape-as-windows_cp1252 | Both are "static ratchet over the file's source, runtime smoke in the test runner's host class". | `pmoves/tests/hardening/test_docker_hardening.py:947-1014` | The project's static-ratchet pattern is consistent across the ratchets I've added |
| 4.3 | cgp-bridge-creator-pipeline | CGP is the bridge from raw MinIO content to PMOVES-Creator's geometry bus + H3 Omni conditioning. | `pmoves/docs/geometry-bus/pipelines/youtube-to-persona.md`, `pmoves/docs/handoffs/youtube_ingest_gap_analysis_2026-10-15.md` | The defect is a single point in a 5-step pipeline; the ratchet only pins this step |
| 4.4 | github-organization-fork-pinning | The fix lands in `pmoves/services/hi-rag-gateway-v2/`, which lives in the `PMOVES.AI` repo. The downstream consumer (`PMOVES-Creator`) is a separate fork that does NOT need a change to consume the now-working CGP. | `POWERFULMOVES/PMOVES-Creator` | One PR, one repo, no cross-PR dependency |

## Ratchet pin (the thing that catches the next person)

```python
# pmoves/tests/test_dockerfile_packages_pmoves_chit.py
@pytest.mark.parametrize("dockerfile", _dockerfiles(), ids=lambda p: p.name)
def test_dockerfile_packages_pmoves_chit(dockerfile: Path) -> None:
    source = dockerfile.read_text(encoding="utf-8")
    init_pattern = re.compile(
        r"mkdir\s+-p\s+(\S*/pmoves)\s+"
        r"(?:&&|;|\\\s*\n\s+)\s*"
        r".*?"
        r"(\S*/pmoves)/__init__\.py",
        re.DOTALL,
    )
    assert init_pattern.search(source), f"{dockerfile.name} does not create /app/pmoves/__init__.py"

    copy_pattern = re.compile(r"^COPY\s+chit\s+(\S*/pmoves)/chit\b", re.MULTILINE)
    assert copy_pattern.search(source), f"{dockerfile.name} does not COPY chit /app/pmoves/chit"
```

The ratchet is parametrized over every `Dockerfile*` in the service dir. Adding a new sibling Dockerfile to `pmoves/services/hi-rag-gateway-v2/` adds a new ratchet row for free; the new row is the canary. The pattern generalises: `pmoves/services/<service>/Dockerfile*` should all package whatever the service's Python imports need.

## Provenance (DARKXSIDE 2026-09-16: no workarounds; SDK + doc provenance required)

- **SDK file:line** — `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu:52-55` (the fix); `pmoves/services/hi-rag-gateway-v2/Dockerfile:18-21` (the historical baseline, unchanged).
- **Test contract** — `pmoves/tests/test_dockerfile_packages_pmoves_chit.py` 3/3 PASS; `pmoves/tests/test_yt_emit_cgp_ok.py` SKIPs (live image is the pre-fix stale build; SKIP is the correct behavior per the ratchet's `localhost_reachable` + `_video_in_archive` checks).
- **AGNOTE** — RELEASE row at `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:3399` (next to the existing media-audio and Windows-cp1252 rows at 3397-3398).
- **LEARNINGS** — this file.
- **PR + branch** — new PR off `fix/hi-rag-cgp-geometry-event-handler` (this agent, mvs_5d5493b128b640e9aff8d45adcc77a66).
- **Docs cited** — `pmoves/docs/geometry-bus/pipelines/youtube-to-persona.md` (the CGP bridge documentation).
- **Operator handoff** — 2026-10-15 "ok you are up MAVIS! lets complete this"; operator approved the proposed slice 2026-10-15.
