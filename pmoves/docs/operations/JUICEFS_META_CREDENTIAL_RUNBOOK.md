# JuiceFS metadata credential — provisioning, delivery, rotation

**Owner: Z890 (Infrastructure Coordinator).** Not "whoever is nearest a terminal".
The credential is fleet infrastructure: it gates every node's ability to mount
`pmoves-media`, and B850 — which holds the metadata DB — should not become the
ambient owner of a secret it merely consumes.

Sourced from JuiceFS community documentation, cited inline. Where this deployment
diverges from vendor guidance, the divergence is named and given a disposition
rather than left as an inherited default.

---

## 0. Why this exists

The scoped `juicefs_meta` role was created and B850's mount was cut over to it,
but the credential never entered the secrets pipeline. It lived at
`/home/pmoves/.pmoves-secrets/juicefs_meta_pw` — a hand-placed file, under a
different user's home, referenced nowhere in the repo. B850 worked; no second
node could mount without someone hand-copying a secret.

`JUICEFS_META_PASSWORD` is now a registered CHIT slot (PR #2705, tier `data`).
This runbook is the operator half: the route exists, and carries nothing until
the steps below are performed.

---

## 1. Vendor alignment — what matches, and what does not

JuiceFS's [PostgreSQL best practices][pg-bp] make four recommendations bearing
directly on this deployment.

### 1.1 Dedicated user + network-scoped `pg_hba` — ALIGNED

The vendor's example grants one dedicated JuiceFS user access from one trusted
CIDR, and nothing else. (Their sample uses a private LAN range and `md5`; the
shape is what matters, not the literal values.)

PR #2702 landed exactly that shape, scoped to the tailnet:

```
host  all  juicefs_meta  100.64.0.0/10        scram-sha-256
host  all  all           100.64.0.0/10        reject
```

Only `juicefs_meta` may authenticate from the tailnet; every other role is
rejected there. `scram-sha-256` rather than the doc's `md5`, which is deprecated
upstream in PostgreSQL and which this cluster does not use.

**For anyone re-deriving this:** the scoped role alone does NOT deliver the
safety property. A scoped role changes which credential JuiceFS *uses*; it does
nothing to stop a superuser credential from being *accepted*. The `pg_hba` rule
is the control. The vendor doc pairs them for exactly this reason, and the pairing
was the piece missing from the original lane handoff.

### 1.2 `META_PASSWORD` / `META_PASSWORD_FILE` — PARTIALLY ALIGNED

> "A more secure approach would be to pass the database password through the
> environment variable `META_PASSWORD`" … "The password can also be passed using
> a file as follows: `export META_PASSWORD_FILE=…`"
> — [Metadata engine setup][meta-engine]

We use `META_PASSWORD`, satisfying the primary recommendation: the password never
appears in the metadata URL, so it cannot leak through `ps` or logs.

But B850's mount currently does the equivalent of `META_PASSWORD="$(cat <secret
file>)"`, when the secret is *already* bind-mounted as a Docker secret.
`META_PASSWORD_FILE` consumes that file directly and removes the shell
round-trip — one fewer place the plaintext exists, and the form the vendor
documents.

**Disposition:** adopt on the next mount recreate. Not urgent; the current form
is not leaking. It is simply closer to the documented pattern.

### 1.3 `sslmode=disable` — DIVERGENT, decide before Step 4

> "By default, JuiceFS clients will use SSL encryption to connect to PostgreSQL."
> If SSL is unavailable, append `sslmode=disable`, "though maintaining SSL
> protection is strongly advised." — [PostgreSQL best practices][pg-bp]

Our DSN carries `sslmode=disable`. Unremarkable while the connection was
container-to-container on an internal Docker network. **It stops being
unremarkable the moment `:5432` is published to the tailnet.**

The honest position: WireGuard encrypts the tailnet transport, so this is not
plaintext on the wire. But the Postgres session has no TLS of its own, and the
deployment is one `tailscale down` away from that assumption failing.

**Disposition:** decide explicitly at Step 4 of the cross-node lane — either
enable TLS on `supabase-db` and drop `sslmode=disable`, or record the
WireGuard-as-transport-security argument in the lane handoff so it is a decision
rather than an inherited default.

### 1.4 Backup restore has never been tested — GAP

> "It is recommended to make a plan for regularly backing up your database, and
> at the same time, **do some tests to restore the data in an experimental
> environment to confirm that the backup is valid**." — [PostgreSQL best
> practices][pg-bp]

B850 runs `--backup-meta` hourly to MinIO (`juicefs/pmoves-media/meta/dump-*.json.gz`,
verified succeeding). We have never restored one. An untested backup is a
hypothesis.

**Disposition:** a Z890 task — restore a dump into a throwaway Postgres and
confirm `juicefs status` reads the restored volume. Tracked separately from this
runbook's procedure.

### 1.5 Metadata must stay single-server — CONSTRAINT

> "PostgreSQL does not yet support Multi-Shard (Distributed) transactions, do not
> use a multi-server distributed architecture for the JuiceFS metadata."
> — [PostgreSQL best practices][pg-bp]

This forecloses "replicate the metadata DB across nodes" as an availability
strategy. B850 is a single point of failure for the metadata engine *by vendor
design*. Availability work belongs in backup/restore (1.4), not replication.

