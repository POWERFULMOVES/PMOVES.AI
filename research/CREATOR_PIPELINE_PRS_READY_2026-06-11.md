# Heads-up → mirror / Z890: Creator-pipeline phases 1-5 PRs ready for the merge batch (2026-06-11)

**From:** 4090-CLAUDE. **For:** the mirror coordinating the Z890 submodule-sync + post-merge-review batch.

The creator-pipeline voice lane (AGNOTE claim #1788) is built out. **Five PRs are open, each subagent-built and pre-commit-verified (ruff + the full creator-operator / flute-gateway suite green before the PR was opened).** They are ready to fold into the same review/merge batch as the submodule sync — per the plan, **all services come up once sync lands + these merge.**

| Phase | PR | Lane | Verified |
|-------|----|----|----------|
| 1 | #1794 | `flute-gateway`: `OmniVoiceProvider` (mirrors voicebox; `engine=omnivoice` dispatch + CHIT publish) | ruff clean, 47 tests (22 new + voicebox) |
| 2 | #1790 | `creator-operator`: Prometheus `/metrics` on omnivoice_server (clap-embed pattern) | ruff clean, 53 passed |
| 3 | #1791 | `creator-operator`: `ServerOmniVoiceClient` (HTTP → production :8002, contract-preserving) | ruff clean, 61 passed |
| 4 | #1792 | `creator-operator`: `image.flux-schnell` (Apache) + `anime.animagine-xl` (OpenRAIL++), license-clean | ruff+yaml clean, 61 passed |
| 5 | #1793 | `creator-operator`: `ROCM_VALIDATION.md` + `rocm_smoke.sh` (Knuckles seam) | bash -n clean, no IPs |

## Merge notes (for the batcher)
- **#1790 + #1791 both edit `pmoves/services/creator-operator/requirements-prod.txt`** (prometheus_client vs httpx) → a one-line conflict to resolve on whichever merges second.
- Each PR's `claude-review` check shows the **pre-existing org-allowlist failure** (`oven-sh/setup-bun`) — infra, not our diffs. All substantive checks pass.
- No interdependencies otherwise; any merge order works (modulo the requirements-prod.txt note).
- These touch **only** `creator-operator` + `flute-gateway` service code/config — **no submodule, no `.gitmodules`, no gitlink** — so they do not collide with the submodule-sync lane.

## Already on main this arc (context)
WS-V OmniVoice slices 1-3 (#1759/#1779/#1780), Node-20-EOL cleared across project/container/Actions runtimes (#1781/#1783), secure production OmniVoice server activated + verified on the 4090 (:8002, token + reference-catalog + traversal-guard).

## Follow-ups (post-batch, not blocking)
- Wire the dispatcher to **select** `ServerOmniVoiceClient` at runtime (the client exists; selection is the next slice).
- Dedicated `voice_design` field on flute-gateway `SynthesizeRequest` (instruct currently rides the engine field).
- Vendor the slice-1 Pinokio launcher into the `PMOVES-Creator` submodule + gitlink bump.
- Register the creator NATS subjects in the live catalog.
- **Open control-body item (from the Z890 fleet-sync handoff):** ratify setting each fork's GitHub default branch = its `.gitmodules` gitlink-tracked branch.

<!-- GRAPHITI_MARK: 4090-CLAUDE::CREATOR-PIPELINE-PRS-READY::2026-06-11 -->
