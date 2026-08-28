# Hardened-Branch Fleet Audit — 2026-05-31

**Author:** Z890-CLAUDE (5090 handoff: deep-bumblebee security lane)
**Scope:** All 38 submodules tracking `PMOVES.AI-Edition-Hardened`
**Trigger:** Security-backfill handoff found BoTZ JWT auth-gate fix (#72) merged to `main`
but absent from the `PMOVES.AI-Edition-Hardened` branch the parent actually pins.

## The invariant

`PMOVES.AI-Edition-Hardened` is the branch the parent `PMOVES.AI` gitlink tracks for each
submodule — i.e. **the code that actually deploys**. A "merged security PR" is only as
deployed as the branch the gitlink points at. Therefore the security-correct invariant is:

> **`hardened ⊇ default`** — the hardened branch must contain every commit on the repo's
> default branch (`main`/`master`/release), plus its hardening deltas. The `behind` count of
> `default → hardened` must be **0**.

When hardened falls behind default, security fixes that land on default **silently fail to
reach production**. That is exactly the BoTZ #72 / BotZ-gateway #4 hole.

### Structural enforcement (best practice)

8 repos already make `PMOVES.AI-Edition-Hardened` their **default branch**. For those, drift
is *structurally impossible* — there is no separate default to fall behind, every PR targets
hardened, and the invariant holds by construction. **Converging the whole fleet on
hardened-as-default is the recommended end state**: it turns a policy you must police into a
topology where the bad state cannot exist.

## Classification (38 pins)

`missing` = commits on the repo default branch that hardened lacks (the security-relevant drift).
`gl=tip?` = does the parent gitlink already point at the hardened tip.

### ✅ Clean — invariant holds, gitlink current (11)

`PMOVES-Archon`, `PMOVES-Deep-Serch`, `PMOVES-HiRAG`, `PMOVES-crush`, and the 7
hardened-as-default repos with gitlink=tip: `PMOVES.YT`, `PMOVES-Jellyfin`,
`Pmoves-Jellyfin-AI-Media-Stack`, `PMOVES-Creator`, `Pmoves-Health-wger`,
`PMOVES-Remote-View`, `PMOVES-space-agent`.

### 🟡 Gate-OK but gitlink stale — safe promote (8 vs origin/main)

Hardened already ⊇ default (`missing=0`); the parent just pins an older SHA. Promoting the
gitlink to the hardened tip is zero-risk forward progress (same operation as PR #1656).
SHAs measured against **`origin/main`** (the prior audit read a 108-commit-stale tree).

| Submodule | gitlink → hardened tip |
|---|---|
| `Pmoves-hyperdimensions` | `41e1dc6` → `5ec35cb` |
| `Pmoves-AgentGym-RL` | `b208734` → `a159ee0` |
| `PMOVES-surf` | `135748a` → `86f7d11` |
| `PMOVES-Ultimate-TTS-Studio` | `26ca5a2` → `7ee6b9d` |
| `PMOVES-Tailscale` | `2ad2d4d` → `74facf6` |
| `PMOVES-Neo4j` | `c68156e` → `e5c1936` |
| `PMOVES-autoresearch` | `c2450ad` → `9eca5b5` |
| `PMOVES-ToKenism-Multi` | `f061fd7` → `f6b9db9` (incl. #49 doc fix) |

`pmoves/integrations/archon` was already current (`604b6fa`) on `origin/main` — no bump needed.

### 🔴 DRIFTED — hardened missing default-branch commits (17)

These need `default → hardened` merge-forward (or per-repo verification that the missing
commits are intentionally excluded). **Each requires a safety check**: does hardened
*intentionally* omit anything (e.g. a stripped vulnerable dependency) that a merge-forward
would reintroduce? That check is the research-agent lane.

| Submodule | missing | hardened-only | known security gap |
|---|---:|---:|---|
| `PMOVES-BoTZ` | 39 | 77 | **#72 JWT auth-gate** (`974dbb77`) |
| `PMOVES-A2UI` | 8 | 7 | — |
| `PMOVES-BotZ-gateway` | 7 | 9 | **#4 log-sanitize** (`25650220`) |
| `PMOVES-DoX` | 6 | 68 | — |
| `PMOVES-Wealth` | 6 | 709 | — |
| `pmoves-e2b-mcp-server` | 6 | 8 | — |
| `PMOVES-E2b-Spells` | 4 | 2 | — |
| `PMOVES-Agent-Zero` | 3 | 833 | — |
| `PMOVES-AgentGym` | 3 | 2 | — |
| `PMOVES-supabase` | 3 | 5 | — (default=`master`) |
| `PMOVES-llama-throughput-lab` | 1 | 4 | — |
| `PMOVES-E2B-Danger-Room-Desktop` | 1 | 4 | — |
| `PMOVES-Pinokio-Ultimate-TTS-Studio` | 1 | 3 | — |
| `PMOVES-Open-Notebook` | 1 | 252 | — |
| `PMOVES-n8n` | 1 | 2 | — |
| `PMOVES-tensorzero` | 1 | 8 | — |
| `PMOVES-a0-plugins` | 1 | 4 | — |

## Reconciliation plan

1. **Safe tranche (this PR):** promote the 8 gate-OK-stale gitlinks to hardened tips. No
   drift, no merge — pure pin advancement.
2. **Drifted tranche (research-agent fan-out):** one read-only agent per drifted repo, each
   answering: (a) is `default → hardened` merge-forward clean? (b) does any hardened-only
   commit intentionally remove something the merge would reintroduce? (c) does the hardening
   match current best practice (deps, CVEs, secrets, CI gates)? Output: per-repo merge-safe
   verdict + PR.
3. **Convergence (follow-up):** migrate remaining split-default repos to hardened-as-default
   so drift becomes structurally impossible.

## Method

Read-only `gh api repos/<r>/compare/PMOVES.AI-Edition-Hardened...<default>` per submodule;
default branch resolved via `gh api repos/<r> --jq .default_branch` for the 11 repos lacking
`main`. Full command trail in the 2026-05-31 session.
