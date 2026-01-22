# PMOVES.AI CHIT User Guide

**CHIT** (Compressed Hierarchical Information Transfer) is PMOVES.AI's secure encoding format for secrets, configuration, and structured data.

## What is CHIT?

CHIT provides:
- **Compression**: Reduces storage size by ~60%
- **Encryption**: AES-256 encryption for sensitive data
- **Integrity**: HMAC verification to detect tampering
- **Portability**: Single file for backup/transfer

## Quick Start

### Encode Secrets

```bash
# Encode from YAML
make secrets-chit-encode < user_keys.yaml > secrets.chit

# With password protection
make secrets-chit-encode --password < user_keys.yaml > secrets.chit

# From environment variables
make secrets-chit-encode --env > secrets.chit
```

### Decode Secrets

```bash
# Decode to YAML
make secrets-chit-decode < secrets.chit > user_keys.yaml

# With password
make secrets-chit-decode --password < secrets.chit > user_keys.yaml

# View without saving
make secrets-chit-decode < secrets.chit | less
```

## Advanced Usage

### CHIT Commands

| Command | Description |
|---------|-------------|
| `make secrets-chit-encode` | Encode secrets to CHIT format |
| `make secrets-chit-decode` | Decode CHIT to YAML |
| `chit validate <file.chit>` | Validate CHIT integrity |
| `chit info <file.chit>` | Show CHIT metadata |
| `chit encrypt <file>` | Encrypt any file to CHIT |
| `chit decrypt <file.chit>` | Decrypt CHIT to original |

### Python API

```python
from pmoves.chit import encode_chit, decode_chit

# Encode
data = {"api_key": "sk-...", "secret": "value"}
chit_data = encode_chit(data, password="optional")

# Decode
decoded = decode_chit(chit_data, password="optional")
```

## CHIT File Format

A CHIT file contains:
1. **Header**: Magic bytes, version, compression type
2. **Metadata**: Creation time, format type, optional labels
3. **Payload**: Compressed and optionally encrypted data
4. **Signature**: HMAC for integrity verification

```
CHIT File Structure:
┌─────────────────────────────────────┐
│ Magic: "CHIT" (4 bytes)             │
│ Version: 1 (1 byte)                 │
│ Flags: encryption, compression (1)  │
│ Metadata Length: (2 bytes)          │
│ Metadata: JSON                      │
│ Payload Length: (4 bytes)           │
│ Payload: (compressed/encrypted)     │
│ HMAC-SHA256: (32 bytes)             │
└─────────────────────────────────────┘
```

## Use Cases

### 1. Backup Secrets

```bash
# Create encrypted backup
make secrets-chit-encode --password < user_keys.yaml > backup-$(date +%Y%m%d).chit

# List backups
ls -lh backups/*.chit

# Restore from backup
make secrets-chit-decode --password < backup-20250118.chit > user_keys.yaml
```

### 2. Transfer Between Machines

```bash
# On source machine
make secrets-chit-encode < user_keys.yaml > secrets.chit

# Transfer (safe to copy, email, or store in cloud)
scp secrets.chit target-machine:/path/to/pmoves/

# On target machine
make secrets-chit-decode < secrets.chit > user_keys.yaml
```

### 3. Version Control (Encrypted)

```bash
# Commit encrypted secrets to git
make secrets-chit-encode --password < user_keys.yaml > secrets.chit
git add secrets.chit
git commit -m "Add encrypted secrets backup"

# Safe to push to private repo
git push origin main
```

### 4. Docker Secrets

```bash
# Create CHIT for Docker
make secrets-chit-encode < user_keys.yaml > secrets.chit

# Use in docker-compose
docker secret create pmoves-secrets < secrets.chit
```

## Security

### Encryption

CHIT uses **AES-256-GCM** for encryption when a password is provided:
- 256-bit key derived from password (PBKDF2, 100,000 iterations)
- 96-bit nonce for unique encryption
- Authenticated encryption (AEAD) for tamper detection

### Password Guidelines

- Minimum 12 characters
- Mix of upper/lower case, numbers, symbols
- Use a password manager
- Don't reuse passwords

### Key Management

Best practices:
1. Store CHIT password in secure location (KeePassXC, 1Password)
2. Don't commit password to git
3. Rotate passwords periodically
4. Use different passwords for different CHIT files

## Troubleshooting

### "Invalid CHIT format"

**Cause**: File is corrupted or not a CHIT file

**Solution**:
```bash
# Validate file
chit validate secrets.chit

# Check file type
file secrets.chit
```

### "Decryption failed"

**Cause**: Wrong password or corrupted file

**Solution**:
- Verify password is correct
- Check HMAC signature: `chit info secrets.chit`
- Restore from backup if available

### "HMAC verification failed"

**Cause**: File has been tampered with or corrupted

**Solution**:
- File integrity compromised
- Do NOT use the file
- Restore from trusted backup

## Examples

### Example 1: Quick Backup

```bash
# One-line backup with timestamp
make secrets-chit-encode < user_keys.yaml > backups/secrets-$(date +%Y%m%d-%H%M).chit
```

### Example 2: Multi-Environment

```bash
# Development
make secrets-chit-encode < dev_keys.yaml > dev.chit

# Staging
make secrets-chit-encode < staging_keys.yaml > staging.chit

# Production
make secrets-chit-encode --password < prod_keys.yaml > prod.chit
```

### Example 3: Partial Secrets

```bash
# Extract specific keys
make secrets-chit-decode < secrets.chit | grep -E "OPENAI|ANTHROPIC" > llm_keys.yaml
```

## CHIT vs Alternatives

| Format | Compression | Encryption | Verification | PMOVES Support |
|--------|-------------|------------|--------------|----------------|
| **CHIT** | ✅ Native | ✅ AES-256 | ✅ HMAC | ✅ Built-in |
| JSON | ❌ | ❌ | ❌ | ✅ |
| YAML | ❌ | ❌ | ❌ | ✅ |
| ENV | ❌ | ❌ | ❌ | ✅ |
| SOPS | ❌ | ✅ GPG/KMS | ✅ | ❌ External |
| Git-crypt | ❌ | ✅ GPG | ✅ | ❌ External |

## API Reference

### encode_chit()

```python
encode_chit(
    data: Union[dict, str, bytes],
    password: Optional[str] = None,
    compression: Literal["gzip", "zlib", "none"] = "gzip",
    labels: Optional[Dict[str, str]] = None
) -> bytes
```

### decode_chit()

```python
decode_chit(
    data: bytes,
    password: Optional[str] = None
) -> Union[dict, str, bytes]
```

## See Also

- `docs/SECRETS_ONBOARDING.md` - General secrets setup
- `pmoves/chit/__init__.py` - CHIT implementation
- `docs/GEOMETRY_BUS_INTEGRATION.md` - CHIT for geometry data
