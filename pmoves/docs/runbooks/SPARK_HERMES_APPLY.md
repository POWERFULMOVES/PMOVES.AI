# SPARK HERMES Apply Runbook — cloud-hybrid worker tier

GRAPHITI_MARK: `PHI-4482-HERMES::SPARK-APPLY::PMOVES`

**Status:** PENDING APPLY — `pmoves-spark` offline on tailnet at authoring
(2026-07-03; last seen <1h, flappy). Apply when it reappears:
`tailscale status | grep -w pmoves-spark`.

**Context:** spec rev 4 (`docs/superpowers/specs/2026-07-02-hermes-agent-zero-provider-standup-design.md`).
Knuckles standup evidence: AGNOTE4482.md § Cloud-Hybrid Provider Standup.
SPARK's differences: 128GB unified memory (70B+ worker lanes), ARM64 CUDA,
native shape-worker role, registered CI runner `pmoves-spark-runner`.

## Steps

1. **Hermes install/update**
   ```bash
   ssh pmoves-spark
   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
   hermes update && hermes --version   # expect >= v0.18.0
   ```

2. **Profile** — `hermes profile create pmoves-hermes-spark && hermes profile use pmoves-hermes-spark`,
   then copy `pmoves/config/profiles/hermes/spark.yaml` over
   `~/.hermes/profiles/pmoves-hermes-spark/config.yaml` and run `hermes doctor --fix`.
   The profile is TZ-first; point `providers.tensorzero.base_url` at SPARK's own
   TZ if it runs one, else the fleet gateway over Tailscale.

3. **Secrets** — from the SPARK checkout: `make -C pmoves secrets-funnel`.
   Same fill-list as Knuckles applies (all 8 provider keys; see AGNOTE record).

4. **Worker candidates (dynamic — NO pinned IDs)** — run the same pipeline as
   Knuckles against SPARK's fit envelope (~110GB usable):
   - research live via HF API / `hf-mem` (70B-class per family now viable:
     e.g. the Hermes-4-70B and Kimi-Dev-72B lanes fit unquantized/Q8);
   - sign the selection trail: `python pmoves/tools/sign_trail.py --agent-id spark-codex ...`
     (spark identity needs an active signing card — verify with
     `verify_agent_identity('spark-codex')` first; add a card via the PR 0
     pattern if missing);
   - register: `POST /api/model-candidates` (model-registry :8110);
   - promote: provider/model/alias rows via PostgREST (service_role), alias
     `registry_worker_<lane>`;
   - splice: `python pmoves/tools/tz_registry_sync.py --models-json <payload>`;
   - recreate the TZ gateway via the make up path (NEVER `docker compose restart`).

5. **Ollama reachability** — SPARK serves the fleet (`ollama_spark` TZ provider
   at `http://pmoves-gb10-spark:11434/v1`): ensure `OLLAMA_HOST=0.0.0.0:11434`
   systemd override (fleet convention, PR #1162) and tailnet ACLs permit :11434.

6. **Shape worker (native role)** — `docker compose --profile <spark profile> up -d spark-shape-worker`
   with authenticated `NATS_URL`; verify one `mesh.shape.handshake.v1` emission
   after a worker inference (`nats sub "mesh.shape.handshake.v1" --count 1`).

7. **Verification checklist** (mirror Knuckles):
   - [ ] `curl -sf http://127.0.0.1:3030/health` (or fleet TZ)
   - [ ] `pmoves_worker_*` smoke returns from local endpoints
   - [ ] `hermes doctor` clean; delegation smoke on `pmoves_worker_hermes`
   - [ ] gateway :7700 healthy once a messaging platform token is provisioned
   - [ ] `mesh.node.announce.v1` visible from node-registry (:8115)
   - [ ] Record evidence in the "Applied" section below + AGNOTE ACK

## Applied

_(empty — fill on live apply)_
