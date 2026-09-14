# Fleet shared-DB doctrine — cross-node Supabase access (cipher/JuiceFS pattern)

**Node:** SPARK · **Date:** 2026-09-14 · **Lane:** fleet-architecture
**Trigger:** operator — "from 5090 we need to fix: nodes need to have shared db like cipher, or
access across local db, same like juicefs."

## The problem, measured (2026-09-14)

Every node runs its own Supabase island. From SPARK, TCP probes across the tailnet:

- `pmoves-kvm4-2` (the data hub, 13-svc Supabase stack): kong `:8000` **closed**, PostgREST
  `:3000` **closed**, db `:54322` **closed**.
- `pmoves-5090`, `pmoves-b850-ai-top`: same — nothing published.
- All eleven fleet nodes: **zero Postgres-family listeners on the tailnet** (the JuiceFS
  reconciliation measured this across 5432/5433/54322).

Live blocker: SPARK's school lane needs `pmoves_core.youtube_videos` (the DARKXSIDE playlist
enrichment), which does not exist on SPARK's local stack — it lives on another node's
Supabase, unreachable. This is the same wall the JuiceFS meta lane hit; the fix is the same
shape.

## What "like cipher" and "like JuiceFS" actually mean here

- **Cipher** shares *memory*, not a database: a scoped API (per-agentId isolation, category +
  tag search) over the store. Agents never touch cipher's DB directly.
- **JuiceFS** shares *storage* by exposing one authoritative engine (the meta Postgres,
  tailnet-bound, role-scoped, dedicated bridge) that every node's client reaches.

The fleet DB should be BOTH: one authoritative shared surface (JuiceFS pattern) reached
through an API with scoped credentials (cipher pattern) — never raw SQL-wire fan-out with
superuser DSNs.

## Design

1. **Hub of record for shared schemas** (`pmoves_core`, `pmoves_kb`): **kvm4-2** — it already
   runs the full Supabase stack and is the standing fleet hub precedent (NATS: "all nodes
   connect here"). Node-local stacks stay authoritative for node-local state (health, node
   tables, sandboxes) — this is NOT "point everything at one DB": island mode and local-first
   resilience keep working when the tailnet is down.
2. **Expose KONG (the PostgREST front door), not raw 5432.** Kong gives row-level auth
   (service-role/anon scopes already exist), no SQL wire exposure, and matches how every
   service already speaks Supabase. Mechanism is the JuiceFS-meta pattern, one service over:
   bind the published port to the **tailnet interface** (`SUPABASE_KONG_BIND`), multi-home
   onto a non-internal bridge if needed, Tailscale ACL governs reachability.
3. **Per-node consumers** read shared schemas via a new `SUPA_REST_FLEET_URL` env (funnel-
   delivered, node-profiled) alongside the local `SUPA_REST_URL` — each service opts into
   which surface per schema. Same override mechanism that fixed this node's
   `SUPA_REST_INTERNAL_URL` today; the tier default being CLI-stack-shaped on a compose node
   is the same lesson generalized.
4. **Writes are per-schema decisions.** Enrichment (`youtube_videos`) is written by 5090-side
   tooling today: either migrate that tooling's target to the hub (preferred — one writer)
   or expose a scoped write role. Never both directions by default.
5. **Credentials**: a dedicated `fleet_reader` PostgREST-scoped key for cross-node reads;
   service-role never crosses the tailnet. Rotation rides the CHIT funnel like every other
   label.

## Why not the alternatives

- **All nodes → single DB for everything**: kills island mode, couples every service's
  health to the tailnet, and makes the hub a fleet-wide SPOF for node-local concerns.
- **Bidirectional mesh (every node exposes its DB)**: N×N auth surface, split-brain on every
  schema two nodes both write, and the JuiceFS lane already taught the cost of exposed
  superuser DSNs.
- **Sync/replication pipelines**: real cost, solves a problem we don't have yet — the fleet
  has one writer per schema today.

## Verification (once the hub binds)

```
# from any node:
curl http://pmoves-kvm4-2:8000/rest/v1/  # 401 = reachable (auth required), not closed
# then with the fleet_reader key:
.../rest/v1/youtube_videos?select=id,title&limit=1
```

## Operator gates

1. On the hub: bind kong's published port to the tailnet IP (compose env, same class as
   `SUPABASE_DB_BIND` in the JuiceFS checklist).
2. Tailscale ACL: permit `*:8000` hub-bound from fleet nodes only.
3. Funnel: mint `fleet_reader` key + `SUPA_REST_FLEET_URL` label.
4. Decide the enrichment writer migration (5090 tooling → hub) — until then SPARK's school
   queue reads a hub that may not yet hold the table; verify before wiring.

## Related

- JuiceFS exposure precedent + remaining steps:
  `pmoves/docs/operations/JUICEFS_CROSSNODE_CUTOVER_CHECKLIST.md` (2026-09-14 reconciliation)
- NATS hub addressing: `.claude/CATALOG.md` (kvm4-2)
- Cipher's scoped-API model: `pmoves/services/cipher*`, per-agentId isolation
- The supabase-db tailnet-exposure mechanism (bridge + pg_hba + bind env) already in
  `pmoves/docker-compose.yml` — this lane generalizes it to kong
