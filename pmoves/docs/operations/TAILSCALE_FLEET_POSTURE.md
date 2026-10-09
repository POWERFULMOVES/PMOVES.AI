# Tailscale in the PMOVES runtime — self-host posture, forks, and the mesh doctrine

**Node:** SPARK · **Date:** 2026-09-15 · **Lane:** tailscale fleet posture (operator-directed)
**Trigger:** "tailscale is to be self hosted and should run when pmoves runs, not a
downloaded client unless launching from the fork."

## The two forks (state measured 2026-09-15)

| Fork | Upstream | State | Role |
|---|---|---|---|
| `PMOVES-Tailscale` | `tailscale/tailscale` | **~5 months behind** (pushed 2026-04-19) | the client/server source — host-level builds come from here |
| `PMOVES-ScaleTail` | `tailscale-dev/ScaleTail` (official Tailscale org) | at parity (pushed today) | **sidecar configurations for Docker** — per-service tailscale as a compose sidecar |

## The doctrine, made concrete

**"Tailscale runs when PMOVES runs"** — three tiers, replacing the system-downloaded client:

1. **Containerized services** — the ScaleTail pattern: a tailscale sidecar container per
   service (or per overlay group), with the service sharing the sidecar's network
   namespace. Mesh membership is then tied to the compose lifecycle: `overlay-up-*` IS
   mesh join, `overlay-down` is mesh leave. No system daemon, no version drift with the
   repo. Adopt per-service deliberately (needs `/dev/net/tun` + `NET_ADMIN` on the host).
2. **Host-level needs** (node identity, subnet routes, the bus itself) — build from
   `PMOVES-Tailscale`, never the app-store/downloaded client. The fork is 5 months
   behind: a **fork-sync lane is owed** before any host build (tailscale/tailscale moves
   weekly; building from a stale fork re-creates the "old image" problem in compile form).
3. **Coordination** stays on the current tailnet control plane until a self-hosted
   control plane (headscale — already funnel-delivered: `HEADSCALE_URL`,
   `HEADSCALE_API_KEY`) is deliberately promoted. That promotion is its own lane with its
   own ACL migration; do not couple it to the client-side adoption.

## OAuth secrets — found, and the one remaining paste

The OAuth client credentials were added as **environment secrets on the PMOVES-Tailscale
fork** (environment `PMOVES-Tailscale`, branch-scoped to main). The mint step
(`ts_oauth_mint.sh`, #3070) lives on **PMOVES.AI's** sync workflow — where the CHIT
pipeline starts — and reads **repo-level** secrets there. Environment secrets on a
different repo cannot reach it.

One paste closes the whole TS-key loop:

```
gh secret set TAILSCALE_OAUTH_CLIENT_ID   -R POWERFULMOVES/PMOVES.AI
gh secret set TAILSCALE_OAUTH_CLIENT_SECRET -R POWERFULMOVES/PMOVES.AI
```

Then dispatch "Sync Secrets to Local Environment"; every node: `PMOVES_NODE=<n> make
secrets-pull` + `secrets-funnel-sync-from-bundle`; the API probe goes green and every
sync self-refreshes the credential.

## Ordered next steps

1. Operator: the two `gh secret set` lines above (the fork's environment copy can stay
   for the fork's own future workflows).
2. Fork-sync lane for `PMOVES-Tailscale` (5 months of upstream; then host builds are
   current).
3. ScaleTail adoption pilot: one service (candidate: a workers-overlay service that
   wants tailnet egress) gets the sidecar template as a proof, then pattern-roll.
4. Headscale promotion: separate lane, own decision, after 1–3.

## Provenance

- Fork states via GitHub API (2026-09-15); ScaleTail = `tailscale-dev/ScaleTail`,
  templates/service-template carries compose.yaml + .env pattern.
- OAuth placement verified via environments API (repo + fork).
- Mint machinery: `pmoves/scripts/ts_oauth_mint.sh`, #3070 (`d4079c111`).
