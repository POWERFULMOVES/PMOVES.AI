# Supabase Fork-Sync + Architecture Handoff (2026-06-09)

Dedicated handoff for the **supabase** CRITICAL merge — deferred from the 2026-06-09
fork-sync run because it's the largest + most security-critical fork (≈2 GB, 2219 commits
behind, auth/DB). This is **not just a merge** — the operator flagged a TAC refresh, a known
Kong/CLI concern, and a multi-node dual-write + storage architecture goal that the upstream
enhancements + JuiceFS are meant to unlock. Read all of it before starting.

## 1. Mechanical fork-sync (the merge)

| Field | Value |
|---|---|
| Fork | `POWERFULMOVES/PMOVES-supabase` (≈2 GB repo) |
| Upstream | `supabase/supabase`, active branch **`master`** (not main) |
| Tracked / default | `PMOVES.AI-Edition-Hardened` (✅ flipped in §2; consistent, **not trapped**) |
| Gitlink | `a08627a4` (== hardened HEAD) |
| Drift | **2219 behind / 9 ahead** |

Use the proven template (`research/FORKSYNC_PARTITION_Z890_4090_2026-06-09.md`), but **do it
incrementally / co-claimed with 4090** — a single 2219-commit merge is too big to verify safely.
**Watch-items on conflict resolution (preserve PMOVES hardening):** GoTrue/PostgREST/Kong
configs, **JWT-secret hardening** (`JWT_SECRET`/`ANON_KEY`/`SERVICE_ROLE_KEY` naming per
`.claude/context/tier-architecture.md` §tier-supabase), RLS policies, the 9 ahead commits.
Image-built → the parent gitlink-promote PR's **post-merge Trivy is the CVE gate**.

## 2. TAC refresh — `TAC_SUPABASE.md`

Upstream has shipped **many enhancements PMOVES.AI can adopt**; the TAC tree is stale. After
the sync, refresh `TAC_SUPABASE.md` (+ `pmoves/docs/operations/SUPABASE_OPERATIONS.md`) to
capture what upstream now provides vs what PMOVES still custom-patches — so we stop hand-patching
things upstream has since fixed (same lesson as the GHCR/CVE sweep). Diff the 9 PMOVES-ahead
commits against current upstream features and retire any that upstreamed.

## 3. ⚠️ Known concern — Kong / CLI "mix-n-match"

Self-hosted Supabase has a recurring **Kong gateway ↔ Supabase CLI version-drift** problem
(the declarative `kong.yml` / route config gets out of sync with the CLI-generated stack, esp.
across upstream bumps). **This may NOT be fully resolved.** The 2219-commit sync WILL touch
Kong config — verify the gateway routes + the CLI-vs-compose story reconcile cleanly post-merge
(`pmoves/docs/operations/SUPABASE_OPERATIONS.md`, `FIRST_RUN.md`, `MAKE_TARGETS.md`). Treat a
clean Kong/CLI reconciliation as an acceptance gate, not an afterthought.

## 4. 🎯 The real goal — multi-node dual-write + offline-first sync

**Vision:** every fleet node runs **self-hosted Supabase in dual-write mode**; nodes
**seamlessly connect to each other and share updates**. Concretely: the operator (often on
the **4090 laptop**) does a batch of work **offline** that lands in the local Supabase; on
reconnecting to the fleet, **4090 propagates those updates** to the rest. This is an
offline-first, eventually-consistent, multi-master Postgres + Storage replication problem.

**What to evaluate during/after the sync:**
- Upstream Supabase **Storage S3 backend** updates — the operator believes the newer S3 storage
  path **helps solve the cross-node storage-sync problem**. Confirm the synced version exposes
  the S3-protocol storage backend and how it maps onto the multi-node goal.
- Postgres replication strategy for dual-write (logical replication / CRDT-ish merge / conflict
  policy) — out of scope for the merge itself, but the sync should not block enabling it.

## 5. 🗄️ JuiceFS — the MinIO successor for shared storage

Repo: **`POWERFULMOVES/PMOVES-juicefs`** (fork exists, **NOT yet wired as a submodule**).
Upstream: JuiceFS — a cloud-native **distributed POSIX filesystem** that stores **data in object
storage** (S3/MinIO) and **metadata in a separate engine** (Redis/Postgres/etc.), giving
**multiple nodes a shared, consistent, mountable filesystem** over the same object store.

**Why it matters here:** the operator believes **JuiceFS solves MinIO** for the fleet — i.e.,
replaces/augments the per-node MinIO with a **single shared filesystem every node mounts**, which
is exactly the substrate the multi-node Supabase Storage + offline-sync goal needs (shared,
POSIX, backed by object storage, metadata-coordinated). Pairs naturally with §4's S3-storage path.

**Actions:**
1. Wire `PMOVES-juicefs` in as a submodule (`.gitmodules`, tracked branch = its
   `PMOVES.AI-Edition-Hardened` once established) — currently the fork is orphaned from the tree.
2. Design where JuiceFS sits: metadata engine (Postgres in tier-data? Redis?) + object backend
   (existing MinIO as the blob store, or external S3). Map onto `env.tier-data`.
3. Decide the MinIO→JuiceFS transition (augment first, then migrate) — don't rip out MinIO until
   JuiceFS is proven; MinIO can remain JuiceFS's object backend.

## Sequencing recommendation
1. **Sync the fork** (incremental, co-claim 4090) → promote gitlink (Trivy gate).
2. **Refresh TAC_SUPABASE.md** against the synced version; reconcile Kong/CLI (acceptance gate).
3. **Spike the S3 storage backend** on the synced version (§4).
4. **Wire + spike JuiceFS** (§5) as the shared-storage substrate.
5. **Then** design the dual-write multi-node replication on top (separate lane).

Pairs with `[[project_fleet_fork_sync_state]]`, `research/FORKSYNC_PARTITION_Z890_4090_2026-06-09.md`,
`research/Z890_HANDOFF_FLEET_SYNC_2026-06-08.md`.
