# JuiceFS cross-node (L6): scoped meta role, then tailnet exposure

**Node:** z890 (authoring) · target host **B850** (the JuiceFS metadata home)
**Date:** 2026-08-18 · **Lane:** L6 from the 2026-08-18 lane board
**Change classes:** `migrations:` (scoped role), later `compose:` (db exposure)

---

## The blocker, with the mechanism

Cross-node JuiceFS mounts on 4090 / 5090 / jetson are blocked because remote nodes
cannot reach B850's metadata engine. JuiceFS documents this as a hard requirement:

> "If you need to share the same file system across multiple nodes, ensure that all
> nodes has access to the Metadata Engine."

Measured from two independent nodes — `pmoves-b850-ai-top:5432` is unreachable from
**z890** and from **nano-1**.

**Why**: `supabase-db` sits on `pmoves_api` + `pmoves_data`, and **both are
`internal: true`**. Docker installs no DNAT rules for containers on internal-only
networks, so published ports are *recorded but never plumbed*. This trap is already
documented in-repo for NATS (`pmoves/docker-compose.yml:2906`), which solved it by
multi-homing onto the non-internal `pmoves_external`.

## The privilege finding that orders the work

JuiceFS's metadata DSN authenticates as **`supabase_admin`** —
`rolsuper = t, rolcreaterole = t`, a **full superuser**. That is also the credential
exposed in `ps` / `docker inspect` for ~11 days and **still un-rotated**.

Exposing a port changes the risk profile of the role behind it. Today that superuser
is only reachable in-stack; once the port is tailnet-reachable it becomes a
network-exposed auth surface. Two individually-manageable facts compound.

### Order (a deliberate refinement of rotate -> role -> expose)

1. **Scoped role first.** Once JuiceFS authenticates as a single-schema role, the
   pending admin rotation **no longer touches the JuiceFS mount at all** — it shrinks
   the rotation's blast radius rather than widening it, and it is cheap and reversible
   where the rotation is expensive (~27 consumers, one maintenance window).
2. **Rotate `supabase_admin`** — operator action.
3. **Expose**, bound to the tailnet interface only.

---

## ⚠️ CORRECTION: the pooler option was wrong for this deployment

An earlier draft of this lane recommended exposing **supavisor (the pooler)** rather
than Postgres, on the architectural grounds that it is the purpose-built connection
front door. **Reviewing the official documentation and then the actual deployment
overturned that.** Recording the reasoning so it is not re-proposed.

### Two official sources conflict — and the platform one does not apply here

| Source | Statement |
|---|---|
| Supabase **platform** docs | port `5432` = session mode, `6543` = transaction mode; *"Transaction mode does not support prepared statements"*; session mode recommended for persistent backends |
| Supavisor **project** docs | *"Configure the `mode_type` on the `user` to set how Supavisor connection pools will behave"* — mode is **per-user configuration, not per-port** |

The port convention is **hosted-platform behaviour**. Self-hosted Supavisor resolves
mode from the **user row**, and this stack sets `POOLER_POOL_MODE=transaction`
(`PMOVES-supabase/docker/docker-compose.yml`, supavisor service). So "connect on 5432
to get session mode" — the assumption the pooler recommendation rested on — **does not
hold for a self-hosted deployment**.

JuiceFS's own docs never mention connection poolers, and point to the **`lib/pq`**
driver, which uses the extended query protocol (prepared statements). Transaction mode
would therefore break it.

### The deployment fact that settles it

**Supavisor has zero tenants and zero users provisioned — on BOTH z890 and B850:**

```
_supavisor.tenants : 0 rows
_supavisor.users   : 0 rows
```

The container is `Up (healthy)` and answering `GET /api/health` with 204s — but its
health check probes the API, not whether any tenant exists. **It has never been
configured to pool anything.** Exposing it would publish a port that cannot serve a
connection. (Same shape as Archon reporting container-`healthy` while `ready:false`
for three days — a green check that measures the wrong thing.)

Making the pooler viable would require: provisioning a tenant, creating a
`_supavisor.users` row with `mode_type` **session** (or `native`) — which contradicts
the stack's `transaction` default — and then verifying `lib/pq` compatibility. That is
**its own lane**, not a step in this one.

---

## Decision: expose `supabase-db`, multi-homed, tailnet-bound

Honest about what it is, matches the DSN the cross-node script already builds, and
uses the documented in-repo precedent.

- Multi-home `supabase-db` onto `pmoves_external` (`internal: false`) so its published
  port is actually plumbed — the NATS pattern at `docker-compose.yml:2906`.
- Bind to the **tailnet interface only**, *not* `0.0.0.0`. The NATS precedent defaults
  to `0.0.0.0` on the stated grounds that NATS is credential-guarded; that
  justification is weaker for a database, and weaker still while the admin credential
  is un-rotated. Reachability should be governed by the Tailscale ACL.
- The scoped role below is what keeps this from being a superuser surface. It is
  **more** important under Option B, not less.

Supavisor remains a legitimate future improvement — tracked separately.

---

## Step 1 — the scoped role (ready to apply; needs the migrations Known Road)

Target file: `pmoves/supabase/migrations/20260818000000_juicefs_meta_scoped_role.sql`

Blocked on an operator-set `KNOWN_ROAD=migrations:handoff:<this file>` — protected-path
writes are operator-authorized by design and an agent must not self-grant them.

Grants **DML on one schema only**; withholds `CREATE`, `BYPASSRLS`, `SUPERUSER`,
`CREATEROLE`, `CREATEDB`, `REPLICATION`, and every other schema. Created `NOLOGIN`
until the password is delivered via the CHIT pipeline (a login-capable role with no
password is a worse default). Idempotent. Applied with `make -C pmoves supa-migrate`
— no raw psql. Does **not** repoint the live mount; that is a separate reviewable step.

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'juicefs_meta') THEN
    CREATE ROLE juicefs_meta NOLOGIN;
    RAISE NOTICE 'created role juicefs_meta (NOLOGIN until a password is set)';
  ELSE
    RAISE NOTICE 'role juicefs_meta already exists — leaving as-is';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA juicefs_meta TO juicefs_meta;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA juicefs_meta TO juicefs_meta;

-- JuiceFS allocates inodes/chunks from sequences.
GRANT USAGE, SELECT, UPDATE
  ON ALL SEQUENCES IN SCHEMA juicefs_meta TO juicefs_meta;

-- So tables added by a future JuiceFS version inherit the same grants.
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA juicefs_meta
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO juicefs_meta;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA juicefs_meta
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO juicefs_meta;
```

Note `CREATE` is withheld because the volume is already formatted (18 tables live on
B850). If a FUTURE volume is formatted against this role, grant `CREATE` for that
operation and revoke it afterwards — do not leave it standing.

## Verification

```bash
# Step 1
make -C pmoves supa-migrate
# on B850: role exists, NOT superuser, and holds NO privileges outside juicefs_meta

# Step 3 (after 1 and 2), from a remote node:
nc -z pmoves-b850-ai-top 5432
make -C pmoves juicefs-cross-node-setup JUICEFS_HOST=pmoves-b850-ai-top DB_PASS=...
# read a REAL file — not just list filenames. A file-backed or unreachable volume
# lists correctly and fails on open, which is the failure this whole lane exists for.
```

## Related

- Lane board: `AGNOTE4482PHI.t1.md` (2026-08-18, L6)
- Cross-node runbook: `pmoves/docs/operations/JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md`
- Internal-network trap precedent: `pmoves/docker-compose.yml:2906` (NATS)
- `pmoves-media` is now MinIO-backed, so the old file-backend blocker is gone; port
  reachability is the only remaining one.
