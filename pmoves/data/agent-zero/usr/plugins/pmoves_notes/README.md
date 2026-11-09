# a0-plugin-pmoves-notes

**Persistent note-taking integration for Agent Zero with PMOVES.AI Open Notebook.**

## Overview

This plugin enables Agent Zero to automatically save conversation summaries and reasoning traces to PMOVES.AI's persistent knowledge base (Open Notebook / SurrealDB). It provides tools for manual note management and publishes events to NATS for coordination with other services.

## Features

- **Auto-save conversation summaries** after each message loop
- **Save reasoning traces** from agent monologues to persistent memory
- **Manual note tools** (`save_note`, `search_notes`) for agent-controlled notes
- **NATS event publishing** for note operations
- **Tag-based categorization** for easy retrieval
- **Full PMOVES.AI integration** (TensorZero, NATS, Open Notebook)

## Plugin layout

This repository is a self-contained Agent Zero plugin (repo root **is** the
plugin root). It follows the standard plugin conventions so Agent Zero can
discover its tools and extensions automatically:

```text
plugin.yaml                                              # manifest (name: pmoves_notes)
README.md
LICENSE
requirements.txt
prompts/
  agent.system.tool.pmoves_notes.md                     # advertises save_note / search_notes to the model
tools/
  save_note.py        -> class SaveNote(Tool)            # tool name: save_note
  search_notes.py     -> class SearchNotes(Tool)         # tool name: search_notes
extensions/
  python/
    message_loop_end/
      _10_auto_save_conversation.py    -> AutoSaveConversation(Extension)
    reasoning_stream/
      _50_capture_reasoning.py         -> CaptureReasoning(Extension)
    reasoning_stream_end/
      _50_save_reasoning_trace.py      -> SaveReasoningTrace(Extension)
```

Tools subclass `helpers.tool.Tool` and implement `async def execute(...) -> Response`,
and are advertised to the model via `prompts/agent.system.tool.pmoves_notes.md`.
Extensions subclass `helpers.extension.Extension`, live under
`extensions/python/<point>/`, and persist notes in a background `DeferredTask`
so they never block the agent loop. Reasoning is captured at `reasoning_stream`
(the chain-of-thought source) and persisted at `reasoning_stream_end` — not from
`loop_data.last_response`, which is the agent's response, not its reasoning.

## Installation

### Via the Agent Zero Plugin Hub (recommended)

In Agent Zero → **Settings → Plugins → Install from Git**, paste this
repository URL. Agent Zero validates `plugin.yaml`, installs the plugin into
`usr/plugins/pmoves_notes/`, and loads its tools and extensions.

### Via the PMOVES plugin index (internal)

