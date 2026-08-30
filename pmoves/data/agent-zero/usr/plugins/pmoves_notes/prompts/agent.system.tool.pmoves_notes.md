## pmoves notes tools
persistent notes in PMOVES.AI Open Notebook; use to save durable findings or recall earlier notes
- `save_note`: args `content`, optional `title`, `tags` (list of strings; folded into the note body)
- `search_notes`: args `query`, optional `limit` (default 10, max 50)

notes:
- `save_note` returns the new note id; `search_notes` runs a text search and returns matching notes with snippets
- use `save_note` for stable findings/decisions worth keeping, not one-off chatter
- conversation summaries and reasoning traces are captured automatically; use these tools for explicit, agent-directed notes

example:
~~~json
{
  "thoughts": ["This finding is worth keeping for later."],
  "headline": "Saving a note",
  "tool_name": "save_note",
  "tool_args": {
    "content": "Open Notebook stores notes in SurrealDB; the API is at /api/notes.",
    "title": "Open Notebook storage",
    "tags": ["research", "open-notebook"]
  }
}
~~~
