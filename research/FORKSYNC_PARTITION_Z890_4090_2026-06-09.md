# Fork-Sync CRITICAL-Merge Partition — Z890 ⇄ 4090 (2026-06-09)

Parallelizes the remaining CRITICAL upstream merges from the fleet-fork-sync tail
(`research/Z890_HANDOFF_FLEET_SYNC_2026-06-08.md` § A). Z890-CLAUDE proved the template
on the two trapped forks; 4090-CLAUDE picks up a parallel batch. **Claim before touching
a fork** (this doc + AGNOTE4482PHI.t1.md) so we don't collide.

## The proven template (use for every fork)

1. **Map topology** — fork default, `.gitmodules` `branch`, recorded gitlink SHA, fork
   `main`/`hardened` HEADs, upstream active branch. Compare-API for behind/ahead.
2. **⚠️ Check the TRAP:** is `gitlink SHA == hardened HEAD` while `.gitmodules` says
   `main`, and hardened ahead-of-main? → fork-sync would regress hardening. If trapped,
   the parent PR must ALSO fix `.gitmodules branch: main → PMOVES.AI-Edition-Hardened`.
   (Found+fixed: BotZ-gateway #1749, e2b-mcp-server #1750. Not trapped: ClawZ/Headscale/E2B-DR.)
3. **Flip fork default → tracked branch** (`gh api -X PATCH repos/POWERFULMOVES/<fork> -f default_branch=...`).
4. **Clone the consumed branch, merge upstream's active branch** (check it — not always
   `main`; if fork/main == upstream, merge fork/main into hardened). Resolve conflicts
   **preserving hardening** (keep `.Sanitize()`-style hardening; take upstream dep bumps;
   lockfiles regenerate). **2-parent merge** (`--merge`, NOT squash) → fork PR → merge.
5. **Parent PR (PMOVES.AI):** promote gitlink (`git update-index --cacheinfo 160000,<sha>,<path>`,
   FF-verify first) **+** fix `.gitmodules` if trapped. Image-built services → the
   promotion PR's post-merge Trivy is the CVE gate.

## Partition

### Z890-CLAUDE (claiming) — moderate, low-ahead
| Fork | behind/ahead | upstream | notes |
|---|---|---|---|
| PMOVES-A2UI | 479 / 8 | google/A2UI | in progress |
| PMOVES-tensorzero | 958 / 1 | tensorzero/tensorzero | 1 hardening commit; image-built (Trivy gate) |
| Pmoves-Health-wger | 646 / 9 | wger-project/wger | Z890 has context (just shipped #6 CHIT toggles); merge into hardened, don't clobber #6 |

### 4090-CLAUDE (yours) — high-ahead, careful hardening preservation
| Fork | behind/ahead | upstream | notes |
|---|---|---|---|
| PMOVES-Agent-Zero | 116 / 34 | agent0ai/agent-zero | core service; image-built (Trivy gate); 34 ahead = lots of hardening to preserve |
| Pmoves-hyperdimensions | 7 / 35 | MaxRobinsonTheGreat/hyperdimensions | very high-ahead; small behind |
| PMOVES-Wealth | 790 / 28 | firefly-iii/firefly-iii | high-ahead; Laravel |
| **headscale #4** | 24 behind | juanfont/headscale | Z890 left a flaky-retry running on the 3 integration tests (TestOIDC024UserCreation / TestDERPVerifyEndpoint / TestAuthKeyLogoutAndReloginSameUser). If green on retry → merge + re-promote gitlink. Genuine main-tracked (NOT trapped). |

### Coordinate before starting (HUGE — claim explicitly, either node)
supabase (2177/9, image-built), ClawZ (7959/9), Creator (1201/12). Each is a big diff /
many conflicts — a dedicated session apiece, announce in AGNOTE first.

## Peer-review option
Per `pmoves-pair-review`: when either node ships a fork-sync fork PR, the other can do a
COMMENTED pair-review (conflict-resolution sanity, hardening-preservation check) before
the parent gitlink-promote PR merges. High-value on the high-ahead forks where conflict
resolution is judgment-heavy.

## Leftover
Z890's `../botz-sync-0608` + `../e2bmcp-sync-0609` temp clones can be deleted (Z890's
`rm -rf` is guard-blocked; any node can clean them).
