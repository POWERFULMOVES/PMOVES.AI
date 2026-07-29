# Agent Zero Configuration

Main configuration lives in `usr/settings.json` and the Settings Web UI.

LLM roles:
- `chat_llm`: primary reasoning and tool use
- `utility_llm`: summaries, memory queries, compression, filtering
- `embedding_llm`: vector embeddings for memory and knowledge

Profiles live in `agents/<profile>/`; user profiles live in `usr/agents/<profile>/`. Profiles override prompt fragments without changing the framework.

Plugins live in `plugins/` and `usr/plugins/`. Each plugin has a `plugin.yaml`; activation can be global or scoped to projects/profiles.

Projects isolate workdir, memory/knowledge scope, custom instructions, secrets, MCP config, and repositories.

Environment settings can use `A0_SET_<setting_name>=<value>`.
