# TensorZero Models

List all available models dynamically from TensorZero configuration.

## Instructions

1. **Extract models from tensorzero.toml** (source of truth):
   ```bash
   grep -E "^\[models\." pmoves/tensorzero/config/tensorzero.toml | sed 's/\[models\.//' | sed 's/\]//' | sort
   ```

2. **Extract embedding models**:
   ```bash
   grep -E "^\[embedding_models\." pmoves/tensorzero/config/tensorzero.toml | sed 's/\[embedding_models\.//' | sed 's/\]//' | sort
   ```

3. **Show provider routing** for each model:
   ```bash
   grep -A2 "^\[models\." pmoves/tensorzero/config/tensorzero.toml | grep "routing"
   ```

4. **Check live provider availability**:
   ```bash
   # Ollama models
   curl -sf http://localhost:11434/api/tags 2>/dev/null | jq -r '.models[].name' || echo "Ollama: offline"

   # TensorZero gateway
   curl -sf http://localhost:3030/health 2>/dev/null && echo "TensorZero: online" || echo "TensorZero: offline"
   ```

5. **Group by provider type** by parsing the routing field from toml

Report:
- Total model count (chat + embedding)
- Models grouped by provider
- Which providers are currently online
- Dynamic syntax reminder: `provider::model_name`

**Note:** All model information comes from `pmoves/tensorzero/config/tensorzero.toml` - no hardcoded lists.
