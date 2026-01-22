# {{SUBMODULE_NAME}} Submodule Context

## Purpose

{{DESCRIPTION}}

## Standalone Mode

When running standalone (independent of PMOVES.AI):

{{STANDALONE_CONFIG}}

## Docked Mode

When integrated with PMOVES.AI:

{{DOCKED_CONFIG}}

## PMOVES.AI Integration

### Service Registry

- **Service Name**: `{{SERVICE_NAME}}`
- **Registration**: Automatic via Mesh Agent
- **Discovery**: Via `GET /api/services/{{SERVICE_NAME}}`

### NATS Communication

- **Publish Subjects**:
{{NATS_PUBLISH}}

- **Subscribe Subjects**:
{{NATS_SUBSCRIBE}}

### MCP Integration

{{MCP_INTEGRATION}}

### CHIT Data

{{CHIT_USAGE}}

## Development

### Repository

- **URL**: `{{REPO_URL}}`
- **Branch**: `{{DEFAULT_BRANCH}}`
- **Path in PMOVES.AI**: `{{SUBMODULE_PATH}}`

### Build

```bash
cd {{SUBMODULE_PATH}}
{{BUILD_COMMANDS}}
```

### Test

```bash
cd {{SUBMODULE_PATH}}
{{TEST_COMMANDS}}
```

## Dependencies

### Required PMOVES.AI Services

{{DEPENDENCIES}}

### Optional Integrations

{{OPTIONAL_INTEGRATIONS}}

## Environment Variables

{{ENV_VARIABLES}}

## Ports

{{PORTS}}

## Health Checks

```bash
# Health endpoint
curl http://localhost:{{HEALTH_PORT}}/{{HEALTH_ENDPOINT}}

# Or check service registry
curl http://localhost:8100/api/services/{{SERVICE_NAME}}
```

## Troubleshooting

{{TROUBLESHOOTING}}

## See Also

- `../../pmoves/docs/DOCKING_ARCHITECTURE.md` - Docking architecture
- `../../pmoves/docs/MODULAR_ARCHITECTURE.md` - PMOVES.AI architecture
- `../../pmoves/docs/MULTI_HOST_DISCOVERY.md` - Multi-host setup