---

## 2. Procedure — provision the credential into the pipeline

Run on **Z890**. Requires `gh` authenticated against the Prod environment.

### 2.1 Read the existing value from B850

The value already exists; this is a migration into the pipeline, not a new mint.
It is root-readable only, under a separate account:

```sh
# On B850, as an operator with sudo:
sudo cat /home/pmoves/.pmoves-secrets/juicefs_meta_pw
```

Never paste it into chat, a ticket, or a synced shell history. If the value's
provenance is at all unclear, prefer 2.2-alt and rotate instead.

### 2.2 Create the GitHub Prod secret

```sh
gh secret set JUICEFS_META_PASSWORD --env Prod --repo POWERFULMOVES/PMOVES.AI
# paste at the prompt — never as an argv value, which lands in shell history
```

The name must match the CHIT label exactly. `sync-secrets-local.yml` carries a row
for it in the Data Stores block; without that row the bundle omits it and the
funnel silently skips the entry.

### 2.2-alt Rotate instead of migrating (preferred when provenance is unclear)

`juicefs_meta` is NOT a superuser, and `bootstrap_db.sh` does not manage it, so
this affects only the mounts — not the Supabase stack.

The password must not reach argv or shell history. The obvious
`psql -c "ALTER ROLE … PASSWORD '<new>'"` form violates both, and so does
`psql -v` — the value lands in the container's argv either way.

Pipe the statement on **stdin**:

```sh
# On B850. `read -rs` does not echo and does not enter history; printf is a
# shell builtin, so the value never becomes a separate process's argv.
read -rs NEWPW
printf "ALTER ROLE juicefs_meta PASSWORD '%s';\n" "$NEWPW" \
  | docker exec -i pmoves-supabase-db-1 \
      psql -h 127.0.0.1 -U supabase_admin -d postgres -v ON_ERROR_STOP=1
unset NEWPW
```

Mint the value with the pipeline's own generator (URL-safe, no quote escaping to
get wrong) rather than choosing one by hand.

**This belongs behind a Make target** that reads from stdin, alongside
`secrets-rotate`. Until that exists, use the form above — and afterwards confirm
no `ALTER ROLE` line reached your history file.

Then update the secret file B850's mount reads, recreate `juicefs-mount`, and set
the Prod secret to the same value.

### 2.3 Deliver to the consuming node

**Order matters for runnerless nodes, and getting it wrong is silent.**
`secrets-funnel-from-prod` calls `scripts/pull_chit_bundle.sh`, which selects the
newest **already-successful** run:

```sh
gh run list --workflow "$WORKFLOW" --status success --limit 1 ...
```

That run can predate the secret you just created. The pull succeeds, the funnel
reports success, and `JUICEFS_META_PASSWORD` is absent or stale. So a fresh
producer run has to exist *before* the pull:

```sh
# 1. On a runner-backed node — produce a bundle that CONTAINS the new secret:
make -C pmoves secrets-sync-trigger TARGETS=<runner-backed-node>

# 2. Wait for that run to finish successfully. Do not skip this.
gh run list --repo POWERFULMOVES/PMOVES.AI \
  --workflow sync-secrets-local.yml --limit 1 \
  --json databaseId,status,conclusion,createdAt

# 3. Only then, on the runnerless node (5090):
make -C pmoves secrets-funnel-from-prod
```

Confirm in step 2 that `createdAt` is **after** you set the Prod secret. That
timestamp comparison is the whole check.

### 2.4 Verify delivery WITHOUT printing the secret

```sh
grep -c '^JUICEFS_META_PASSWORD=..' pmoves/env.tier-data     # expect 1
```

`..` rather than a bare presence check: present-but-empty is the failure mode
this catches, and `grep -c '^JUICEFS_META_PASSWORD='` passes on it.

---

## 3. Verify end to end

After Step 4 of the cross-node lane has published `:5432`:

```sh
make -C pmoves juicefs-cross-node-setup JUICEFS_HOST=pmoves-b850-ai-top META_ROLE=juicefs_meta
```

Expect success as `juicefs_meta` and a **reject** as any other role — that
asymmetry is the `pg_hba` control (PR #2702) working, and is worth confirming
rather than assuming.

Then the read-path proof from the mount runbook: list *and* read. A file-backed
or unreachable volume lists correctly and fails on open, which is the failure the
whole cross-node lane exists to close.

---

## 4. Rotation

This credential is independent of the Supabase rotation by design. `supa-bootstrap-db`
aligns `pmoves`, `supabase_admin` and `authenticator` from `SUPABASE_DB_PASSWORD`;
it does not touch `juicefs_meta`. A Supabase rotation therefore does NOT rotate
this, and rotating this does not disturb the Supabase stack. That independence is
the point of the scoped role.

To rotate: 2.2-alt, then 2.3 on every mounting node, then recreate each mount.

---

## Related

- `JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md` — the mount procedure itself
- `pmoves/docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md` — the lane
- PR #2702 — the `pg_hba` role scoping described in 1.1
- PR #2705 — the CHIT slot this runbook provisions

[meta-engine]: https://juicefs.com/docs/community/databases_for_metadata/
[pg-bp]: https://juicefs.com/docs/community/postgresql_best_practices/
