# hf-agent

Polls the Hugging Face Hub for models matching the configured criteria and publishes each new one once on `hf.model.discovered.v1`. Registry row: `hf_agent` (port 8201, `/healthz`). `hf-research-agent` consumes the subject and scores the model.

## Discovery payload

`model_id`, `tags`, `downloads`, `likes`, `last_modified`, `pipeline_tag`, `author`, `hf_url`, `discovered_at`, and since 2026-10-11 `library_name` and `gated` when the Hub returns them (`gated` is `False`, `"auto"` or `"manual"`; a gated model needs an accepted licence before any fleet node can pull it). The card itself (licence, `model-index` evaluations, base model) is read downstream by `hf-research-agent`, not here, so the poll loop stays one request per page.

## Env

| Var | Default | Meaning |
|---|---|---|
| `NATS_URL` | `nats://nats:4222` | bus (compose injects the credentialed URL) |
| `HF_TOKEN` | unset | via `_load_secret`; raises the rate limit, optional |
| `HF_POLL_INTERVAL` | `300` | seconds |
| `HF_TASK_FILTER` | empty | `pipeline_tag`, e.g. `text-generation` |
| `HF_TAGS` | empty | comma list, Hub `filter` |
| `HF_AUTHOR` | empty | namespace |
| `HF_SORT` / `HF_DIRECTION` / `HF_LIMIT` | `lastModified` / `-1` / `50` | page shape (`direction` only on the legacy API) |

The `huggingface_hub` version shim (`ModelFilter` before 1.0, keyword filters after) is in `_build_list_models_kwargs`.
