# Z.AI GLM Coding Plan Reference

## API Endpoints

| Endpoint | URL |
|----------|-----|
| Coding API (primary) | `https://api.z.ai/api/coding/paas/v4` |
| API Key Management | `https://z.ai/manage-apikey/apikey-list` |
| MCP Vision | `https://api.z.ai/api/mcp/vision/mcp` |
| MCP Web Search | `https://api.z.ai/api/mcp/web_search_prime/mcp` |
| MCP Web Reader | `https://api.z.ai/api/mcp/web_reader/mcp` |
| MCP Zread | `https://api.z.ai/api/mcp/zread/mcp` |

## Model Matrix

| Model | Context | Use Case | Mapping |
|-------|---------|----------|---------|
| glm-5.1 | 128K | Primary coding, complex reasoning | claude-sonnet-4, claude-opus-4 |
| glm-4.7 | 128K | Balanced tasks, fallback | claude-sonnet-4 |
| glm-4.5-air | 128K | Fast, lightweight tasks | claude-haiku-4-5 |
| glm-4.6v | — | Vision analysis (MCP server) | N/A (tool-based) |

## Claude Code Configuration

```json
{
  "apiProvider": "openai-compatible",
  "apiKey": "${Z_AI_API_KEY}",
  "baseURL": "https://api.z.ai/api/coding/paas/v4",
  "model": "glm-5.1"
}
```

## Kilo Code Configuration

Set in `kilo.json` under `agents`:
```json
{
  "agents": {
    "model": "glm-5.1",
    "modelProvider": "zai",
    "modelFallback": "glm-4.7",
    "codingApiEndpoint": "https://api.z.ai/api/coding/paas/v4"
  }
}
```

## OpenClaw Configuration

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "glm-5.1",
        "fallback": "glm-4.7",
        "provider": "zai"
      }
    }
  }
}
```

## MCP Servers

4 servers available — see `.kilo/command/zai-mcp.md` for full reference.

| Server | Type | Endpoint |
|--------|------|----------|
| zai-vision | stdio (npx) | `npx -y @z_ai/mcp-server` |
| zai-web-search | streamable-http | `https://api.z.ai/api/mcp/web_search_prime/mcp` |
| zai-web-reader | streamable-http | `https://api.z.ai/api/mcp/web_reader/mcp` |
| zai-zread | streamable-http | `https://api.z.ai/api/mcp/zread/mcp` |

## Usage Limits

| Plan | Coding API | Search+Reader+Zread | Vision |
|------|-----------|---------------------|--------|
| Lite | Standard | 100/month | 5-hour pool |
| Pro | Priority | 1,000/month | 5-hour pool |
| Max | Highest priority | 4,000/month | 5-hour pool |
