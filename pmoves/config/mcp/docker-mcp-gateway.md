# Docker MCP Gateway for PMOVES.AI

**Version**: Docker MCP Toolkit v0.42.1
**Gateway Status**: Running on port 8090 (SSE transport)
**Auth**: MCP_GATEWAY_AUTH_TOKEN required
**Profile**: `default` (current) / `pmoves-ai` (target)

## Default Profile Servers

| Server | Type | Tools | Relevance to PMOVES |
|--------|------|-------|---------------------|
| **github-official** | image | 36 tools | PR review, repo management, issue tracking |
| **hostinger-mcp-server** | image | 78 tools | **CRITICAL**: VPS, DNS, domain, hosting, billing |
| **hugging-face** | remote | 8 tools | Model search, paper search, space search |
| **openapi** | image | 5 tools | OpenAPI spec validation, curl generation |
| **openapi-schema** | image | 2 tools | Schema component analysis |
| **thirdweb** | image | 10 tools | Smart contract generation (ERC20, ERC721, etc.) |

## Hostinger MCP Tools (For Ageless Beauty Migration)

### DNS Management
- `DNS_deleteDNSRecordsV1`
- `DNS_getDNSRecordsV1`
- `DNS_updateDNSRecordsV1`
- `DNS_validateDNSRecordsV1`

### VPS Management
- `VPS_createNewVirtualMachineV1`
- `VPS_getVirtualMachinesV1`
- `VPS_restartVirtualMachineV1`
- `VPS_getMetricsV1`
- `VPS_getBackupsV1`

### Domain Management
- `domains_checkDomainAvailabilityV1`
- `domains_getDomainListV1`
- `domains_purchaseNewDomainV1`
- `domains_updateDomainNameserversV1`

### Hosting
- `hosting_listWebsitesV1`
- `hosting_createWebsiteV1`
- `hosting_listAvailableDatacentersV1`

### Billing
- `billing_getSubscriptionListV1`
- `billing_getPaymentMethodListV1`

## Gateway Commands

```bash
# Start gateway with default profile
docker mcp gateway run --profile default --port 8090 --transport sse --log-calls

# Start gateway with PMOVES profile (to be created)
docker mcp gateway run --profile pmoves-ai --port 8090 --transport sse

# Dry run (test config without starting)
docker mcp gateway run --profile default --dry-run

# List available servers in catalog
docker mcp catalog list

# List profiles
docker mcp profile list
```

## Hermes Integration

To connect Hermes Agent to the Docker MCP Gateway:

1. Set `MCP_GATEWAY_AUTH_TOKEN` in `.env`
2. Configure `config.yaml` mcp_servers section:

```yaml
mcp_servers:
  docker_mcp_gateway:
    url: "http://localhost:8090/sse"
    auth_token: "${MCP_GATEWAY_AUTH_TOKEN}"
    tools: "*"
```

3. Hermes will auto-discover all tools from the gateway

## Secrets

Docker MCP uses Docker Desktop secrets store by default.
Required secrets for PMOVES:
- `github.personal_access_token` (for github-official)
- `hostinger-mcp-server.api_token` (for Hostinger VPS operations)
- HuggingFace token (for hugging-face remote)

## Status

- [x] Docker MCP Toolkit installed (v0.42.1)
- [x] Default profile inspected (5 servers, 139 tools)
- [x] Gateway start tested (port 8090, SSE transport)
- [x] Hostinger MCP server available (78 tools)
- [ ] PMOVES-AI profile created (needs custom server selection)
- [ ] Auth token configured for Hermes integration
- [ ] Hermes config.yaml updated with MCP gateway URL
