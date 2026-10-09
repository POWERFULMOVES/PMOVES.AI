# Fleet bring-up TODOs — 2026-09-01

**Node:** `PMOVES-4090` · `4090-claude` · founder directives this session
**Companion:** [`4090-open-findings-2026-08-31.md`](./4090-open-findings-2026-08-31.md) (defects), this file (work)

**Scope, so this does not compete with the canonical plans.** This is a
*bring-up* queue: the specific blockers between the fleet's current state and
services running, found by measuring this node on 2026-09-01. It does **not**
supersede `pmoves/docs/ROADMAP.md` or `pmoves/docs/NEXT_STEPS.md`, which carry
product and release priority and which `pmoves/AGENTS.md:34-36` makes mandatory
reading before changes. Where they disagree about what to do next, the canonical plans win on
*what to build* and this file wins on *what is currently broken underneath it*.
Items here graduate into those plans or close; nothing here is a long-lived
priority statement.

Every item below is measured, not recalled. Where a number appears, the command
that produced it is next to it, because a tally quoted forward is how this fleet
keeps rediscovering the same defect.

---

## T1 — the 7422 leafnode listener has never been published  ·  **P1, blocks the most**

The hub/spoke NATS topology is designed, the spokes are written, and the hub
listener is not exposed.

```
docker port pmoves-nats-1
  4222/tcp -> 0.0.0.0:4222
  8222/tcp -> 127.0.0.1:9223
  (no 7422)
```

Both leaf configs say so themselves:

- `pmoves/config/nats/edge-nano-1-leaf.conf:29` — *"Hub (z890) running pmoves-nats.conf with leafnodes{listen:7422}"*
- `pmoves/config/nats/elder-melchor-leaf.conf:17` — *"Z890 hub running pmoves-nats.conf with leafnodes{listen:7422} **PUBLISHED**"*

The spec is `pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md`
— four trust-zone accounts (SYS/CORE/EDGE/CLOUD), nsc/JWT resolver, `7422`
listener. **Status line still reads "design — operator review"** after ~4 weeks.

**This one gap blocks:** GEOMETRY BUS deploy with correct leaves · Jetson
dispatch (work-order L4, recorded as "#2492 phases 2/4") · "each node needs to
be able to host" · Reticulum, which should not start until the mesh is stable.

**Do:** dust off the v0 spec against current NATS docs → publish 7422 on the hub
→ verify `curl http://<hub>:9223/leafz` shows `leafnodes >= 1` (the check is
already written into `edge-nano-1-leaf.conf:46`) → then GEOMETRY BUS.

**Note while there:** `4222` publishes on `0.0.0.0`. Deliberate or not, it is
worth a decision on a laptop that travels.

## T2 — Glances is configured and deployed nowhere  ·  **P1, unblocks T3**

```
curl localhost:61208/api/4/status   ->  000
grep -rl glances pmoves/docker-compose*.yml   ->  (no matches)
```

Config exists — `pmoves/config/profiles/hermes/glances.json`,
`z890-glances.conf` — with no compose service anywhere. Designed ≫ deployed,
the same shape as JuiceFS.

This is the tool that answers T3. Founder: *"glances can validate system specs
packages needed."*

**Do:** add a Glances service (per-node, loopback-bound, tailnet via Serve —
not a new WAN port) → read specs off each node → fill T3.

## T3 — the three KVM profiles have no hardware block, on purpose  ·  **P2**

`kvm4-1.yaml`, `kvm4-2.yaml`, `kvm2.yaml` declare `deployment_class`,
`provides: [egress, always-on]`, `runtime_shape: [persistent]` and `reach:` —
and **no hardware**.

> **T3 is BLOCKED on PR #2867.** Those three files live on branch
> `feat/node-role-axis` and are **not on `main`**. Anyone picking T3 up from
> this commit alone will find at most one of them. Do not start T3 until #2867
> merges.

That was deliberate: the work order (L12) records
`kvm-exit-node-hosting-strategy.md` as STALE with *"wrong kvm2 specs"*, and
copying a number a work order flags as wrong launders it into config where the
next reader finds it with no warning attached. `profile_loader` requires only
`id`, so the absence is safe.

