# PR #489 Learnings: Archon UI Integration
**PR:** feat(archon): Add embedded UI and fix service integration
**Date:** 2026-01-15
**Reviewers:** CodeRabbit AI, Manual Review

---

## Issues Identified

### 1. CodeRabbit False Positive on python-jose
**Learning:** AI review tools may use outdated vulnerability databases.

- CodeRabbit flagged `python-jose==3.5.0` as having CVE-2024-33663 and CVE-2024-33664
- These CVEs were fixed in python-jose 3.4.0+
- Version 3.5.0 (May 2025) is already patched

**Pattern:** Always verify AI security findings against current vulnerability databases.
**Action:** Run `pip-audit --strict requirements.lock` to verify actual vulnerabilities.

---

### 2. Hardcoded Credentials Pattern
**Learning:** Default credentials should use environment variable fallbacks.

**Found:**
```yaml
# docker-compose.yml:974-975 - BAD
- CLICKHOUSE_USER=tensorzero
- CLICKHOUSE_PASSWORD=tensorzero

# Should be:
- CLICKHOUSE_USER=${CLICKHOUSE_USER:-tensorzero}
- CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD:-tensorzero}
```

**Pattern:** All credentials should support override via environment variables.
**File:** `pmoves/docker-compose.yml`

---

### 3. Weak Default Password Pattern
**Learning:** Default passwords that match username are anti-pattern.

**Found:**
```yaml
# docker-compose.yml:1371 - WEAK
- POSTGRES_PASSWORD=${INVIDIOUS_PG_PASSWORD:-kemal}
# Username is kemal, password defaults to kemal

# Better: Require explicit configuration
- POSTGRES_PASSWORD=${INVIDIOUS_PG_PASSWORD:?INVIDIOUS_PG_PASSWORD not set}
```

**Pattern:** Use `:?VAR` syntax to force explicit configuration for sensitive values.

---

### 4. Defensive Error Handling Already Present
**Learning:** CodeRabbit flagged "FileNotFoundError risk" but code was already defensive.

**Code:**
```python
if not python_src.exists():
    raise RuntimeError(
        "Archon vendor sources were not found. Expected to see "
        f"{python_src}. Ensure the upstream Archon repository is available."
    )
```

**Pattern:** Pre-checking with `exists()` before file access is the correct pattern.
**Learning:** AI tools may flag defensive programming as "risky" - review context carefully.

---

## Patterns to Adopt

### 1. Environment Variable Fallback Pattern
```yaml
# For non-sensitive defaults
- VAR_NAME=${VAR_NAME:-default_value}

# For sensitive values (no default)
- VAR_NAME=${VAR_NAME:?VAR_NAME not set}
```

### 2. Credentials Management Pattern
```bash
# env.shared - defaults for development
CLICKHOUSE_USER=tensorzero
CLICKHOUSE_PASSWORD=changeme_tensorzero_secret

# .env.local - override for production (not committed)
CLICKHOUSE_USER=prod_user
CLICKHOUSE_PASSWORD=strong_unique_password
```

### 3. Vulnerability Verification Pattern
```bash
# When AI flags a security issue:
1. Check current version vs CVE fix version
2. Run pip-audit or npm audit
3. Check GitHub Security Advisory directly
4. Verify transitive dependencies
```

---

## Files Modified
- `pmoves/services/archon/requirements.lock`
- `pmoves/services/archon/main.py`
- `pmoves/docker-compose.yml`
- `pmoves/compose/docker-compose.core.yml`

---

## Related Issues
- GHSA-6c5p-j8vq-pqhj (python-jose algorithm confusion)
- GHSA-cjwg-qfpm-7377 (python-jose JWE DoS)
