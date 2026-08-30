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
| Land the design spec (#2492) | **done** — merged 2026-08-12 | — |
| Wire fork as submodule (#2493) | **done** — merged 2026-08-12 | — |
| This runbook + AGNOTE claim | **done** | — |
| Phase 1 — mint nsc operator/accounts/users | **DONE** (verified 2026-08-15) | — |
| Phase 2 — hub: config + `leafnodes{7422}` + SYS | **config written + PROVEN**; not yet wired to prod | Known-Road compose (operator-auth) **+ requires Phase 3 in the same window** |
| Phase 3 — migrate CORE services → `.creds` | ready to sequence | Known-Road compose |
| Phase 4 — EDGE leaf (nano-1 @ 7422) | **leaf config written + PROVEN**; awaits P2 | jetsons ARE live (2026-08-15) |
| Phase 5 — CLOUD leaf (KVM) | awaits P2 | cross-node access (Hostinger) |
| Phase 6 — `pmoves-nats-mcp` → CORE `.creds` + CHIT-signed publish | **done** — merged as #2496 | `.creds` flip rides P2/P3 |

### Phase 1 is no longer blocked (verified on z890, 2026-08-15)

The gate below said "`nsc` not installed on z890". That is **stale** — measured now:

- `nsc` is installed; the vault exists at `%APPDATA%/pmoves/nats-nsc` (config/ data/ keys/).
- Operator `PMOVES` + all four accounts are minted: **SYS, CORE, EDGE, CLOUD** (`nsc list accounts`).
- Four user creds exist, including **`EDGE/edge-nano-1.creds`** — the jetson leaf credential itself.

So the critical-path unblocker is cleared and **Phase 2 is what everything now waits on.**

### ⚠️ Sequencing warning for Phase 2 (read before authorizing)

The production hub (`pmoves-nats-1`) is launched from **CLI flags** with plaintext
`--user/--pass` (`nats:pmoves` defaults). Swapping it to the account/JWT config below is
**not backwards compatible**: every existing client authenticating as `nats:pmoves` will fail
with an authorization violation the moment the hub starts requiring account creds. **Phase 2 and
Phase 3 must land in the same maintenance window**, or the hub must temporarily run both auth
modes. Do not merge a Phase-2 compose swap expecting it to be a no-op.

---

## The gates (what the operator/tooling must clear before deeper slices)

1. ~~**`nsc` install**~~ — **CLEARED 2026-08-15.** `nsc` is installed on z890 and Phase 1 is minted:
   Operator `PMOVES` → 4 Accounts (SYS/CORE/EDGE/CLOUD) → 4 user `.creds` (incl. `edge-nano-1`),
   vault at `%APPDATA%/pmoves/nats-nsc`. This is no longer the critical path — **Phase 2 is.**
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

## Measured implementation findings (z890, 2026-08-15, nats:2.11.8-alpine)

Established by building the hub + leaf in **throwaway containers** (production `pmoves-nats-1`
never touched) and running the spec §10 tests. Configs live at `pmoves/config/nats/`.

**Spec §4's "open detail" is RESOLVED.** The question was whether a leaf's account is pinned by an
`account:` field on the remote or implied by the creds. Both sides observed:
- **Hub side — implied by the creds.** A leaf presenting `EDGE/edge-nano-1.creds` shows up in hub
  `/leafz` as `account=AAS574M5ZNQE…`, exactly the EDGE account pubkey. No `account:` field needed.
- **Leaf side — separate, defaults to `$G`.** The leaf logs `Leafnode connection created for
  account: $G`. That is correct for a leaf defining no local accounts; `account:` on the remote
  only pins WHICH LOCAL account the link binds to.

**Five config gotchas — each one silently prevents boot or attachment:**

| # | Gotcha | Symptom | Correct form |
|---|--------|---------|--------------|
| 1 | `operator:` omitted | `error resolving system account: account validation failed` (hub won't boot) | `operator: <operator JWT>` — **required**; spec §3's snippet omits it |
| 2 | `max_memory` in `jetstream{}` | `unknown field "max_memory"` — config never loads | `max_mem` |
| 3 | `no_advertise` inside a `remotes[]` entry | `unknown field "no_advertise"` — config never loads | block-level, directly under `leafnodes {` |
| 4 | `${VAR:-default}` | `variable reference ... can not be found` | no shell defaults; render it or export it |
| 5 | `$VAR` inside a quoted string | runtime `lookup for host "$VAR": no such host` | variable must stand alone: `urls: [ $PMOVES_NATS_LEAF_URL ]` carrying the whole URL |

Gotchas 2 and 3 were **already present in the committed `elder-melchor-leaf.conf`** — so that file
could never have loaded even if its port/auth had been right. That is independent corroboration of
the 2026-08-08 forensic finding that no coherent leaf has ever run in PMOVES production.

**§10 acceptance tests — status:**

| Test | Result |
|---|---|
| Leaf handshake at 7422 | **PASS** — `pmoves-edge-nano-1` attached, `account=<EDGE pubkey>`, rtt 244µs |
| `4222`-target refused | **PASS** — `attempted to connect to wrong port` (the exact reason the old leaf conf never worked) |
| EDGE↔CORE isolation | **PASS** — CORE subscriber on `test.>` received **0** from an EDGE publisher on `test.isolation`; positive control (EDGE→EDGE) received 1 |
| Export/import round-trip | not yet — needs the §5 matrix wired (Phase 4) |
| Two-layer trust / MCP signed publish | not yet — rides Phase 3 `.creds` migration |
| SYS-guarded monitoring, cred rotation | not yet — Phase 2/3 |

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