**Do:** fill from Glances (T2) or `nproc` / `free -g` **on** each node. Also
resolve the `kvm4-2` over-subscription the 2026-08-27 infra analysis records
(compose limits well above its RAM) before putting data-plane services there.

## T4 — doc reconciliation: tailscale · rustdesk · pinokio · docker · glances  ·  **P2**

Founder directive. The 2026-08-27 work order (L12) already carries freshness
verdicts for several of these — **use them rather than re-auditing**, and note
that the work order's own validation gate says: *"Doc changes: freshness-verdict
table from L12 audit before rewriting any platform doc."*

| doc area | L12 verdict (2026-08-27) | action |
|---|---|---|
| Pinokio | product is **8.0.x**; PINOKIO8 ADR **unmerged** (worktree `pinokio8-spec`); the two 04-23 guides **STALE** (pre-8, no pterm) | merge ADR, refresh both guides |
| Tailscale | runbook/TAC **CURRENT** (kvm4-1 egress confirmed); `kvm-exit-node-hosting-strategy.md` **STALE**; sovereign-egress doc **missing from main** | fix strategy tables, rehome sovereign-egress |
| RustDesk | **current-enough** (relay healthy, console-injection pending) | status note only |
| Docker | networking model is `HYBRID_TOPOLOGY_NETWORK_AWARENESS.md` — **implemented further than its DRAFT label says** (`TopologyContext` has the fields, `PMOVES_NETWORKS` injected, 206 services agree / 0 mismatch) | drop the DRAFT label; record the gaps in T5 |
| Glances | config only, no service | see T2 |

## T5 — network-awareness gaps  ·  **P2**

Measured 2026-09-01 across all `pmoves/docker-compose*.yml`:

```
PMOVES_NETWORKS == networks:            208 services   (was 206)
MISMATCH                                  0
networks: but no PMOVES_NETWORKS         57   (network-blind)
PMOVES_NETWORKS but no networks:          0   (was 2 -- both clip-embed; FIXED, PR #2870)
/topology endpoint                        2   (media-audio, media-video only)
gw-priority applied                       0   of 107 that need it
```

- **`gw-priority`: 0 of 107.** Auto-networking rule #2 — the documented fix for
  the host-unreachable class — is unapplied everywhere. It appears exactly once
  in the repo, as a *comment* in `services/common/topology.py:27`. Highest
  leverage item here.
- **`clip-embed` / `clap-embed` — FIXED in PR #2870.** clip-embed had
  `PMOVES_NETWORKS` and no `networks:` key at all; clap-embed had a `networks:`
  key with the wrong contents. **Both** call `from_pretrained` at first request
  and sat on `internal: true` tiers only, so each would report healthy and then
  fail its first real request. Recorded here because the lesson generalises:
  fixing one by copying its sibling propagated a second defect. Matching a twin
  is only sound if the twin has been exercised — and neither had ever run.
- **AgentGym cannot start standalone**: `docker-compose.agentgym.yml` declares
  `app_tier`/`api_tier`/`data_tier`/`monitoring_tier` as `external: true` with
  **no `name:` mapping**; none of those networks exist and nothing creates them.
  `docker-compose.comfyui.yml` does the identical thing correctly
  (`api_tier: {external: true, name: pmoves_api}`) — it is the template.
- **`/topology` is on 2 of 263 services** — the spec's two named first adopters.
  The helper was never rolled out from `services/common`.

## T6 — point the REMAINING consumers at the existing resolver  ·  **P2**

**Corrected 2026-09-01 after review.** An earlier version of this file claimed
node-vocabulary.yaml had "one reader, zero runtime consumers" and proposed
building a resolver in `services/common`. **That was false**, and following it
would have created a second resolver beside a working one.

`pmoves/tools/node_identity.py` (11.5 KB) already loads the vocabulary
(`VOCABULARY_PATH`, line 41) and exposes `load_vocabulary()`, `canonical_node()`,
`this_node()`, `load_registry()`, `agents_claiming()`, `resolve_identity()`.
Seven consumers, including every launcher at session startup:

