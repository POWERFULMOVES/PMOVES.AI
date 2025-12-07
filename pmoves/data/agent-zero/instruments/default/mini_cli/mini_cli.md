# Problem
Execute PMOVES Mini CLI commands for unified environment setup, hardware-aware bring-up, MCP tooling, CHIT secret management, and infrastructure operations.

# Solution
Use the Mini CLI Python module to manage PMOVES infrastructure across heterogeneous hardware (desktop GPU rigs, laptops, Jetson edge devices).

## Command Surface

### Core Commands
```bash
# Bootstrap env files + stage provisioning bundle
python3 -m pmoves.tools.mini_cli bootstrap [--with-glancer]

# Secrets sync + env generation + profile detection
python3 -m pmoves.tools.mini_cli init [--generate]

# Aggregate readiness (env, MCP, compose, models, Glancer)
python3 -m pmoves.tools.mini_cli status
```

### Hardware Profiles
```bash
# List available profiles
python3 -m pmoves.tools.mini_cli profile list

# Show profile details (hardware, compose overrides, model bundles, MCP adapters)
python3 -m pmoves.tools.mini_cli profile show <profile_id>

# Auto-detect hardware and suggest profiles
python3 -m pmoves.tools.mini_cli profile detect [--top 3]

# Set active profile (writes to ~/.pmoves/profile.yaml)
python3 -m pmoves.tools.mini_cli profile apply <profile_id>

# Display active profile
python3 -m pmoves.tools.mini_cli profile current
```

### MCP Toolkit Management
```bash
# List configured MCP toolkits with availability status
python3 -m pmoves.tools.mini_cli mcp list

# Run MCP health checks
python3 -m pmoves.tools.mini_cli mcp health

# Show setup instructions for a specific tool
python3 -m pmoves.tools.mini_cli mcp setup <tool_id>
```

### CHIT Secret Management
```bash
# Encode env to CHIT CGP bundle
python3 -m pmoves.tools.mini_cli secrets encode \
  [--env-file pmoves/env.shared] \
  [--out pmoves/pmoves/data/chit/env.cgp.json] \
  [--no-cleartext]

# Decode CHIT bundle to env format
python3 -m pmoves.tools.mini_cli secrets decode \
  [--cgp pmoves/pmoves/data/chit/env.cgp.json] \
  [--out /tmp/env.decoded]
```

### Dependency Management
```bash
# Check if host dependencies are available
python3 -m pmoves.tools.mini_cli deps check

# Install missing dependencies
python3 -m pmoves.tools.mini_cli deps install [--yes] [--use-container]
```

### Automation Management
```bash
# List n8n automations and channels
python3 -m pmoves.tools.mini_cli automations list

# Show webhook endpoints
python3 -m pmoves.tools.mini_cli automations webhooks

# Filter automations by channel
python3 -m pmoves.tools.mini_cli automations channels <channel>
```

### Tailscale Integration
```bash
# Capture a Tailnet auth key
python3 -m pmoves.tools.mini_cli tailscale authkey

# Join the tailnet
python3 -m pmoves.tools.mini_cli tailscale join

# Force re-auth join
python3 -m pmoves.tools.mini_cli tailscale rejoin
```

### Build Tools (Crush)
```bash
# Generate Crush configuration for PMOVES
python3 -m pmoves.tools.mini_cli crush setup

# Show Crush configuration details
python3 -m pmoves.tools.mini_cli crush status

# Print generated Crush configuration JSON
python3 -m pmoves.tools.mini_cli crush preview
```

## Hardware Profile Schema

Profiles describe hardware capabilities:
- **hardware**: CPU vendor/cores, GPU type/memory, RAM
- **compose_overrides**: Docker compose files to include (e.g., `docker-compose.gpu.yml`)
- **model_bundles**: Open-source models sized for the hardware
- **mcp**: MCP toolkits compatible with the profile
- **chit_scope**: Secret labels to include

Example profiles: `rtx-3090-ti`, `rtx-5090`, `jetson-orin`, `cpu-only`

## Notes
- Run from the PMOVES.AI repository root
- Requires Typer: `pip install typer[all]`
- See full spec: `docs/PMOVES_MINI_CLI_SPEC.md`
- Profiles stored in `config/profiles/*.yaml`
- MCP manifests in `config/mcp/*.yaml`
