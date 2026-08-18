# B850 "Knuckles" Bring-Back Runbook — Tailscale/SSH Re-Enroll + Security Follow-ups

> **Status:** operator-run. Authored by z890-claude 2026-08-09 to close the "not
> documented" gap — no prior checklist listed the exact pending enroll commands.
> **Node:** B850 "Knuckles" — primary dev host + heavyweight ROCm inference, and
> the **single data-tier home** (Postgres / NATS / the JuiceFS metadata store).
> Do **not** split-brain the data tier onto another node.

B850 is back online after being offline. This runbook re-enrolls it into the
Tailscale mesh, verifies fleet visibility, and closes two **HIGH-severity**
security items on its live `juicefs-mount`.

---

## 0. Resolve the hostname FIRST (read-only)

B850 appears under three different names across the docs — they are **not**
interchangeable for enrollment:

| Name | Source | Authority |
|------|--------|-----------|
| `pmoves-b850-ai-top` | `.claude/context/runner-topology.md` | **authoritative** |
| `pmoves-9850x3d-r9700` | some runbooks | drift |
| `pmoves-rdna4` | AI-Top service script | drift |

The enroll `DEVICE=` and the `tailscale up --hostname` **must match the name the
node is actually registered under**. Confirm the live name before doing anything:

```bash
# On any node already on the tailnet (read-only — changes nothing).
# fleet-status, not raw `tailscale status`: it prints the hostname column and
# redacts IPs, which is the standing convention (BOOTSTRAP.md § Fleet view —
# "never raw tailscale status for public IPs"). Hostnames are all this step needs.
make -C pmoves fleet-status | grep -iE 'b850|knuckles|9850|rdna4'
```

Set `CONFIRMED` to whatever that prints (expected: `pmoves-b850-ai-top`) and use
it verbatim everywhere below. If the node does not appear at all, it has no live
registration yet — proceed to step 1 (enroll) which creates it.

> Hostname canonicalization across the three docs is flagged as a **separate
> docs-fix** (deferred this pass) — do not "fix" it by renaming the live node.

---

## 1. Generate the enrollment token (on z890 or any owner node)

```bash
# Sources CHIT-managed fleet secrets into the tier env files (never edit env.shared).
make -C pmoves secrets-funnel

# Needs CHIT_PASSPHRASE in the environment (voice-activated / CHIT vault — do NOT
# paste it on a shared CLI). Target: pmoves/mk/infra.mk : fleet-enroll.
export CHIT_PASSPHRASE=...              # from the CHIT vault
make -C pmoves fleet-enroll ROLE=owner DEVICE="$CONFIRMED"
```

`ROLE=owner` because B850 is your own management/inference workstation, not a
third party. (Enrollment tokens for `partner`/`guest` are for others — see the
`enrollment-is-for-others` note.)

---

## 2. Join the tailnet FROM B850 with the correct tags

Run **on B850**. The tags come from `pmoves/configs/tailscale-acl-policy.json`
(the `tag:lab` fleet-management block, lines ~120–154) — **not** the z890
launcher script's tag set:

```bash
sudo tailscale up \
  --hostname "$CONFIRMED" \
  --accept-routes \
  --accept-dns \
  --advertise-tags=tag:pmoves,tag:gpu,tag:lab
```

Why these three tags:
- `tag:pmoves` — full-mesh membership (port-22 reachability, exit-node egress).
- `tag:gpu` — B850 serves Ollama/llama-server to the fleet (a destination in the
  `:11434` / gpu-orchestrator rules).
- `tag:lab` — fleet-management identity; grants root-SSH to the KVM concentrators
  via the scoped `tag:lab → tag:vps,tag:exit` rule.

> **Do NOT untag B850 to "fix" reachability.** Measured 2026-08-04, untagging a
> tagged compute node silently drops it out of `tag:gpu` (breaking fleet Ollama
> at `:11434`) and out of the exit-node egress src list. Untagging pmoves-4090
> took it offline from the mesh. The ACL, not a tag removal, is the reachability
> mechanism here.

