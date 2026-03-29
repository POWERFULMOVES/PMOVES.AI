# Z.AI MCP Servers

Manage Z.AI MCP servers for Kilo Code on 5090.

## Available Servers

| Server | Type | Purpose |
|--------|------|---------|
| Vision | stdio (npx) | Image/video analysis, OCR, UI-to-code |
| Web Search | streamable-http | Real-time web search |
| Web Reader | streamable-http | Full webpage content extraction |
| Zread | streamable-http | GitHub repo search and file reading |

## Configuration

Requires `Z_AI_API_KEY` in environment. Get from https://z.ai/manage-apikey/apikey-list.

### Vision (local)
Requires Node.js >= v22. Runs via npx.
```
npx -y @z_ai/mcp-server
```

### Remote servers
Automatically available when Z_AI_API_KEY is set.
- Web Search: https://api.z.ai/api/mcp/web_search_prime/mcp
- Web Reader: https://api.z.ai/api/mcp/web_reader/mcp
- Zread: https://api.z.ai/api/mcp/zread/mcp

## Rate Limits (per GLM Coding Plan)

| Plan | Search+Reader+Zread | Vision |
|------|---------------------|--------|
| Lite | 100/month | 5-hour pool |
| Pro | 1,000/month | 5-hour pool |
| Max | 4,000/month | 5-hour pool |

## Notes

- One Z.AI API key works across all 4 servers
- Vision requires local Node.js; remote servers need no install
- Reference: https://docs.z.ai/devpack/mcp/vision-mcp-server
