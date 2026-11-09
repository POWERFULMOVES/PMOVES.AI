# Runbook draft — Deploying an A0 node (fleet-standard, CLI + browser wired)

- **Status**: DRAFT for PR (operator asked: "prs as how will we deploy on other nodes")
- **Authored**: 2026-11-01 by agent0-sidecar
- **Builds on**: `scripts/sidecar-host-prep.sh` (148-line, capability-detecting host prep), `deploy/sidecar/README.md`, `deploy/` tree (docker-stacks, k8s, provision, runbooks, runners)
- **Proven live on**: sidecar container 8b7cd2387a19 (this node) — host CLI answered 2026-11-01

## The fleet-standard node bring-up (7 steps)

1. **Host prep** — `bash scripts/sidecar-host-prep.sh <ContainerName>` on any Docker host: detects GPU/nvidia-runtime + Ollama, writes portable `sidecar.env` (standalone topology, dev-CHIT, host-gateway), emits the hardened `docker run` (cap-drop, no-new-privileges, host.docker.internal mapping).
2. **Container up** — run the emitted command; verify with `docker exec <name> env | grep PARENT_SYSTEM` (+ `nvidia-smi` when GPU).
3. **A0 CLI connector** — install the A0 CLI on the host OS, connect it to the instance (F4 pairing). This is what gives the agent `code_execution_remote` + `text_editor_remote` on the host filesystem. *Sidecar proof: hostname POWERFULMOVES answered 2026-11-01.*
4. **Browser consent** — on the host, enable Chrome remote-debugging consent (`chrome://inspect/#remote-debugging` → allow), then `/browser host on`. Gives the agent real host-browser control. Without this step the browser lane stays Docker-only.
5. **Tailnet** — join the node to the tailnet (authkey lane: `mini_cli tailscale_authkey`); record the device in the census (`research/tailscale_devices_*.json`).
6. **Env contract** — node-specific env via the operator-run `make -C pmoves env-local-set` (zero-access rule: agents never hand-edit `.env.local`).
7. **Verification gate** — from the sidecar: HTTP probe of the new instance's port, one `code_execution_remote` round-trip, one browser `tabs list`. All three green = node ONLINE (register row + sitrep update).

## Per-node specifics

| Node | State 2026-11-01 | Next action |
| --- | --- | --- |
| Sidecar (8b7cd…) | CLI ✅ live; browser consent unverified | browser `tabs list` probe; then done |
| ERP instance (AUTH_LOGIN) | probes 000 from container this session | verify via host-side probe; install CLI connector if absent |
| SPARK-A0 (100.92.144.16) | :8080 000 this session (was alive 10-26 via tailscale serve) | re-serve or re-register; then CLI connector + browser consent |
| elder-melchor / missinglinc | compose grounded, launch pending operator go | full 7-step runbook applies |

## PR plan

- **PR 1 (docs)**: this runbook → `deploy/runbooks/A0_NODE_BRINGUP.md` + README index row.
- **PR 2 (scripts)**: `scripts/a0-node-verify.sh` — the step-7 gate as an executable (probes + CLI round-trip + browser check, exit-coded).
- Both target the monorepo; merges stay operator-gated per PR_CLOSEOUT. (gh auth currently unavailable from the submodule — creation is operator-assisted or waits for token.)

## Open items
- Browser consent state on this host (probe pending).
- gh auth for actual PR opening.
- ERP instance's canonical address (census lists Elder-Melchor + B850-AI-TOP as Windows nodes; ERP instance identity to be confirmed by operator).