```
pmoves/scripts/claude-pmoves.sh          pmoves/tools/crush_configurator.py
pmoves/scripts/crush-pmoves              pmoves/tools/identity_lineage.py
pmoves/scripts/windows/claude-pmoves.bat pmoves/scripts/validate_agent_registry.py
```

*How the wrong claim happened, because the method matters more than the fact:*
the search that produced it was a repo-wide ripgrep that **timed out** and
returned partial results. It reported the CI workflow and nothing else, and I
read silence as absence. A timed-out search is not a measurement.

**The real remaining work is smaller than what this file first proposed** —
these three still resolve node names on their own instead of asking
`node_identity.py`:

- `pmoves/tools/agent_terminal_theme.py::_HOST_MAP`
- `agent_registry.yaml`'s 17 raw `node_affinity` tokens (no validation against
  the vocabulary)
- the claim register's 20 agent names

So: inventory those, point them at the existing resolver, and add a gate that
rejects a `node_affinity` token the vocabulary does not know. **Do not write a
new resolver.**

## T7 — A0 + Archon dispatch wiring  ·  **P2**

**Both are already up** (measured 2026-09-01) — no bring-up needed:

```
pmoves-agent-zero-1   Up 42 hours (healthy)   supervisor :8080, runtime :8081
pmoves-archon-1       Up 3 days (healthy)     :3090
pmoves-archon-postgres Up 3 days (healthy)
```

A0's NATS is connected with JetStream on, stream `AGENTZERO`, subjects
`agentzero.task.v1` + `agentzero.memory.update`, runtime `a0-connector.v1`.

Founder intent: **GLM 5.3 in A0**; **Claude Code + Crush in Archon** for
dispatch. Cipher (`:8105`, verified 200) is the memory/dispatch path.

**Do:** verify A0's live model actually resolves to GLM 5.3 rather than a preset
default — the known open question is A0 preset-vs-env precedence — and confirm
Archon's dispatch runners. Neither is a bring-up; both are a *check that the
declared model is the running model*, which is this fleet's recurring defect
class.

## T8 — Reticulum  ·  **parked, by directive**

Founder: *"we will be setting up reticulum network once mesh nodes stabilized."*
Blocked on T1. Do not start before the leaf topology is live and stable —
starting a second mesh layer over an unstable first one makes both
undiagnosable. Blueprints are in `pmoves/docs/` (Haven + Reticulum).

## T9 — persona grounding: run → store → wire  ·  **P3, long**

`pmoves/tools/catalog_lensing_engine.py` is **2070 lines** (measured, not
recalled) and — correcting the standing note that it "has never been run" — it
**has** run and produces well-formed output:

```
pmoves/data/test_catalog_8_lensed.json   8480 bytes, 8 entries
  lenses: multi_agent_orchestration · ai_memory_systems ·
          consciousness_embodiment · local_first_sovereignty ·
          cultural_microbiome
  chit_signature: {delta, Hz, kappa, A, F, ...}
```

So the engine works. What does **not** exist is 325-grounded output: those 8
entries are a synthetic fixture (`item-001`, `arxiv.org/abs/2401.12345` is a
placeholder id), and it is the only lensed artifact under `pmoves/data/`.

The accurate gap statement is therefore narrower and more encouraging than the
old one: not *"build and run it"* but **run it on the real 325 catalog · store
the output · wire it at Archon mint time**. The 8 Supabase personas are still
generic role stubs rather than lensed combinations.

Note for the 5×5 latent knob: the fixture carries exactly **five lenses** with a
CHIT signature per item. Whether that five is the same five as the knob's is
worth checking before anything is built on the assumption that it is.

---

## Suggested order

`T1` (unblocks the mesh) → `T2` → `T3` (T2 supplies it) → `T5`'s `gw-priority`
and AgentGym fixes (mechanical, high leverage) → `T6` (wiring, data done) →
`T7` (verify, not build) → `T4` docs → `T8` when stable → `T9` long.

`T4` and `T5` can run in parallel with `T1` — they touch different files.

<!-- GRAPHITI_MARK: 4090-claude::FLEET-BRINGUP-TODOS::2026-09-01 -->
