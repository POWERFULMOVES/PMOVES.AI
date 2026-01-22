# {{SUBMODULE_NAME}} Integration with PMOVES.AI

## Integration Overview

This document describes how {{SUBMODULE_NAME}} integrates with PMOVES.AI.

## Quick Start

### 1. Submodule Setup

```bash
# Clone PMOVES.AI with submodules
git clone --recurse-submodules https://github.com/pmoves/PMOVES.AI.git
cd PMOVES.AI/pmoves
```

### 2. Configuration

```bash
# Copy environment template
cp {{ENV_TEMPLATE}} env.local

# Edit configuration
nano env.local
```

### 3. Start

```bash
# Start {{SUBMODULE_NAME}}
make {{START_COMMAND}}
```

## Service Discovery

{{SUBMODULE_NAME}} registers with the PMOVES.AI Service Registry:

```json
{
  "name": "{{SERVICE_NAME}}",
  "host": "{{DEFAULT_HOST}}",
  "port": {{DEFAULT_PORT}},
  "mode": "{{DEFAULT_MODE}}",
  "capabilities": [{{CAPABILITIES}}]
}
```

## API Integration

### REST API

{{SUBMODULE_NAME}} exposes the following APIs:

{{API_ENDPOINTS}}

### NATS Events

{{SUBMODULE_NAME}} publishes/consumes these NATS subjects:

| Subject | Direction | Description |
|---------|-----------|-------------|
{{NATS_EVENTS_TABLE}}

## Data Flow

```
{{DATA_FLOW_DIAGRAM}}
```

## Multi-Host Deployment

### On Main PC (Docked)

{{MAIN_PC_DEPLOYMENT}}

### On Edge Device (Standalone)

{{EDGE_DEPLOYMENT}}

## Service Dependencies

{{SUBMODULE_NAME}} depends on:

{{SERVICE_DEPENDENCIES}}

## Integration Testing

```bash
# Test integration
cd pmoves
make test-integration SERVICE={{SERVICE_NAME}}

# Or use the test script
pmoves/tests/integration/test_{{SERVICE_NAME}}.py
```

## Troubleshooting

### Common Issues

**Issue**: {{SERVICE_NAME}} not discovered

**Solution**:
```bash
# Check service registry
curl http://localhost:8100/api/services/{{SERVICE_NAME}}

# Check mesh agent logs
docker logs mesh-agent

# Verify NATS connection
docker logs nats
```

**Issue**: Cannot connect to {{SERVICE_NAME}}

**Solution**:
```bash
# Verify Tailscale connection
tailscale status

# Ping service
ping {{SERVICE_NAME}}

# Check firewall
sudo ufw status
```

## Migration Guide

### From Standalone to Docked

To migrate {{SUBMODULE_NAME}} from standalone to docked mode:

1. **Backup data**
   ```bash
   {{BACKUP_COMMAND}}
   ```

2. **Update configuration**
   ```bash
   # Change SERVICE_MODE from standalone to docked
   sed -i 's/SERVICE_MODE=standalone/SERVICE_MODE=docked/' env.local
   ```

3. **Restart service**
   ```bash
   make restart {{SERVICE_NAME}}
   ```

4. **Verify integration**
   ```bash
   make registry-status
   ```

## See Also

- `../../pmoves/docs/MULTI_HOST_DISCOVERY.md` - Multi-host setup
- `../../pmoves/docs/SECRETS_ONBOARDING.md` - Secrets configuration
- `../SUBMODULE.md` - Submodule context
