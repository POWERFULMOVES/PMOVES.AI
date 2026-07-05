# TAC Tree Refresh — Reconciliation Snapshot (2026-06-23)

Post-merge TAC audit across all 34 trees in `pmoves/configs/tac_trees/`, run via
`python pmoves/tools/tac_runner.py <tree>`. Authored by 4090-CLAUDE (deploy/CI
spine) as a fleet reconciliation; **each tree is owned by its `agent_hint`** —
owners drive their own fixes (Village Rule). This snapshot routes the work; it
does not edit other lanes' trees.

**Refresh principle (per Known Roads):** TAC fails are mostly *accurate* — real
gaps or unverified runtime checks, not stale trees. Don't "make green" by editing
checks; reconcile reality (`grep` before coding a gap; status propagates up).

## Health snapshot (pass / fail / pending)

| Tree | Owner | pass | fail | pending | Note |
|------|-------|-----:|-----:|--------:|------|
| firefly-iii | codex | 7 | 0 | 0 | ✅ clean |
| pmoves-launch-readiness | z890-claude | 27 | 0 | 22 | clean (pending = manual) |
| cast-gateway | **4090-claude** | 35 | 2 | 0 | compose hardening gaps (below) |
| github-app | z890-claude | 13 | 3 | 5 | runtime BoTZ/Archon + runner-auth (see §GHCR note) |
| security-posture | codex | 15 | 4 | 0 | candidate for new daemon-hardening nodes |
| networking-defense-in-depth | codex | 9 | 3 | 24 | candidate for daemon log-rotation node |
| tensorzero-gpu | codex | 24 | 4 | 1 | |
| voice-agents | codex | 23 | 5 | 37 | |
| health-wger | codex | 5 | 2 | 0 | |
| hirag-retrieval | codex | 9 | 2 | 0 | |
| archon-agents | codex | 5 | 4 | 0 | |
| botz-mcp | codex | 6 | 5 | 0 | |
| comfyui-pipeline | codex | 4 | 4 | 0 | |
| soundcloud-ingest | codex | 8 | 6 | 4 | |
| n8n | codex | 7 | 7 | 0 | |
| tokenism-chit | codex | 3 | 5 | 0 | |
| dox-intelligence | codex | 0 | 7 | 0 | none passing — reconcile |
| observability | codex | 4 | 10 | 0 | high fail — reconcile |
| mcp-topology | codex | 13 | 12 | 15 | high fail — reconcile |
| agent-zero-customization | codex | 15 | 35 | 0 | **highest fail — likely many stale patterns** |
| node-5090-powerfulmoves | 5090-claude | 0 | 2 | 18 | |
| huggingface-integration | codex | 8 | 0 | 14 | |
| nvidia-nims | codex | 5 | 0 | 16 | |
| node-z890-coordinator | z890-claude | 1 | 0 | 19 | |
| dgx-spark | spark_claw | 0 | 1 | 14 | |

### Never-run (all-pending — never audited)
`agent-teams-taxonomy` (67), `skills-taxonomy` (36), `node-hermes-agent` (33,
hermes-agent), `node-4090-laptop` (30, **4090-claude**), `training-pipeline` (21,
5090-claude), `p7-agents-skills-lifecycle` (24), `pinokio-p7` (23, 5090-claude),
`jetson-orin` (19, z890-claude), `cataclysm-studios` (10, floos-resolver).

## 4090-claude lane (mine) — reconciled

- **cast-gateway** (35/2): both fails are **real compose-hardening gaps**, not
  stale checks — `cg.health.hardening` wants the `tier-agent-hardened-ro` anchor
  on `cast-tts-gateway` in `docker-compose.yml`, and `cg.security.container`
  wants the nonroot `65532` user. These belong in the **deferred compose-
  hardening PR** (Docker audit P2: "apply `x-tier-*-hardened` anchors fleet-wide")
  — `docker-compose.yml` is a basename-protected Known Road file, so this is a
  deliberate hardening change, not a tree edit. **Action: fold cast-tts-gateway
  into the compose-hardening PR.**
- **node-4090-laptop** (0/0/30): tree is **not stale** — all 30 are runtime/
  manual checks (Tailscale reach, Ollama `:11434`, gh auth, shift-crew skills)
  that need **live verification on the node**, which is the `node-4090-sitrep` /
  `node-4090-verify` skill flow, not a tree edit. **Action: run the live sitrep
  to record verified status; tree definitions are current.**

## Session-relevant additions to propose to owners (not edited here)

This session landed fleet hardening that warrants **new TAC nodes** (owner = codex):
- **security-posture / networking-defense-in-depth:** add nodes for
  container **log rotation** + **live-restore** (`deploy/provision/daemon.json`,
  `DOCKER_DAEMON_HARDENING.md` — PR #1869) and the **no-volume-prune** runner
  safety (`runner-maintenance.yml` / `integrations-ghcr.yml` — PR #1868).

## §GHCR note for github-app owner (z890-claude)
The §4 resolution (2026-06-23) is that **GHCR push for the user namespace uses a
classic PAT by design** — GitHub App installation tokens cannot create/write
packages under the `powerfulmoves` *user* namespace. So `gh-app.runners.app-auth`
("runners use App auth") is **not a gap to close for GHCR push** — it's
superseded for that path. The new org App on CATACLYSM-STUDIOS-INC is parked for
the future public fork-manager. Recommend re-scoping that node to reflect
PAT-for-GHCR + App-for-repo-ops. See `[[project_github_app_auth]]`.

## Recommended order for owners
1. **codex:** reconcile the high-fail trees with `grep`-first (agent-zero-customization 35, mcp-topology 12, observability 10, dox-intelligence 7) — likely many stale patterns from renamed/moved code.
2. **codex:** add the daemon-hardening + no-volume-prune nodes (session features above).
3. **z890-claude:** re-scope `gh-app.runners.app-auth` per the §GHCR note.
4. **4090-claude:** cast-tts-gateway → compose-hardening PR; node-4090 live sitrep.
5. Run the never-run trees at least once to establish a baseline.
