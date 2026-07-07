# Supabase Safe Data-Restart & Key-Reconciliation Runbook

> **Data-service discipline:** Supabase holds durable state (auth, projects, RAG
> embeddings, ledgers). Restarts must preserve the data volume and be
> dependency-aware. Never restart it ad-hoc — follow this runbook. List the
> dependencies first so the blast radius is clear.

## 1. Topology — what Supabase is, and what depends on it

**The authoritative store:** one Postgres, in the `supabase-db` container, backed by
the **`supabase-db-data`** Docker volume. **This volume is the source of truth. It is
never removed during a restart.**

**Runtime identity (verify before acting):**
```bash
docker ps -a --filter name=supabase --format '{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Status}}'
make -C pmoves supa-runtime-guard      # PASS = one runtime; FAIL = mixed CLI/compose drift
make -C pmoves supa-env-doctor         # layered-env key conflicts
```
> **Known drift (2026-07-06):** the running stack is compose project **`supabase`** (a
> standalone bring-up, its own generated JWT secret). The pmoves runtime-guard reports
> `compose running: 0` because it doesn't own that project — so `env.shared`'s
> `SERVICE_ROLE_KEY` is signed by a *different* JWT secret and every client gets **401**.
> This is the condition this runbook reconciles.

**Auth layer (reads keys at startup — restart these to adopt new keys):**
`supabase-kong` (gateway :8000) · `supabase-auth` (GoTrue, reads `JWT_SECRET` +
`SERVICE_ROLE_KEY`) · `supabase-rest` (PostgREST, validates JWT) · `supabase-realtime`.
Restarting these **does not touch `supabase-db-data`**.

**Dependents (the blast radius — every client re-hydrates with new keys):**