---

## 3. Approve the tags (admin console, if prompted)

If Tailscale prompts for tag approval (device-auth or tag-owner approval), approve
`tag:pmoves`, `tag:gpu`, `tag:lab` for the node in the admin console.

---

## 4. Verify mesh + fleet visibility

```bash
# From any node on the tailnet. fleet-status is the Known Road: it prints
# hostname / OS / connection and redacts IPs (see BOOTSTRAP.md § Fleet view).
make -C pmoves fleet-status | grep -i "$CONFIRMED"   # expect: present, online

make -C pmoves fleet-status                          # expect: relay health green
```

**Tags are not in either of those.** `tailscale status` does not print per-node
tags at all — its third column shows the *owner*, which for a tagged node reads
`tagged-devices`, and `fleet-status` does not surface that column either. Tags
live only in the JSON, so read them there and print nothing but hostname + tags
(no addresses, so the no-IPs convention still holds):

```bash
tailscale status --json \
  | jq -r --arg h "$CONFIRMED" '.Peer[] | select(.HostName==$h) | "\(.HostName): \(.Tags // ["<untagged>"] | join(", "))"'
# expect: pmoves-b850-ai-top: tag:gpu, tag:lab, tag:pmoves
```

**T2 pass criteria:** `make -C pmoves fleet-status` shows `$CONFIRMED` online and
relay health green; the JSON query above lists `tag:pmoves`, `tag:gpu`, `tag:lab`.

---

## 5. SSH — nothing to install on B850

The fleet does **not** install SSH keys on B850. Access is **Tailscale SSH**,
authorized by tag in the ACL (`tag:lab` sources reach `tag:vps`/`tag:exit` as
root; owner identities reach nodes per the owner rule). There is no per-node key
step here.

