# Deep Research Service

The deep research runner collects user prompts, supporting context, and optional
resources before delegating work to an LLM provider. Callers can now reference
curated Qwen cookbooks to extend the model context for a specific run.

## Cookbook Resources

Set the optional `resources.cookbooks` field on the request payload to specify
which Markdown guides should be injected. Each entry can be either a path within
[`https://github.com/QwenLM/Qwen3-VL/tree/main/cookbooks`](https://github.com/QwenLM/Qwen3-VL/tree/main/cookbooks)
(e.g. `vision/multimodal_retrieval.md`) or a fully-qualified raw URL.

When provided, the runner will:

1. Download and cache the referenced cookbooks via `pmoves.services.deepresearch.cookbooks.load_cookbooks`.
2. Merge the full Markdown contents into `user_payload["context"]` before the
   provider call so the LLM sees the additional references.
3. Attach short excerpts of each cookbook into the outgoing notebook payload so
   operators can trace which resources influenced the run.

The helper performs in-memory caching, so repeated references reuse previously
fetched Markdown without additional network calls.
