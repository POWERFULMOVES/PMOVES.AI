# NATS Accounts + Leaf-Topology — Rollout Runbook

**Companion to:** `pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md`
**Decision:** 2026-08-08 — operator adopted the spec + wiring the `PMOVES-nats-server` fork.
**Owner:** z890-claude (KEYSTONE, infra). **Merge gate:** DARKXSIDE (Control).

This turns the spec's §9 phases into a gated, independently-testable sequence. Each phase names
what is **actionable now** vs. what is **operator-gated** and why. Nothing here bypasses a gate.

---

## Why (one paragraph)

A git forensic (2026-08-08) established there is **no coherent leaf in production**: the `nats-leaf`
pattern was a 2026-03-19 WSL2 Docker-routing workaround (#1034) that was reverted 3 days later
(`feafffae6`) but whose config files persisted and got copied into every later "leaf" (none ever
worked — `elder-melchor-leaf.conf` even targets client port 4222, not a 7422 leaf port). The current
documented topology (`CATALOG.md`) is a hub-and-spoke of **independent standalone brokers on KVM4-2**,
explicitly **not** leaf-federated. This lane builds the *real* leaf trust model for the first time.

---

## Status board

| Slice | State | Gate |
|-------|-------|------|
| Land the design spec (#2492) | **done** (draft PR) | operator merge |
| Wire fork as submodule (#2493) | **done** (draft PR) | operator merge |
| This runbook + AGNOTE claim | **done** | operator merge |
| Phase 1 — mint nsc operator/accounts/users | **blocked** | `nsc` not installed on z890; custody decision (#1901) |
| Phase 2 — hub: fork config + `leafnodes{7422}` + SYS | blocked on P1 | Known-Road compose/Dockerfile (operator-auth) |
| Phase 3 — migrate CORE services → `.creds` | blocked on P2 | Known-Road compose |
| Phase 4 — EDGE leaf (nano-1 @ 7422) | blocked on P2 | cross-node access (jetson) |
| Phase 5 — CLOUD leaf (KVM) | blocked on P2 | cross-node access (Hostinger) |
| Phase 6 — `pmoves-nats-mcp` → CORE `.creds` + CHIT-signed publish | **partly actionable** | packaging now; `.creds` wiring on P1 |

---

## The gates (what the operator/tooling must clear before deeper slices)

1. **`nsc` install** — Phase 1 mints Operator `PMOVES` → 4 Accounts (SYS/CORE/EDGE/CLOUD) → user
   `.creds`. `nsc` is not on z890. Install is the critical-path unblocker for everything after slice 3.
2. **Custody decision (#1901 precedent)** — spec §3/§8: v0 = **file-mounted Docker secret** for the
   nsc operator seed + `.creds` (the `_FILE` convention across `pmoves/services/**`); CHIT-vault custody
   is the documented follow-up. **Final custody choice is the operator's** per #1901 §7 — confirm before minting.
3. **`secrets_manifest.yaml` entries (§8)** — zero-access under damage-control. Operator adds the new
   secret IDs via the **example → manifest → funnel** pipeline (never hand-edit `env.shared`).
4. **Known-Road compose/Dockerfile/config** — the hub service swap (flag-launched → fork image with
   accounts + 7422), publishing 7422, and the leaf `.conf` edits are operator-authorized Known-Road domains.
5. **Cross-node access** — Phases 4–5 attach jetson (EDGE) and a KVM (CLOUD) as leaves; needs those nodes.

## Actionable now (no gate)

- **Phase 6a packaging** for `pmoves-nats-mcp` (§7b): add `Dockerfile`, a CORE-bound compose stanza,
  `examples/` (raw + signed publish, subscribe) — the `.creds` auth path is written creds-optional
  (back-compat raw publish per spec §7b.2) so it lands before minting; flip to CORE `.creds` at P1.
- **Fork config templates** in `PMOVES-nats-server` (§7a): `conf/pmoves-nats.conf` with `${...}`
  placeholders for `resolver_preload` (rendered at funnel time), a thin Dockerfile (stock
  `nats-server` + baked conf + entrypoint that templates the resolver), `examples/` leaf-attach demo.
  These carry **no secrets** — the account JWTs are public and render at funnel time; the seeds/`.creds`
  stay file-mounted secrets.

## Acceptance tests (spec §10 — run per phase)

Leaf handshake at 7422 (4222 refused) · EDGE isolation (CORE-private subject denied) · export
round-trip (`mesh.gpu.status.v1` ↑, `image.gen.request.v1` ↓) · two-layer trust (signed
`tokenism.prosodic.bpm.v1` accepted, unsigned crosses transport but fails CHIT verify) · MCP signed
publish · SYS-guarded monitoring (`:9223` needs SYS creds) · cred rotation emits
`tokenism.credential.rotated.v1`.

## Coordination

- **z890 (me):** slices 1–3 done; Phase 6a packaging + fork config templates next (actionable).
- **operator (DARKXSIDE):** install `nsc`, confirm custody (#1901), add manifest entries, authorize the
  Known-Road compose swap.
- **4090's anchor ratchet (#2488)** now guards documented-command drift — the hub runbook commands here
  must resolve (GHOST_TARGET/PATH), which keeps this doc honest as the config lands.
