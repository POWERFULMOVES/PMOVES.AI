Run the PMOVES Mini CLI onboarding helper to check or generate environment configuration.

This command helps with initial setup and verification of your PMOVES environment.

## Usage

Run this command when:
- Setting up PMOVES for the first time
- Verifying environment configuration status
- Regenerating env files after changes

## Arguments

- `$ARGUMENTS` - Optional flags:
  - `--generate` or `-g`: Generate env files instead of just showing status
  - `--manifest <path>`: Override the secrets manifest path

## Implementation

Execute the following steps:

1. **Check status (default):**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli init
   ```

2. **Generate environment files:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli init --generate
   ```

3. **With custom manifest:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli init --manifest /path/to/manifest.yaml
   ```

## What It Does

- **Status mode** (default): Reports which secrets are configured vs missing
- **Generate mode**: Creates/updates env files based on the secrets manifest
- Uses `pmoves/chit/secrets_manifest.yaml` as the default manifest

## Related Commands

- `/botz:profile` - Hardware profile management
- `/botz:secrets` - CHIT encode/decode operations
- `/botz:mcp` - MCP toolkit verification

## Notes

- The Mini CLI requires Typer (`pip install typer[all]`)
- Run from the PMOVES.AI repository root
- Environment files are written to `pmoves/env.shared` and related locations
