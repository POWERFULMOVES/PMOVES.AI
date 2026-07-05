---
name: google-workspace
description: >
  Access Google Workspace (Drive, Docs, Sheets, Calendar, Gmail) via MCP.
  Read Drive files, edit Docs and Sheets, check Calendar, read/send Gmail.
  Uses OAuth credentials (GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET).
  Also provides Gemini API access via separate gemini MCP server.
---

# google-workspace — Google Workspace + Gemini Integration

Connects Claude Code to Google Workspace and Gemini API via MCP. Enables
reading Drive files, editing Docs/Sheets, Calendar access, and Gmail — plus
Gemini AI for additional model capabilities.

## Prerequisites

### Google OAuth Setup (one-time)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select project → Enable APIs:
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Google Calendar API
   - Gmail API
3. Create OAuth 2.0 credentials → Desktop app
4. Download credentials → add to `pmoves/env.shared` (Known Road — use `make secrets-*`):
   ```bash
   GOOGLE_CLIENT_ID=<your-client-id>
   GOOGLE_CLIENT_SECRET=<your-client-secret>
   ```
5. First use triggers OAuth browser flow → generates refresh token

### Gemini API Key
1. Get API key from [Google AI Studio](https://aistudio.google.com/)
2. Add to `pmoves/env.shared`: `GEMINI_API_KEY=<your-key>`

## Operations

### Google Drive
```text
Ask Claude: "List my Google Drive files in CataclysmstudiosInc/POWERFULMOVES"
Ask Claude: "Download the PMOVES roadmap doc from Drive"
Ask Claude: "Search Drive for files mentioning 'MoF architecture'"
```

### Google Docs/Sheets
```text
Ask Claude: "Read the POWERFULMOVES planning doc"
Ask Claude: "Add today's session summary to the PMOVES session log sheet"
Ask Claude: "Create a new Doc for the AgentGym results report"
```

### Google Calendar
```text
Ask Claude: "What's on my calendar this week?"
Ask Claude: "Schedule a PMOVES demo session for Friday at 3pm"
```

### Gmail
```text
Ask Claude: "Check for emails about PMOVES from this week"
Ask Claude: "Draft a reply to the last DARKXSIDE message"
```

### Gemini API
```text
Ask Claude: "Use Gemini to summarize this long document"
Ask Claude: "Run Gemma4 embedding on this text for the Geometry Bus"
```

## Gemini Models Available

| Model | Use Case | Notes |
|-------|----------|-------|
| `gemini-2.0-flash` | Fast reasoning, chat | Primary Gemini model |
| `gemini-2.0-pro` | Deep reasoning | Complex analysis |
| `gemma-3-27b-it` | Local-compatible instruction | Unsloth variant on SPARK |
| `text-embedding-004` | Embeddings | Geometry Bus / CHIT vectors |

## PMOVES Integration Points

- **Geometry Bus**: Gemma embeddings → `geometry.embed.v1` NATS subject
- **CHIT**: Embedding vectors feed Hi-RAG v2 (port 8086/8087)
- **2nd Brain**: Drive + Obsidian form dual sync of POWERFULMOVES knowledge

## Notes

- OAuth refresh tokens persist across sessions — re-auth only if token expires
- Google Workspace MCP covers Docs/Sheets/Calendar/Gmail
- GDrive MCP covers file listing and download
- Both use same OAuth credentials
- See `obsidian-brain` for local vault access
- See `chit:bus` for NATS geometry bus events
