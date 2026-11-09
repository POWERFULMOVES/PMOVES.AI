# Model — Dispatch

Route a task to the right model suit via the fleet's dispatch surfaces (local-first, TensorZero gateway, coding-plan lanes).

## Arguments

- `$ARGUMENTS` - the task description and optional constraints (context size, multimodal, long-context, cost tier, harness target)

## Instructions

1. Read the truth before routing — never route from memory:
   - Model suits: `pmoves/configs/model-suits/*.yaml` (id, role, context_window, fallback chain)
   - Provider cascades: `pmoves/tools/models/{kilocode,minimax}_provider_cascade.yaml`
   - Contract: `pmoves/docs/MODEL_FABRIC_CONTRACT.md` — the local-first order is law: `local -> Ollama Cloud -> Cloudflare free tier -> coding-plan lanes`
2. Match the task shape to the suit role:
   - Long-context research / massive docs → MiniMax-M3 → minimax-m2.7 (1M windows; Token Plan)
   - Blueprint-first implementation → kiloclaw lanes (glm-5.1 via Z.AI coding plan)
   - Local/private → Ollama suits on the node's profile (`pmoves/config/profiles/*.yaml`)
   - Harness-dispatched work → the bootstrap routing table (`pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml`), e.g. publish to `pmoves.agent.task.v1` with target `glm-5.1` / `hermes-3` / `mavis`
3. Gateway path when a suit routes through TensorZero: in-network base is `:3000` (3030 is host-only); check `http://localhost:3000/health` first.
4. MiniMax specifics: model IDs are case-sensitive (`MiniMax-M3`), endpoint `api.minimax.io/v1/chat/completions` (OpenAI-compatible), token-plan key `MINIMAX_TOKEN_PLAN_API_KEY` from the tier envs; a 401 on a correct path is key custody, not routing.
5. Report the chosen suit, the surface used, and the fallback chain armed.

## Notes

- Never hardcode a key; read from tier env files via `pmoves/scripts/with-env.sh`.
- Quota-exhausted on a Token Plan tier falls to the cascade's next entry — do not silently retry the same tier.
