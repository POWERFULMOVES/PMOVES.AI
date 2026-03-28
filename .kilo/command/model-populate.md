# Model Population

Pull and register local models from your YouTube playlist discovery.

## Arguments

- `$ARGUMENTS` — Model name(s) to pull, or "all" for full catalog

## Implementation

Pull a model via Ollama:
```bash
ollama pull $ARGUMENTS
```

Register via sync profile (per `models_sync.py` CLI):
```bash
python3 pmoves/tools/models/models_sync.py sync --profile agent-zero --host workstation_5090
```

Swap a single service model:
```bash
python3 pmoves/tools/models/models_sync.py swap --service agent-zero --name $ARGUMENTS
```

List seed models:
```bash
python3 pmoves/tools/models/models_sync.py seed-list --host workstation_5090 --source auto
```

Verify readiness:
```bash
make -C pmoves model-readiness
```

## YouTube Playlist Models

Common models tracked from the local model discovery playlist:
- qwen3-coder:32b — coding specialist
- qwen3-vl:8b — vision-language
- deepseek-r1:32b — reasoning
- gemma3:embed — embeddings
- llama4:scout — efficient inference

## Notes

- Use PMOVES.Flare naming: pmoves/<model-family>/<variant>
- GPU orchestrator auto-discovers via mesh.gpu.model.loaded.v1
- vLLM can serve any Ollama model with higher throughput
