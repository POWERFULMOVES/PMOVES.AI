# Neo4j Submodule Promotion Plan

**Status:** Architectural Proposal
**Priority:** HIGH (blocking CONCH Phase 4)
**Pattern:** Follow `PMOVES-supabase` submodule structure
**Date:** 2026-03-12

---

## Problem Statement

### Current Issues
1. **Password Mismatch:** `NEO4J_AUTH` in container environment ≠ password in database
2. **No Seed Management:** Consciousness taxonomy (30KB Cypher) has no proper migration system
3. **No Schema Versioning:** Can't track consciousness schema evolution
4. **Dated Auth Pattern:** Neo4j auth doesn't follow modern seeded defaults pattern
5. **No Cross-Module Integration:** Each service manages Neo4j connection independently

### Root Cause
Neo4j is embedded in `docker-compose.yml` without dedicated submodule infrastructure. The `NEO4J_AUTH` environment variable only works for FIRST database creation. After that, the password lives in the database itself.

---

## Proposed Architecture: PMOVES-Neo4j Submodule

### Structure (Following PMOVES-Supabase Pattern)

```
PMOVES-Neo4j/
├── .claude/
│   └── CLAUDE.md                    # Submodule-specific context
├── docker/
│   ├── Dockerfile                   # Neo4j image with custom plugins
│   └── docker-compose.yml           # Standalone Neo4j stack
├── db/
│   ├── migrations/                  # Schema versioning
│   │   ├── 001_init.cypher
│   │   ├── 002_constraints.cypher
│   │   ├── 003_consciousness_taxonomy.cypher  # 30KB schema
│   │   └── ...
│   └── seeds/                       # Seed data
│       ├── 001_person_aliases.csv
│       └── 002_chit_geometry.cypher
├── scripts/
│   ├── bootstrap.sh                 # Initial setup
│   ├── migrate.sh                   # Run migrations
│   └── seed.sh                      # Load seed data
├── Makefile                         # Submodule targets
├── README.md                        # Documentation
└── chit/
    └── seeds_manifest.yaml          # Credential definitions
```

### Integration Points

**1. Parent Makefile (`pmoves/Makefile`)**
```makefile
# Neo4j submodule targets
.PHONY: neo4j-up neo4j-down neo4j-logs neo4j-migrate neo4j-seed

neo4j-up: ## Start Neo4j submodule stack
	$(MAKE) -C integrations/neo4j up

neo4j-migrate: ## Run Neo4j migrations
	$(MAKE) -C integrations/neo4j migrate

neo4j-seed: ## Load Neo4j seed data
	$(MAKE) -C integrations/neo4j seed

load-consciousness-neo4j: ## Load consciousness taxonomy (migration 003)
	$(MAKE) -C integrations/neo4j migrate VERSION=003
```

**2. Docker Compose Integration**
```yaml
# pmoves/docker-compose.yml
services:
  neo4j:
    external: true  # Use PMOVES-Neo4j submodule stack
```

**3. Credential Management (`chit/seeds_manifest.yaml`)**
```yaml
neo4j:
  credentials:
    - name: NEO4J_PASSWORD
      type: seeded_random
      length: 24
      prefix: "pm_"
      description: "Neo4j database password (auto-generated on first run)"
    - name: NEO4J_AUTH
      type: composite
      template: "neo4j/{NEO4J_PASSWORD}"
      description: "Neo4j authentication string for docker-compose"
```

---

## Migration Path

### Phase 1: Create Submodule (1 day)
1. Create `PMOVES-Neo4j` repository
2. Set up directory structure (following Supabase pattern)
3. Create Dockerfile with Neo4j 5.22 + APOC plugins
4. Add bootstrap/migrate/seed scripts
5. Document in CLAUDE.md

### Phase 2: Migrate Existing Schemas (1 day)
1. Extract current consciousness taxonomy (30KB) to `db/migrations/003_consciousness_taxonomy.cypher`
2. Extract CHIT geometry fixtures to `db/seeds/002_chit_geometry.cypher`
3. Extract person aliases seed to `db/seeds/001_person_aliases.csv`
4. Create migration versioning system

### Phase 3: Integration (2 days)
1. Add submodule to PMOVES.AI: `git submodule add ... PMOVES-Neo4j`
2. Update `pmoves/docker-compose.yml` to use external neo4j
3. Update `pmoves/Makefile` with delegate targets
4. Update `brand_defaults.py` to use seeded NEO4J_PASSWORD
5. Update `.gitmodules` configuration

### Phase 4: Credential Sync (1 day)
1. Add NEO4J_PASSWORD to `chit/seeds_manifest.yaml`
2. Update `secrets-funnel` to populate Neo4j credentials
3. Create password rotation procedure
4. Add to `push-gh-secrets.sh` whitelist

### Phase 5: Testing & Validation (1 day)
1. Test submodule bringup: `make -C integrations/neo4j up`
2. Test migration system: `make neo4j-migrate`
3. Test consciousness load: `make load-consciousness-neo4j`
4. Test credential rotation
5. Full smoke test with services that depend on Neo4j

