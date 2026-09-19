# Org Migration + Secrets Topology Plan

_Status: PROPOSED (DARKXSIDE decision points marked **[DECIDE]**) · 2026-09-09 · Author: CRUSH-SPARK (Z890)_

## Why now

The learning-by-mess phase is over; the mesh goes live. Three pressures
converge: (1) the personal account carries 400 live repos (368 forks) that are
the fork fleet — unmanaged sprawl; (2) the secrets funnel replicates a ~140-label
env into per-repo GitHub Actions secrets, and GitHub caps repo secrets at 100;
(3) fleet memory (cipher) is now per-node and tailnet-published, so nodes,
repos, and secrets need one coherent grouping instead of accretion.

## Measured state (2026-09-09)

| Surface | State |
|---|---|
| `POWERFULMOVES` (personal) | 400 live repos, 368 forks, 12 private / 388 public |
| `CATACLYSM-STUDIOS-INC` (org) | 1 repo: private `PMOVES.AI` (canonical production) |
| `PMOVES-AI` (org) | empty shell |
| GitHub App | live and validated (`pat-health-check.yml`), `create-github-app-token` pinned-SHA across 10+ workflows, reusable `_app-token.yml` |
| Repo secrets | ~140-label env replicated via `sync-secrets-local.yml` → `push-gh-secrets.sh`; 100/repo cap pressure |
| GitHub limits (verified vs docs) | repo secrets **100**, org secrets **1,000** but only **100 visible per workflow** (alphabetical), env secrets 100, App tokens 1h auto-revoked |

## Target architecture

### 1. One canonical org for the fleet — **[DECIDE: which]**
- Option A: `PMOVES-AI` becomes canonical (name matches the lattice; CSI stays
  the business/production shell).
- Option B: `CATACLYSM-STUDIOS-INC` stays canonical; `PMOVES-AI` becomes the
  public/mirror org.
- The fork fleet (upstream forks of tracked submodules) moves to the canonical
  org so the GitHub App installs once org-wide instead of per-account.

### 2. Repo grouping — tiers mirror the agent taxonomy
`agents / media / data / llm / ui / infra` (+ `canonical` for PMOVES.AI
itself). Groups drive three things 1:1: org secret visibility sets, App
installation repo lists, and submodule hygiene audits. The 58 tracked
submodules get a `tier:` field in `.gitmodules`-adjacent config
(`pmoves/configs/submodule_layer_validation_manifest.json` already exists —
extend it rather than adding a new registry).

### 3. Secrets topology — shrink repo secrets toward zero
- **Org secrets (1,000 cap, selected-repo visibility):** shared CI creds only —
  `GH_APP_SEC` (App private key), GHCR/DockerHub publish creds, CI runner
  tokens. Keep the visible-per-workflow-100 cap in mind: prefix secret names by
  tier (`CI_`, `PUBLISH_`) because the 100 visible are sorted alphabetically.
- **Per-repo secrets:** auto-derived allowlist — grep each repo's
  `.github/workflows` for `secrets.X` and sync exactly that set. Most
  submodules need 0–5. The funnel gains a `--derive` mode instead of
  blanket-syncing the env.
- **Runtime env (~140 labels) never enters GitHub.** It lives in CHIT + vault +
  per-node `env.shared`. GH is a distribution endpoint, not the source of truth.
- **Cloud creds:** prefer OIDC federation (Hostinger/Azure where supported);
  App-minted 1h tokens replace any remaining stored PATs.
- **[DECIDE]** approve the derivation script replacing blanket sync
  (`push-gh-secrets.sh --derive <repo>`).

### 4. Fleet memory topology (landed this session, recorded here)
Per-node cipher, tailnet-published on fleet-memory nodes: agents use their
node's local `pmoves-cipher-local`; `TS_<NODE>:8105` reaches another node's
memory. `tailscale-node-ips.sh` maps Z890/5090/4090/SPARK/B850/KVM4-1/KVM4-2/
KVM2 (`pmoves-4090` registration fixed 2026-09-09). Host nodes suppress their
own TS self-entry (pending in `crush_configurator`). Per-agent identity =
Supabase-minted `cipher_<uuid>` tokens (`cipher-mint-token`).

## Phased migration

- **P0 — prerequisites (this node):**
  1. `make -C pmoves secrets-funnel` — reconcile the stale service-role
     projection (NEXT_STEPS 2026-07-17: shared service-role vars fail PostgREST
     auth; this currently blocks `cipher-mint-token` with 401).
  2. Confirm App installation covers the chosen org (selected-repos mode).
- **P1 — canonical move:** transfer the 58 tracked submodule forks to the
  canonical org (transfer preserves SHAs and fork relationships; gitlinks are
  unaffected). Update `.gitmodules` URLs + `fleet-fork-sync` targets + branch
  protection in one lane. Re-run `make -C pmoves submodule-integrity`.
- **P2 — secrets regroup:** org secret groups by tier; funnel `--derive`
  allowlists; diff consumption-vs-stored per repo and delete the surplus.
- **P3 — archive the sprawl:** remaining ~310 stale forks on the personal
  account get archived (not deleted — the learning record stays) or moved to an
  `archive/` org namespace.
- **P4 — per-node memory roll-out:** publish cipher on SPARK/5090/B850/KVMs
  (`CIPHER_BIND=0.0.0.0` per host), mint per-agent tokens per node, wire the
  `CIPHER_<AGENT>_TOKEN` placeholder into the crush generator.

## Decision log requested from DARKXSIDE

1. Canonical org: `PMOVES-AI` vs `CATACLYSM-STUDIOS-INC`.
2. Approve funnel `--derive` replacing blanket repo-secret sync.
3. Approve per-agent token distribution into `env.shared` (node-local, never
   committed) as the fleet identity mechanism.
4. Archive-vs-transfer policy for stale forks.
