# MiniMax — KiloCode Command

Run MiniMax M2.7 health checks, model verification, and BoTZ integration tests.

## Health Checks

```bash
# Cloud token plan — model list
curl -sf https://api.minimax.io/v1/models \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(m['id']) for m in d.get('data',[])]"

# Cloud token plan — single completion test
curl -sf https://api.minimax.io/v1/chat/completions \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-M2.7","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])"

# Wave-function collapse toggle test
curl -sf https://api.minimax.io/v1/chat/completions \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-M2.7","max_tokens":50,"messages":[{"role":"user","content":"count from 1 to 5"}]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])"
```

## Model Verification

```bash
# Verify M2.7 is the default
MODEL_NAME=$(curl -sf https://api.minimax.io/v1/models \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); models=[m['id'] for m in d.get('data',[])]; print('MINIMAX_M27' if 'MiniMax-M2.7' in models else 'MISSING')")
echo "M2.7 status: $MODEL_NAME"

# Verify M2.1 is available
curl -sf https://api.minimax.io/v1/models \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); models=[m['id'] for m in d.get('data',[])]; print('M2.1 OK' if 'MiniMax-M2.1' in models else 'M2.1 MISSING')"
```

## Integration Checks

```bash
# HERMES ↔ MiniMax provider test (if HERMES_API_KEY set)
hermes model 2>&1 | grep -i minimax || echo "HERMES not configured for MiniMax"

# TensorZero routing (if TENSORZERO_BASE_URL set)
curl -sf http://localhost:3030/api/routing \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('MiniMax routing:', d.get('minimax', 'NOT FOUND'))"

# BoTZ affinity check
curl -sf http://localhost:3030/api/status \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('BoTZ:', d.get('botz', {}).get('minimax_affinity', 'n/a'))"
```

## Full Smoke

```bash
# One-shot MiniMax smoke
set -e
export MINIMAX_API_KEY="${MINIMAX_API_KEY:?Need MINIMAX_API_KEY}"
curl -sf https://api.minimax.io/v1/models \
  -H "Authorization: Bearer $MINIMAX_API_KEY" > /dev/null \
  && echo "MiniMax API: OK" \
  || echo "MiniMax API: FAIL"
curl -sf https://api.minimax.io/v1/chat/completions \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-M2.7","max_tokens":20,"messages":[{"role":"user","content":"say hello in 3 words"}]}' \
  | python3 -c "import json,sys; print('M2.7 completion:', json.load(sys.stdin)['choices'][0]['message']['content'])"
```

## Environment Variables Needed

```bash
MINIMAX_API_KEY        # MiniMax token plan API key
MINIMAX_API_BASE      # https://api.minimax.io/v1 (global) or https://api.minimaxi.com/anthropic/v1 (China)
```

## References

- pmoves/configs/agent-profiles/minimax_claw.yaml
- pmoves/docs/AGENTS/HERMES_INTEGRATION.md
- pmoves/config/tensorzero/tensorzero.minimax.toml