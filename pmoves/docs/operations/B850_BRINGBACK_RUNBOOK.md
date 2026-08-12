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

> **Tracked gap:** the per-node SSH-key story is still incomplete fleet-wide — see
> `pmoves/docs/handoffs/doc-coordination-juicefs-ingest-2026-08-06.md` (§ around
> lines 28–31: `claude-pmoves` SSH is authorized only on 4090 + jetsons, not the
> 5090). This does not block B850 (owner-role, Tailscale-SSH by tag), but keep it
> in mind when driving *other* nodes from z890.

---

## 6. Security follow-ups — HIGH severity (operator)

B850's currently-running `juicefs-mount` was started with the **Supabase admin
password inline in the container command line**, so it is visible in `ps` and
`docker inspect` to any local user — and has been for **days**. Ref:
`pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md` §
"Security item" (lines ~79–95).

### 6a. Re-create the mount with `META_PASSWORD` (no inline secret)

The password must be passed via the `META_PASSWORD` env var so the DSN in the
command line carries no credential. The canonical targets already do this:

```bash
# Local-DB mount on the data-tier host (B850), password via env, cache bounded:
export SUPABASE_DB_PASSWORD=...          # from the CHIT secrets pipeline
make -C pmoves juicefs-mount-local
```

`juicefs-mount-local` (see `pmoves/mk/egress.mk`) now also injects **per-host
bounded cache flags** (`scripts/juicefs-cache-bounds.sh`) so B850 does not inherit
the JuiceFS 100 GiB default nor self-disable caching on a full disk. Confirm the
new container has **no password** in its command line:

```bash
docker inspect juicefs-mount --format '{{json .Args}}'    # must NOT contain the password
docker inspect juicefs-mount --format '{{json .Config.Env}}' | grep -c META_PASSWORD   # expect 1
```

> **This narrows the exposure — it does not close it. Read before signing off.**
>
> `docker run -e META_PASSWORD` (value-less, inherited from the shell) makes Docker
> persist the **expanded** value into the container's `.Config.Env`. So this step
> moves the credential out of `.Args` — where it was visible in **both** `ps` and
> `docker inspect` — into `.Config.Env`, where it is still visible to
> `docker inspect`. The second verification command above is itself the proof: it
> greps `.Config.Env` and expects a hit.
>
> **Who can still read it:** any local user in the `docker` group (and thus root),
> via `docker inspect juicefs-mount`. That is a smaller set than "anyone who can run
> `ps`", which is the point of doing this — but it is not "no cleartext in inspect".
>
> **Real remediation:** file-mounted Docker secrets with a `*_FILE` indirection read
> inside the entrypoint, which keeps the value out of `.Args` *and* `.Config.Env`.
> The fleet already specifies this — see `#2492 § 8` (materialized per node as a
> file-mounted secret, never committed, never in `ps`), following the `#1901`
> precedent. Until that lands here, treat § 6a as *reduction*, not closure, and
> rotate on the assumption the value is readable by the docker group.

### 6b. Rotate the exposed Supabase admin password

Because the old password sat in process listings and container metadata for at
least three days, **rotate it** after the mount is re-created without it. Rotate
in Supabase, then flow the new value through the CHIT secrets pipeline
(`make -C pmoves secrets-funnel`) — do not hand-edit `env.shared`. Any other
consumer of `SUPABASE_DB_PASSWORD` / the JuiceFS meta DSN (the gateway, cross-node
mounts) picks up the new value on next `up`.

**T2 security pass criteria:** `juicefs-mount` re-created with `META_PASSWORD`
(no cleartext in `ps`, and none in `.Args` — but **still readable in
`.Config.Env`** via `docker inspect`, see the note in § 6a); Supabase admin
password rotated and funneled. The file-mounted-secret work in `#2492 § 8` is
what closes `inspect`; this pass does not.

---

## Related

- Cross-node mounts on 4090/5090 depend on B850 being up + reachable →
  `JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md`.
- Cache-bounds helper (wired into all mount call sites) →
  `pmoves/scripts/juicefs-cache-bounds.sh`.
- Storage-backend blocker + security note →
  `pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md`.