> ### ⚠️ Pass the per-node username — the ACL is probably not your problem
>
> From a tagged workstation, `ssh <host>` defaults to your **local** username. On
> Windows that is something like `DARKXSIDE`, which does not exist on a Linux
> node, and Tailscale rejects it with:
>
> ```
> tailnet policy does not permit you to SSH as user "DARKXSIDE"
> ```
>
> That message names the **user**, not the node — it is easy to misread as "this
> node is ACL-blocked" and go off writing ACL rules. Measured 2026-08-15: the rule
> `tag:pmoves → tag:pmoves (autogroup:nonroot)` already permits it, z890 carries
> `tag:pmoves`, and **no ACL change was needed**. Supply the account that exists
> on the target:
>
> ```bash
> ssh pmoves@pmoves-b850-ai-top     # B850
> ssh pmovesnvme@pmoves-nano-1      # jetsons
> ```
>
> Related standing rule: `autogroup:nonroot` grants a *non-root* user, and **that
> user must already exist on the node** — the ACL cannot conjure it.
>
> **Privileges you get there (B850):** the `pmoves` account is in the `docker`
> group but has **no passwordless sudo**, and the JuiceFS mount's bind paths live
> under `/home/pmoves-knuckles/` (a *different* user's home). So you can drive
> Docker fine, but you cannot write those paths — stage helper files under
> `/home/pmoves/` and bind-mount them. Always `docker stop -t 30` before removing a
> FUSE-mount container so JuiceFS unmounts cleanly; a stale mount needs root.

> **Tracked gap:** the per-node SSH-key story is still incomplete fleet-wide — see
> `pmoves/docs/handoffs/doc-coordination-juicefs-ingest-2026-08-06.md` (§ around
> lines 28–31: `claude-pmoves` SSH is authorized only on 4090 + jetsons, not the
> 5090). This does not block B850 (owner-role, Tailscale-SSH by tag), but keep it
> in mind when driving *other* nodes from z890.

---

## 6. Credential handling for the mount — ✅ DONE 2026-08-15

The JuiceFS mount's metadata credential is supplied by a **file-mounted secret**
read at container start — the `*_FILE` indirection the fleet standardises on
(`#2492 § 8`, following the `#1901` precedent). This is the pattern to copy for
any node that mounts JuiceFS.

**Why the file, and not an env var:** `docker run -e VAR` (value-less, inherited
from the shell) makes Docker persist the *expanded* value into the container's
stored config, where `docker inspect` still shows it. Reading the value from a
mounted file inside the command keeps it out of the container's argv **and** its
stored config.

### The shape

```bash
# Secret lives in a 0600 file owned by the invoking user; never committed.
#   /home/<user>/.pmoves-secrets/jfs_meta_pw          (mode 600)
# Mount it read-only and read it at exec time:
docker run -d --name juicefs-mount --restart unless-stopped \
  --network pmoves_data --privileged --entrypoint sh \
  -e JFS_MOUNT="$MNT" \
  -v <juicefs-data>:/data \
  -v "$MNT:$MNT:rshared" \
  -v <repo-scripts>:/scripts:ro \
  -v "$SECRET_FILE:/run/secrets/jfs_meta_pw:ro" \
  juicedata/mount:ce-v1.3.0 \
  -c 'JFS_CACHE_FLAGS="$(JFS_CACHE_DIR=/data/jfsCache JFS_CACHE_MEASURE_DIR=/data \
        bash /scripts/juicefs-cache-bounds.sh 2>/dev/null || true)"; \
      test -n "$JFS_CACHE_FLAGS" || JFS_CACHE_FLAGS="--cache-dir /data/jfsCache --cache-size 512 --free-space-ratio 0.05"; \
      export META_PASSWORD="$(cat /run/secrets/jfs_meta_pw)"; \
      exec juicefs mount --enable-xattr $JFS_CACHE_FLAGS \
        "postgres://supabase_admin@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable" "$JFS_MOUNT"'
```

Note the DSN carries **no credential** — `juicefs` takes it from `META_PASSWORD`.

### Verification (all four must be 0)

```bash
SEC=$(cat "$SECRET_FILE")
docker inspect juicefs-mount --format '{{json .Args}}' | grep -cE 'postgres://[^:@"]+:[^@"]+@'  # inline DSN cred
docker inspect juicefs-mount | grep -cF "$SEC"                                                  # stored config
pgrep -a juicefs | grep -cF "$SEC"                                                              # process argv
docker logs juicefs-mount 2>&1 | grep -cF "$SEC"                                                # logs
unset SEC
```

> Count with `grep -cF "$SEC"`, and exclude your own `grep` when scanning `ps` —
> `ps aux | grep -F "$SEC"` matches the grep process's own argv and reports a
> false positive. Use `pgrep -a juicefs` (greps pgrep's *output*) instead.

**Verified on B850 2026-08-15:** all four counts 0; mount ACTIVE; cache bounds
applied from the helper (`--cache-size 41880 --free-space-ratio 0.045` on a
91%-full disk); 0 error lines.

### 6b. Credential rotation — standing hygiene item (operator)

Rotate the metadata credential on the normal schedule, and whenever a mount has
been re-created. Rotate at the source, then flow the new value through the CHIT
secrets pipeline (`make -C pmoves secrets-funnel`) — never hand-edit `env.shared`.
Consumers of `SUPABASE_DB_PASSWORD` / the JuiceFS meta DSN pick it up on next `up`.

> **Blast radius before you start:** ~27 containers on B850 carry
> `SUPABASE_DB_PASSWORD`/`POSTGRES_PASSWORD`. Changing the database password
> *without* funneling + restarting those consumers takes the data tier down.
> Do both in one window, then re-create the mount's secret file.

---

## Related

- Cross-node mounts on 4090/5090 depend on B850 being up + reachable →
  `JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md`.
- Cache-bounds helper (wired into all mount call sites) →
  `pmoves/scripts/juicefs-cache-bounds.sh`.
- Storage-backend blocker + security note →
  `pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md`.
