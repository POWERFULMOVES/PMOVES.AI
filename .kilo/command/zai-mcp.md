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

### Vision (local, requires Node.js >= v22)
```
npx -y @z_ai/mcp-server
```

### Remote servers
Automatically available when Z_AI_API_KEY is set.

## Rate Limits (per GLM Coding Plan)

| Plan | Search+Reader+Zread | Vision |
|------|---------------------|--------|
| Lite | 100/month | 5-hour pool |
| Pro | 1,000/month | 5-hour pool |
| Max | 4,000/month | 5-hour pool |

## References

- https://docs.z.ai/devpack/mcp/vision-mcp-server
- https://docs.z.ai/devpack/mcp/search-mcp-server
- https://docs.z.ai/devpack/mcp/reader-mcp-server
- https://docs.z.ai/devpack/mcp/zread-mcp-server
