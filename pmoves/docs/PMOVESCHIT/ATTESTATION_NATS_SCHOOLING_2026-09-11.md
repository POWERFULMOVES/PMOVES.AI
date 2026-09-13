# ATTESTATION — NATS Schooling & Provenance (2026-09-11)

**Packet:** `pmoves/docs/PMOVESCHIT/nats-schooling-attestation.cgp.json` (`chit.cgp.v0.2`, signed)
**Direction (operator, DARKXSIDE):** *"this is attestation — should pub on discord and get updated
as its verified, can be minted with required provenances as example and demonstration."*
**Discord:** published via the canonical `content.published.v1` → `publisher-discord` path.
**Ledger:** register NOTE `2026-09-11T21:40:27Z` (provenance testimony) + this doc's verification table.

## What is attested

1. **The PMOVES NATS treatment was designed before it was deployed.** Trust-zone accounts
   (SYS/CORE/EDGE/CLOUD), the real 7422 leafnode listener, WebSocket for A2UI, MQTT-ready edge,
   SYS-guarded monitoring, and the two-gate trust model (NATS account = transport trust; CHIT
   signature = payload provenance) exist committed in-tree — the v0 spec (2026-08-07) and the
   `PMOVES-nats-server/pmoves/` overlay — while the running broker stayed flag-launched
   single-account until the 2026-09-11 restore. Schooling map: PR #3027.
2. **The conception chronology recorded in the register NOTE 2026-09-11T21:40:27Z** — operator
   testimony covering the agent message-board prior art, the signal-mixing methodology, the DoX
   process, the shared scrapbook, Transcribe-and-Fetch precedence, the friends-calc origin, and
   the git + playlist grounding corpus — is the provenance substrate for attribution.

## Attribution (provenance-carried; NOT a market valuation)

| Contributor | Role | Weight |
|---|---|---|
| ⚡ POWERFULMOVES / DARKXSIDE | conception, testimony, topology direction, vision | 0.5 |
| ⚙ z890-claude | author, accounts+leaf v0 design spec | 0.2 |
| ◇ crush_glm52 | schooling map, verification, attestation transport | 0.3 |

Weights are Dirichlet-normalized provenance weights on the attestation packet. Settlement/market
valuation remains behind the Tokenism production-activation gate (dry-run until the signed pack).

## Verification ledger (this is the "updated as verified" surface)

| # | Claim | State | Evidence |
|---|---|---|---|
| att-nats-01 | Fork overlay exists in-tree | **VERIFIED** | `PMOVES-nats-server/pmoves/` (conf, README, examples) |
| att-nats-02 | v0 spec dated 2026-08-07 | **VERIFIED** | `pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md` |
| att-nats-03 | Broker ran single-account flags until restore | **VERIFIED** | register RELEASE `2026-09-11T19:59:45Z` + map §1 |
| att-prov-01 | Operator testimony recorded | **VERIFIED** | register NOTE `2026-09-11T21:40:27Z` |
| att-topo-01 | Floating-topology call recorded | **VERIFIED** | PR #3027 §5.1 (`e249a50a1`) |
| att-verif-01 | Third-party chronology verification (4090/Z890/5090) | **PENDING** | routed per identity-proposal review paths |
| att-mint-01 | Discord publication delivered | **VERIFIED** | publisher `/publish` → `{"ok":true}` (2026-09-11T23:10Z), embed carries attribution + ledger pointer |

**Update rule:** a claim flips state only with evidence; every flip files a register row and may
re-publish the Discord attestation. The packet's `sig` covers the attestation content + attribution
(transport signature, `chit-signing-v01`); provenance weight changes re-sign.

## Why this is also a demonstration

The publication went out through `publisher-discord`'s own `POST /publish` surface (the service
holds the webhook; `{"ok":true}` = delivered). The fuller loop — broker → `content.published.v1`
subscribe → embed — was attempted first and is **recorded as a finding, not a failure**: the
publisher's NATS leg has been dead since 2026-08-07 (healthy container, zero subscription
re-registration; image/source layout drift; recreate with current env completed but the image's
loop still silent). Residuals filed to the register: publisher NATS leg, secrets-funnel
chit-export abort on malformed WGER_ADMIN_PASSWORD (pre-existing bundle defect, unowned).
