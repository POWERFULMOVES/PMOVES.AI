# Secrets Distribution Patterns

**Scope:** How GitHub Secrets reach the runtime nodes that need them. Three patterns indexed by fleet topology + node lifecycle stage.

**Last updated:** 2026-05-18

---

## Pattern A — Matrix workflow (currently in use)

**Workflow:** `.github/workflows/sync-secrets-local.yml`
**Use when:** Node has a registered, online ai-lab-labeled GitHub Actions runner.

```yaml
strategy:
  fail-fast: false
  matrix:
    target: [spark, z890, ...]   # ai-lab sub-labels
runs-on: [self-hosted, ai-lab, "${{ matrix.target }}"]
```

Each `workflow_dispatch` runs the job once per matrix entry, on the runner carrying both `ai-lab` and the per-node sub-label (`spark`, `z890`, future `5090`, `b850`). Each runner ends up with its own up-to-date CHIT bundle at the runner's `$XDG_CONFIG_HOME/pmoves/chit/env.cgp.json` plus `local.env`.

**Trigger:**
```powershell
gh workflow run sync-secrets-local.yml --repo POWERFULMOVES/PMOVES.AI \
  -f targets="spark,z890"
```

**Pros:**
- One trigger updates the whole fleet
- Each node owns its own bundle; no cross-node copy
- `fail-fast: false` tolerates one node being offline without breaking the others
- Already integrated with `_config_paths.sh` (canonical XDG config dir per OS)

**Cons:**
- Requires each capable node to host a self-hosted runner with the correct labels
- Runner runtime needs `uv`/`python3` + `openssl` + bash — small but non-zero footprint
- For Windows-native nodes, runner means WSL2 = the cross-running pattern `feedback_no_cross_running_services` warns against unless tightly scoped to CI work

**Required per-node labels:**
| Node | Labels to add to runner | Currently set? |
|---|---|---|
| SPARK | `self-hosted, ai-lab, spark` | ✅ all present (`pmoves-spark-ailab`) |
| Z890 | `self-hosted, ai-lab, z890` | ❌ runner offline + missing `z890` sub-label (see MLF-006) |
| 5090 | `self-hosted, ai-lab, 5090` | ❌ runner not registered |
| B850 | `self-hosted, ai-lab, b850` | ❌ runner not registered |

---

## Pattern B — Artifact upload + per-node pull (recommended for new nodes)

**Status:** SHIPPED (consumer side, 2026-07-24). The producer upload-artifact step has been live in `sync-secrets-local.yml` since Pattern A; the consumer is now `make -C pmoves secrets-pull` (installs the newest successful run's bundle at the canonical user-scoped CHIT path) and the one-shot `make -C pmoves secrets-funnel-from-prod` (pull + materialize tier files). No per-run path or run-id juggling — schedule the one-shot per node (Task Scheduler / cron) or run on demand. Use for any node whose runtime cannot host a GH Actions runner (5090, Z890) OR when secrets should be pushed to a specific path rather than landing in a runner-writable directory.

**Design:**

1. **Producer workflow** runs on any ai-lab runner (e.g. SPARK), writes CHIT bundle, **uploads as encrypted artifact**:
   ```yaml
   - name: Upload bundle
     uses: actions/upload-artifact@v4
     with:
       name: chit-bundle-${{ github.run_id }}
       path: pmoves/data/chit/env.cgp.json
       retention-days: 1
   ```

2. **Consumer step on target node** (cron, systemd timer, scheduled task, or operator one-shot):
   ```bash
   gh run download <run-id> --repo POWERFULMOVES/PMOVES.AI \
     --name chit-bundle-<run-id> \
     --dir "$XDG_CONFIG_HOME/pmoves/chit"

   make -C pmoves secrets-funnel   # decode + populate tier files
   ```

3. **Target node only needs:** `gh` CLI + authenticated session (PAT or device-flow). No GH Actions runner.

**Why this is the right answer for new hardware:**
- Secrets are **pushed to the exact path the runtime reads**, not a folder that might be blocked by Windows ACLs, immutable filesystem layers, container readonly mounts, or zeroAccessPath damage-control hooks.
- New node enrollment becomes: install `gh`, authenticate, schedule the pull. No runner registration, no CI infra on the node.
- Per-node pull schedule decouples freshness from workflow trigger time (each node can pull on its own cadence).

**Trade-off:**
- Adds a second workflow (producer) and a small pull script per node.
- Artifact retention costs apply (1-day retention recommended; bundles are CHIT-encrypted so storage is acceptable).

**Authorization signal (2026-05-18, DARKXSIDE):**
> "review B as method for new nodes when new hardware added — secrets are sent where they need to go not folder that might be blocked on system"

---

## Pattern C — Tailscale Drive shared filesystem (parked, depends on Longbow)

**Status:** Parked until Longbow integration is properly in place.

**Concept:** Mount a Tailscale Drive (or equivalent tailnet-only shared filesystem) across SPARK + ai-lab nodes. Producer writes bundle once. Every node reads from the same mount.

**Why parked:**
- Requires Longbow integration to be production-ready for the shared-volume access pattern
- Surface area review needed: secret bundle visible to any node holding the mount — fine within tailnet, but ACL discipline matters
- Tailscale Drive currently in beta; reliability profile for "primary secret distribution" not yet established

**Will revisit when:** Longbow is integrated + Tailscale Drive moves out of beta + ACL surface is reviewed.

---

## Decision matrix per node type

| Node type | Pattern | Rationale |
|---|---|---|
| Long-lived Linux service host (SPARK, 4090 Linux) | **A** | Runner footprint is acceptable; bundle freshness tied to CI cadence; matrix scales |
| Long-lived Windows-native host (Z890 post-migration) | **B** | Avoid WSL2-only-for-CI antipattern; pull on schedule into XDG path |
| Ephemeral / dev node | **B** | Short lifetime; runner registration overhead too high |
| VPS / KVM (kvm2, kvm4-*) | **A** *(separate `vps` label)* | Already has dedicated runners; per-VPS labels already isolate them |
| Future shared compute cluster | **C** (once Longbow ready) | Many nodes, low admin overhead, single source of truth |

---

## Operator runbook — add a new node

1. **Decide pattern** using the matrix above.
2. **If Pattern A:** register a self-hosted GH Actions runner with labels `self-hosted, ai-lab, <node-name>`. Edit `sync-secrets-local.yml` matrix default to include `<node-name>` (or pass via `targets` input).
3. **If Pattern B:** install `gh` + authenticate; schedule (cron / systemd timer / Task Scheduler) to run the pull script daily or on demand; verify `$XDG_CONFIG_HOME/pmoves/chit/env.cgp.json` lands; `make -C pmoves secrets-funnel`.
4. **If Pattern C:** N/A until Longbow.
5. **Verify** with `make -C pmoves secrets-audit` and a service smoke check that reads a synced secret.

---

## See also

- `pmoves/docs/MINIMAX_API_KEY_SETUP.md` — per-key activation example (uses Pattern A today)
- `pmoves/docs/operations/MISSING_LINC_FINDINGS.md` — MLF-006 tracks the per-node sub-label gap on the offline Z890 runner
- `pmoves/scripts/_config_paths.sh` — canonical `$XDG_CONFIG_HOME` resolution shared across runners + service hosts
- `feedback_no_cross_running_services` memory — why WSL2 should be CI-scoped only, not service-runtime