### Phase 6: Documentation (1 day)
1. Update `CLAUDE.md` with Neo4j submodule pattern
2. Create Neo4j-specific documentation
3. Update troubleshooting guides
4. Add to integration rollup

---

## Benefits

### 1. Proper Seed Management
- Consciousness taxonomy tracked as migration `003`
- Version-controlled schema evolution
- Rollback capability

### 2. Consistent Credentials
- Seeded random password on first install
- Stored in `chit/seeds_manifest.yaml`
- Synced via `secrets-funnel` to GitHub Actions
- No more password mismatches

### 3. Cross-Module Integration
- Single source of truth for Neo4j configuration
- Consistent connection strings across all services
- Shared bootstrap/migrate/seed scripts

### 4. Development Workflow
- `make neo4j-up` → Start Neo4j stack
- `make neo4j-migrate` → Run pending migrations
- `make neo4j-seed` → Load seed data
- `make neo4j-logs` → View Neo4j logs

### 5. Production Readiness
- Migration system for schema updates
- Password rotation procedure
- Backup/restore integration
- Observability hooks (Prometheus, Grafana)

---

## Comparison: Before vs After

### Before (Current State)
```yaml
# pmoves/docker-compose.yml
services:
  neo4j:
    image: neo4j:5.22
    environment:
      NEO4J_AUTH: neo4j/pm_Fo2sRp1I_0yp5FekMt5iYg  # ❌ Baked in, wrong
    volumes:
      - pmoves_neo4jdata:/data
```

**Issues:**
- ❌ Password mismatch (env vs database)
- ❌ No migration system
- ❌ No seed management
- ❌ No schema versioning
- ❌ Hard to upgrade

### After (Proposed)
```yaml
# pmoves/docker-compose.yml
services:
  # Neo4j managed by PMOVES-Neo4j submodule
  # Use: make -C integrations/neo4j up
```

```makefile
# pmoves/Makefile
neo4j-up: ## Start Neo4j from submodule
	$(MAKE) -C integrations/neo4j up

neo4j-migrate: ## Run pending migrations
	$(MAKE) -C integrations/neo4j migrate

load-consciousness-neo4j: ## Load consciousness taxonomy (migration 003)
	$(MAKE) -C integrations/neo4j migrate VERSION=003
```

**Benefits:**
- ✅ Seeded credentials (auto-generated, synced)
- ✅ Migration system (versioned schemas)
- ✅ Seed management (consciousness taxonomy tracked)
- ✅ Schema versioning (evolution tracked)
- ✅ Easy upgrade (submodule update)

---

## Immediate Workaround (While Submodule is Created)

### Option 1: Reset Neo4j with Correct Password
```bash
# Stop Neo4j
docker stop pmoves-neo4j-1

# Remove data volume (WARNING: loses all data)
make -C pmoves volume-reset SERVICE=neo4j

# Update env.shared with fresh password from brand_defaults
make -C pmoves env-setup

# Start Neo4j (will initialize with new password)
docker compose up -d neo4j

# Load consciousness schema
make -C pmoves load-consciousness-neo4j
```

### Option 2: Reset Neo4j Password via Direct Access
```bash
# Stop Neo4j
docker stop pmoves-neo4j-1

# Start with auth disabled
docker run -d --rm \
  -v pmoves_neo4jdata:/data \
  -e NEO4J_AUTH=none \
  neo4j:5.22

# Connect and reset password
docker exec -it <container> cypher-shell
# Cypher: ALTER USER neo4j SET PASSWORD 'new_password';

# Stop and restart with auth enabled
# Update env.shared with new password
```

### Option 3: Create Password Reset Script
```bash
# pmoves/tools/reset_neo4j_password.sh
#!/bin/bash
NEW_PASSWORD="pm_$(openssl rand -hex 16)"
docker exec pmoves-neo4j-1 cypher-shell -u neo4j -p oldpassword \
  "ALTER USER neo4j SET PASSWORD '$NEW_PASSWORD';"
echo "NEO4J_AUTH=neo4j/$NEW_PASSWORD" >> pmoves/env.shared
```

---

## Success Criteria

- [ ] Submodule `PMOVES-Neo4j` created
- [ ] Consciousness taxonomy tracked as migration `003`
- [ ] `make neo4j-up` starts Neo4j stack
- [ ] `make neo4j-migrate` runs migrations
- [ ] `make load-consciousness-neo4j` loads taxonomy
- [ ] Credentials seeded via `brand_defaults.py`
- [ ] Credentials synced via `secrets-funnel`
- [ ] All existing Neo4j-dependent services work
- [ ] Documentation updated in `CLAUDE.md`

---

## Next Steps

1. **Create Issue:** "Promote Neo4j to First-Class Submodule"
2. **Create Branch:** `feat/neo4j-submodule-promotion`
3. **Execute Phases 1-6** (6-7 days total)
4. **PR:** Merge to main
5. **Cascade:** Update PMOVES.AI-Edition-Hardened

---

**Proposed By:** Claude Sonnet 4.6
**Date:** 2026-03-12
**Related:** Runtime Validation + CONCH Pipeline Execution (Phase 4 blocked on Neo4j auth)
