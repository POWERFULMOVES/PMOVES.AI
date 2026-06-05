# GHCR Publish — Trivy CVE Inventory & Remediation Plan (2026-06-05)

**Author:** 4090-claude · **Source run:** `integrations-ghcr.yml` #27023303282 (push, `main`, 15:15Z)
**Trigger:** recurring failed-run notifications on `main`; investigation traced them to the Trivy HIGH/CRITICAL gate (separate from the fork-sync.yml YAML break fixed in #1718 and the GHCR kvm2 deadlock fixed in #1717).

## TL;DR

The GHCR publish fails on **real** HIGH/CRITICAL CVEs in three integration images. All are **CVE-2026-\*** (disclosed *after* the existing `.github/trivy/integrations-main-2026-05-30.trivyignore`, which is why the gate began tripping recently). **~90% are JS dependency drift** (`axios`, `react-router`, `vitest`) in forked apps that are **150–193 commits behind upstream** — so **syncing the forks to upstream clears most of it by construction**, no hand-patching. Strategy (per DARKXSIDE): **sync forks → re-scan → triage the small residual** — do not patch old CVEs that an upstream sync resolves.

## 1. Full CVE inventory (gating scan, HIGH/CRITICAL)

| Image | Sev | CVE | Package | Installed → Fixed |
|---|---|---|---|---|
| **archon** | HIGH | CVE-2026-44486 | `axios` | 1.15.1 → 1.16.0 |
| | HIGH | CVE-2026-44487 | `axios` | → **NO FIX** |
| | HIGH | CVE-2026-44488 | `axios` | → 1.16.0 |
| | HIGH | CVE-2026-44496 | `axios` | → 1.16.0 |
| | HIGH | CVE-2026-33245 | `react-router` | 7.13.1 → 7.13.2 |
| | HIGH | CVE-2026-34077 | `react-router` | → 7.14.0 |
| | HIGH | CVE-2026-42211 | `react-router` | → 7.14.2 |
| | HIGH | CVE-2026-42342 | `react-router` | → 7.15.0 |
| | HIGH | CVE-2026-42504 | Go `stdlib` | v1.23.12 → 1.26.4 |
| **archon-ui** | HIGH | (same axios ×4 + react-router ×4) | `axios`, `react-router` | → 1.16.0 / 7.15.0 |
| | HIGH | CVE-2026-42504 | Go `stdlib` | v1.26.3 → 1.26.4 |
| **open-notebook** | HIGH | CVE-2026-44486/88/96 | `axios` | 1.13.5 → 1.16.0 |
| | HIGH | CVE-2026-44487 | `axios` | → **NO FIX** |
| | **CRITICAL** | CVE-2026-47429 | `vitest` | 3.2.4 → 4.1.0 |

**Totals:** archon 9 HIGH (8 fixable), archon-ui 9 HIGH (8 fixable), open-notebook 4 HIGH + **1 CRITICAL** (4 fixable). The only genuinely-unfixable item is **CVE-2026-44487 (axios)** — no patched version exists yet anywhere.

> Note: `agent-zero` is **not** in this list — its build+push succeeded; it only showed `cancelled` mid-`Generate SBOMs` (concurrency cancel by a newer push), not a real failure. Trivy DB-cache contention warnings (`Unable to reserve cache with key cache-trivy-…`) on pmoves-yt/wger are cosmetic post-step warnings, non-fatal.

## 2. Build-source → fork mapping (from `integrations-ghcr.matrix.json`)

| Image | git_url | ref | context | Dep source to fix |
|---|---|---|---|---|
| archon / archon-ui | `PMOVES.AI.git` | `main` | `pmoves/` | **`pmoves/integrations/archon`** submodule (PMOVES-Archon fork) |
| open-notebook | `PMOVES-Open-Notebook.git` | `PMOVES.AI-Edition-Hardened` | `.` | the fork branch directly (own `.github/trivy/open-notebook.trivyignore`) |

## 3. Staleness — the fork-sync lever

Two distinct axes (don't conflate them):

**a) Fork branch vs UPSTREAM** (drives the CVEs — the deps live here):

| Fork | Upstream | Behind | Ahead (PMOVES custom) |
|---|---|---|---|
| PMOVES-Archon | coleam00/Archon `dev` | **193** | 13 |
| PMOVES-Open-Notebook | lfnovo/open-notebook `main` | **152** | 41 |

Over 150–193 commits, upstream near-certainly bumped axios/react-router/vitest → a merge-preserving sync clears most CVEs. The `ahead` counts are PMOVES hardening — the sync **must merge, not reset**.

**b) Gitlink pin vs fork main** (`pmoves-submodule-fleet` audit, intra-fork drift): most pins are 0–6 behind. ⚠️ The audit's `behind` is **unreliable for forks on a custom default branch** (`PMOVES.AI-Edition-Hardened`) — e.g. it reports PMOVES-Archon `1308` and PMOVES-ClawZ `30967` only because it compares against `origin/main` rather than the hardened branch. Use axis (a) for CVE decisions.

## 4. Remediation sequence

1. **Sync forks to upstream (merge-preserving):** PMOVES-Archon (coleam00/Archon `dev`), PMOVES-Open-Notebook (lfnovo/open-notebook `main`). Preserve the `ahead` hardening commits.
2. **Bump gitlinks:** update `pmoves/integrations/archon` (and any other affected pins) to the synced fork commits; open-notebook builds from the fork branch directly so its image picks up the sync without a gitlink bump (track the pin anyway).
3. **Re-run GHCR publish → re-scan.**
4. **Triage residual only:**
   - `CVE-2026-44487` (axios, no fix) → justified `.trivyignore` entry **with expiry/review date**.
   - Go `stdlib` (CVE-2026-42504) → rebuild on a newer Go base image (build-arg/base bump), not a dep change.

## 5. Secondary fleet-hygiene findings (NOT CVE-blocking — separate track)

From the `pmoves-submodule-fleet` audit (informational):
- High gitlink drift (real, on `main`-default forks): `PMOVES-Headscale` (271), `PMOVES-Agent-Zero` (24), `PMOVES-BoTZ` (23). `PMOVES-ClawZ` (30967) and `PMOVES-Archon` (1308) are custom-branch false-highs (see §3b).
- Dirty initialized submodules: `PMOVES-DoX`, `PMOVES-ToKenism-Multi`.
- Many uninitialized nested submodules under `PMOVES-BoTZ/features/skills/repos/*` and `PMOVES-DoX/external/*` (expected if not `--init --recursive`).

These are batch-promotion candidates for a separate `chore(submodules): promote …` pass, independent of the CVE remediation.

## 6. Existing Trivy suppressions in play
- `.github/trivy/integrations-main-2026-05-30.trivyignore` (shared, dated) — predates the CVE-2026-444xx wave.
- `.github/trivy/open-notebook.trivyignore` (per-image).

Any new suppression added in step 4 must carry a justification + review date (no blanket/unbounded ignores).