| Dependent | Consumes | Restart after key change |
|-----------|----------|--------------------------|
| Archon (server/mcp/frontend) | `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | `make up-archon-native` |
| Cipher Memory (:8105) | Supabase DB/keys | `make up-cipher` |
| PMOVES-Wealth (Firefly) | `SUPABASE_*` / DB | its compose service |
| n8n, agent-zero, apps/core/media/ui | `SUPABASE_URL`/keys (compose refs) | affected compose services |

> Source of the list: every `pmoves/docker-compose*.yml` that references
> `SUPABASE_URL|SERVICE_ROLE_KEY|JWT_SECRET|supabase-kong`. Re-derive with:
> `grep -lE "SUPABASE_URL|SERVICE_ROLE_KEY|JWT_SECRET|supabase-kong" pmoves/docker-compose*.yml`

## 2. Hard safety rules (aligned to official Supabase self-hosting docs)

- ✅ **Recreate, not restart.** Per official docs, "a plain `docker compose restart` is not
  sufficient as it does not pick up configuration changes." After a key/secret change,
  **force-recreate** the affected services (`--force-recreate`, or the fork's `run.sh recreate`).
- ✅ Preserve data: recreate the **auth layer only**; leave `supabase-db` (and its volume) running.
  Recreate does **not** delete data — only `reset.sh` / `down -v` deletes `volumes/db/data`.
- ⛔ **Never** `docker compose down -v`, `supabase-clean`, `reset.sh`, or remove `supabase-db-data` — data loss.
- ⛔ Never rotate keys without recreating **all** dependents in §1 — half-rotated keys = silent 401s.
- ✅ One runtime only. Resolve CLI-vs-compose drift first: `make -C pmoves supa-runtime-reconcile`.
- ✅ Keys are machine-emitted. Regenerate via the official scripts → `env.shared` via the pipeline;
  never hand-edit `env.shared`. **Review the generated `.env` before proceeding** (official guidance).

## 3. Procedure — reconcile keys with a safe restart

**Goal:** make `env.shared` (JWT_SECRET + ANON_KEY + SERVICE_ROLE_KEY) and the running
Supabase agree, without losing data.

1. **Confirm one runtime + data volume present.**
   ```bash
   make -C pmoves supa-runtime-guard
   docker volume ls | grep supabase-db-data     # MUST exist; do not delete
   ```
2. **Regenerate a consistent key set — official two-script sequence** (secrets first, then the
   asymmetric JWT signing key pair; review `.env` before proceeding):
   ```bash
   bash pmoves/scripts/supabase/generate-keys.sh       # POSTGRES_PASSWORD, SECRET_KEY_BASE, VAULT_ENC_KEY, JWT secret
   bash pmoves/scripts/supabase/add-new-auth-keys.sh    # asymmetric JWT signing key pair (if present in the fork)
   ```
   Route the values into `env.shared` through the pipeline (machine-emitted, not hand-edited):
   ```bash
   make -C pmoves secrets-funnel        # or secrets-rotate KEY=... per reference_pmoves_secrets_pipeline
   make -C pmoves ensure-env-shared     # applies brand_defaults incl. Archon SUPABASE_* aliases
   ```
   > Legacy `anon`/`service_role` keys stay functional; the modern `SUPABASE_PUBLISHABLE_KEY` /
   > `SUPABASE_SECRET_KEY` may run alongside them. Keep whichever set the clients consume consistent.
3. **Force-recreate the auth layer** (picks up the new keys — a plain restart will NOT; data untouched):
   ```bash
   docker compose -p supabase up -d --force-recreate \
       supabase-kong supabase-auth supabase-rest supabase-realtime
   ```
   > Target the **actual running project** (`-p supabase` per §1 — not the pmoves runtime if it isn't
   > the one serving). `supabase-db` and `supabase-db-data` are left running: **recreate ≠ data loss.**
4. **Verify the store accepts the new key:**
   ```bash
   make -C pmoves archon-native-config          # SUPABASE_SERVICE_KEY: <set>, URL populated
   curl -s -o /dev/null -w "%{http_code}\n" -H "apikey: <new service key>" \
        "http://localhost:8000/rest/v1/archon_settings?select=key&limit=1"   # expect 200, not 401
   ```
5. **Re-hydrate dependents** (§1 table) so they pick up the new keys:
   ```bash
   make -C pmoves up-archon-native      # Archon: server+mcp+frontend
   make -C pmoves up-cipher             # Cipher, etc. per the dependents table
   ```
6. **Confirm health:** `archon-server :8181/health`, `archon-mcp :8051/health`,
   `archon-frontend :3737`, plus each dependent's health endpoint.

## 4. Rollback

If a dependent won't authenticate after the restart, the DB data is still intact
(volume never touched). Re-check §3.4 (key populated + accepted); if the running stack
was a standalone project, ensure step 3's explicit `-p supabase` recreate actually
restarted *that* project's auth services, not a second (stopped) pmoses runtime.

## 5. Multi-node consistency (the root cause of the "Archon workaround")

The 401 that forced the Archon workaround **is** the multi-node failure mode: two Supabase
runtimes with **different, independently-generated key sets**. Fleet rule — **one authoritative
key set, distributed by the pipeline; never a second stack minting its own keys.**

- **One authoritative Supabase per fleet** (or a deliberately federated set). Every node/client
  reads its keys from the same machine-emitted `env.shared` lineage — not from a locally
  bootstrapped stack. `supa-runtime-guard` must PASS on every node (no rogue/standalone runtime).
- **Prefer asymmetric JWT signing keys** (`add-new-auth-keys.sh`). Clients verify with the
  **public** key, so key distribution across nodes is safe (only the issuer holds the private key)
  and rotation doesn't require shipping a shared secret to every node.
- **Drift detection:** before wiring any new client, run `supa-env-doctor` +
  `supa-runtime-guard`, and confirm the client's service key is accepted (§3.4, expect 200 not 401).
  A standalone project (e.g. `-p supabase` up 3 days with its own keys) is the smell — reconcile it
  to the authoritative set, don't paper over it with per-client key copies.
- **Read replicas / HA:** official managed Supabase does multi-node via read replicas (single
  primary, JWT keys shared cluster-wide). Self-hosted has no built-in HA — treat the primary as
  the single source of truth and replicate the **key set**, not a second control plane.

## References
- **Official:** [Self-hosting with Docker](https://supabase.com/docs/guides/self-hosting/docker)
  (key gen `generate-keys.sh` + `add-new-auth-keys.sh`; `recreate` not `restart`; data persistence),
  [API keys](https://supabase.com/docs/guides/api/api-keys) (publishable/secret vs legacy anon/service_role).
- Targets: `supa-start` / `supa-stop` / `supa-restart` / `supa-env-doctor` /
  `supa-runtime-guard` / `supa-runtime-reconcile` (pmoves/Makefile).
- Key gen: `pmoves/scripts/supabase/generate-keys.sh` (+ `add-new-auth-keys.sh` if present in the fork).
- Assurance: `pmoves/configs/tac_trees/supabase.tac.yaml` (this runbook is its remediation path).
- Secrets pipeline: `reference_pmoves_secrets_pipeline` memory; env is machine-emitted.
- Related: `project_duplicate_supabase_pooler`, `project_cipher_internal_network_root_cause`.
