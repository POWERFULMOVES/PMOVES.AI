# Agent Zero Architecture

The agent loop builds a system prompt, appends conversation history, asks the model for one JSON tool request, executes that tool, records the result, and repeats until `response` ends the task.

Key runtime files:
- `agent.py`: `Agent`, `AgentContext`, loop state, tool dispatch
- `initialize.py`: framework initialization
- `run_ui.py`: Web UI entry point
- `helpers/`: shared framework helpers
- `tools/`: core tools
- `plugins/`: framework plugins
- `usr/`: user data, custom plugins, settings, workdir

Prompt assembly is file-based. Main prompts come from `prompts/`, profile overrides from `agents/<profile>/prompts/`, and plugin prompts from `plugins/<plugin>/prompts/`.

Plugins can add tools, prompts, API handlers, Web UI components, extensions, and hooks. User plugins live in `usr/plugins/` and should survive updates.

Memory and knowledge use the memory plugin and vector search. Knowledge files are indexed for recall; they should be concise because irrelevant recall can steer behavior badly.