This plugin is listed in the **PMOVES** fork index at
[POWERFULMOVES/PMOVES-a0-plugins](https://github.com/POWERFULMOVES/PMOVES-a0-plugins)
under `plugins/pmoves_notes/` — a PMOVES-internal staging index, not the
community-maintained channel. The index folder name must match the `name` field
in this repo's `plugin.yaml`.

To make the plugin discoverable to **all** Agent Zero users, submit it to the
official community index at [agent0ai/a0-plugins](https://github.com/agent0ai/a0-plugins):
fork that repo, add `plugins/pmoves_notes/index.yaml` pointing at this
repository, and open a PR (its CI validates that the remote `plugin.yaml` `name`
exactly matches the folder name).

### Manual installation

```bash
git clone https://github.com/POWERFULMOVES/Pmoves-a0-plugin-pmoves-notes.git
# Copy the whole plugin into the Agent Zero user plugins directory:
cp -r Pmoves-a0-plugin-pmoves-notes /a0/usr/plugins/pmoves_notes
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|-----------|---------|-------------|
| `OPEN_NOTEBOOK_API_URL` | No | `http://open-notebook:5055` | Open Notebook API endpoint |
| `OPEN_NOTEBOOK_API_TOKEN` | No | | API token for authentication |
| `NATS_URL` | No | `nats://nats:pmoves@nats:4222` | NATS connection URL |
| `PMOVES_NOTES_ENABLED` | No | `true` | Enable/disable plugin |
| `PMOVES_NOTES_MIN_REASONING_LENGTH` | No | `100` | Min reasoning length to save |

### Docker Compose Example

```yaml
services:
  agent-zero:
    image: ghcr.io/powerfulmoves/pmoves-agent-zero:pmoves-latest
    environment:
      - OPEN_NOTEBOOK_API_URL=http://open-notebook:5055
      - OPEN_NOTEBOOK_API_TOKEN=${OPEN_NOTEBOOK_TOKEN}
      - NATS_URL=nats://nats:pmoves@nats:4222
      - PMOVES_NOTES_ENABLED=true
    depends_on:
      - open-notebook
      - nats
```

## Extension Points

### message_loop_end

Automatically saves a conversation summary after each message loop, sourced from
`self.agent.history.output_text()`. `BACKGROUND` contexts are skipped.

**Tags applied:** `conversation`, `auto-saved`, `<agent_name>`

### reasoning_stream + reasoning_stream_end

Captures the agent's chain-of-thought and persists it as a reasoning trace.
`reasoning_stream` (`_50_capture_reasoning.py`) stashes the full reasoning text
on the agent; `reasoning_stream_end` (`_50_save_reasoning_trace.py`) persists it
(when it exceeds `PMOVES_NOTES_MIN_REASONING_LENGTH`) and clears the stash.
`BACKGROUND` contexts are skipped so internal reasoning is not surfaced.

**Tags applied:** `reasoning`, `trace`, `<agent_name>`, `memory`

## Tools

### save_note

Manually save a note to Open Notebook.

```python
{
  "content": "Important finding from research...",
  "title": "Research Notes 2026-03-13",
  "tags": ["research", "findings"]
}
```

**Parameters:**
- `content` (required): Note content
- `title` (optional): Note title
- `tags` (optional): List of tags

**Returns:** Note ID and confirmation

### search_notes

Run a text search over the knowledge base (`POST /api/search`, scoped to notes).

```python
{
  "query": "Agent Zero integration patterns",
  "limit": 10
}
```

**Parameters:**
- `query` (required): Search query
- `limit` (optional): Max results (default: 10, max 50)

**Returns:** List of matching notes with snippets

## NATS Events

### agent.notes.saved.v1

Published when a note is created or updated.

```json
{
  "note_id": "uuid",
  "title": "Note Title",
  "tags": ["tag1", "tag2"],
  "timestamp": "2026-03-13T14:00:00Z"
}
```

### agent.notes.searched.v1

Published when a note search is performed.

```json
{
  "query": "search term",
  "results_count": 5,
  "timestamp": "2026-03-13T14:00:00Z"
}
```

## PMOVES.AI Integration

This plugin follows PMOVES.AI integration patterns:

1. **TensorZero**: Uses TensorZero format for any LLM calls (if added)
2. **NATS**: Authenticated NATS URL (`nats://nats:pmoves@nats:4222`)
3. **Open Notebook**: Connects to SurrealDB knowledge base at port 5055
4. **Security**: No hardcoded credentials; uses environment variables
5. **Observability**: Publishes events for service mesh monitoring

## Usage Example

```python
# In Agent Zero, the plugin automatically saves conversations

# User: "Research PMOVES.AI integration patterns"
# Agent: [Reasoning...] [Saves reasoning trace via reasoning_stream_end extension]
# Agent: [Provides answer]
# [Message loop ends → Auto-saves conversation summary via message_loop_end extension]

# Agent can also manually save notes
# Agent: Let me save that important finding to my notes.
# [Calls save_note tool]

# Agent can search existing knowledge
# Agent: Let me check what I know about TensorZero integration.
# [Calls search_notes tool]
```

## Development

The plugin runs inside the Agent Zero runtime, which provides `helpers.tool`,
`helpers.extension`, `helpers.defer`, `helpers.print_style`, and `aiohttp`. To
exercise it, install it into a running Agent Zero (see Installation) and watch
the agent logs while it converses — conversation summaries and reasoning traces
appear in Open Notebook, and `save_note` / `search_notes` are available as tools.

Before contributing changes upstream, run Agent Zero's **a0-review-plugin**
skill (4-phase audit: manifest, structure, code patterns, security + index) and
resolve any FAIL items.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow PMOVES.AI security patterns
4. Add tests for new features
5. Submit a PR

## License

MIT License - see LICENSE file for details

## Author

POWERFULMOVES

## See Also

- [PMOVES.AI Documentation](https://github.com/POWERFULMOVES/PMOVES.AI)
- [Agent Zero Documentation](https://github.com/POWERFULMOVES/PMOVES-Agent-Zero)
- [PMOVES-a0-plugins Index](https://github.com/POWERFULMOVES/PMOVES-a0-plugins)
- [Open Notebook](https://github.com/POWERFULMOVES/PMOVES-Open-Notebook)
