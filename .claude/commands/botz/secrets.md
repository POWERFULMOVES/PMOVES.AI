Manage secrets using CHIT (Compressed Hierarchical Information Transfer) encoding.

CHIT provides secure encoding/decoding of environment secrets with optional encryption.

## Usage

Run this command when:
- Encoding environment secrets for secure storage
- Decoding CHIT bundles back to env format
- Sharing secrets securely between environments
- Backing up secrets in encoded format

## Arguments

- `$ARGUMENTS` - Action and options:
  - `encode` - Encode env file to CHIT bundle
  - `decode` - Decode CHIT bundle to env format

### Encode Options
- `--env-file, -e <path>` - Source env file (default: `pmoves/env.shared`)
- `--out, -o <path>` - Output CGP path (default: `pmoves/pmoves/data/chit/env.cgp.json`)
- `--no-cleartext` - Store secrets as base64 only (no plaintext)

### Decode Options
- `--cgp, -c <path>` - Input CGP file (default: `pmoves/pmoves/data/chit/env.cgp.json`)
- `--out, -o <path>` - Output decoded env file (default: `pmoves/pmoves/data/chit/env.decoded`)

## Implementation

Execute the appropriate command based on the action:

1. **Encode secrets:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli secrets encode
   ```

2. **Encode with custom paths:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli secrets encode \
     --env-file pmoves/env.local \
     --out /tmp/secrets.cgp.json
   ```

3. **Encode without cleartext:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli secrets encode --no-cleartext
   ```

4. **Decode secrets:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli secrets decode
   ```

5. **Decode with custom paths:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli secrets decode \
     --cgp /path/to/secrets.cgp.json \
     --out /tmp/decoded.env
   ```

## CHIT Format

CHIT (CGP - CHIT Geometry Protocol) bundles contain:
- Encoded key-value pairs from env files
- Optional encryption metadata
- Geometry information for hierarchical organization
- Timestamp and source tracking

## Security Notes

- **Never commit** decoded env files or CGP bundles with cleartext to git
- Use `--no-cleartext` for bundles that will be shared or stored
- CGP files are JSON format for interoperability
- CHIT encoding is NOT encryption - use proper encryption for sensitive data

## Related Commands

- `/botz:init` - Environment initialization with secrets
- `/botz:profile` - Hardware profile management
- `/health:check-all` - Verify services have required secrets

## Notes

- Source env file must exist for encoding
- Decode creates the output directory if needed
- CHIT context documentation: `.claude/context/chit-geometry-bus.md`
