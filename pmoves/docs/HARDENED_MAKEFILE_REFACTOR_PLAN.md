# Hardened Makefile Refactor Plan

This document outlines the refactoring checklist for the PMOVES.AI Makefile to align with production hardened requirements.

## Overview

The Makefile is the primary interface for PMOVES.AI operations. This plan ensures:
- All commands work in production hardened environment
- No services are marked as "optional"
- Proper dependency management
- Consistent naming and organization
- Complete documentation

## Refactoring Checklist

### Phase 1: Organization & Naming

- [ ] Targets grouped by functionality (network, ports, secrets, etc.)
- [ ] Consistent target naming (verb-noun format)
- [ ] PHONY declarations for all non-file targets
- [ ] Help target lists all available commands
- [ ] Target descriptions follow format: `## Description`

### Phase 2: Network & Discovery

- [ ] `mesh-setup` - Tailscale mesh configuration
- [ ] `mesh-status` - Show mesh network status
- [ ] `mesh-disconnect` - Disconnect from mesh
- [ ] `nats-tls-setup` - Generate NATS TLS certificates
- [ ] `registry-start` - Start service registry
- [ ] `registry-status` - Show discovered services
- [ ] `registry-sync` - Force sync across mesh

### Phase 3: Port Management

- [ ] `ports-auto-detect` - Auto-detect port conflicts
- [ ] `ports-validate` - Check for port conflicts
- [ ] `ports-reset` - Reset port assignments
- [ ] `ports-show` - Show current assignments

### Phase 4: Secrets Management

- [ ] `secrets-setup-wizard` - Interactive secrets wizard
- [ ] `secrets-validate` - Validate all secrets
- [ ] `secrets-chit-encode` - Encode to CHIT format
- [ ] `secrets-chit-decode` - Decode from CHIT format
- [ ] `secrets-show` - Show loaded secrets
- [ ] `secrets-import` - Import from YAML file

### Phase 5: Service Lifecycle

- [ ] `up` - Start all services (required)
- [ ] `up-agents` - Start agent services (required)
- [ ] `up-workers` - Start worker services (required)
- [ ] `down` - Stop all services
- [ ] `restart` - Restart all services
- [ ] `ps` - Show service status
- [ ] `logs` - Show service logs

### Phase 6: Database & Data

- [ ] `supa-start` - Start Supabase (required)
- [ ] `supa-stop` - Stop Supabase
- [ ] `supa-status` - Check Supabase status
- [ ] `supa-migrate` - Run migrations
- [ ] `bootstrap-data` - Bootstrap initial data
- [ ] `a0-mcp-seed` - Seed Agent Zero MCP tools

### Phase 7: Observability

- [ ] `health` - Quick health check
- [ ] `metrics` - Show Prometheus metrics
- [ ] `logs` - Show aggregated logs
- [ ] `dashboard` - Open Grafana dashboard

### Phase 8: Testing & Validation

- [ ] `test` - Run all tests
- [ ] `test-smoke` - Run smoke tests
- [ ] `test-unit` - Run unit tests
- [ ] `test-integration` - Run integration tests
- [ ] `verify-all` - Run full verification

### Phase 9: Development

- [ ] `dev` - Start development environment
- [ ] `dev-watch` - Start with hot reload
- [ ] `build` - Build all services
- [ ] `clean` - Clean build artifacts
- [ ] `deep-clean` - Remove all generated files

### Phase 10: First-Run & Onboarding

- [ ] `check-tools` - Verify required tools
- [ ] `ensure-env-shared` - Create env.shared if missing
- [ ] `first-run` - Interactive first-run setup
- [ ] `first-run-multi-host` - Multi-host first-run

## Completed Items

The following have been completed in recent refactoring:

### Multi-Host Discovery (Phase 1)
- ✅ `mesh-setup` - Tailscale mesh configuration
- ✅ `mesh-status` - Show mesh network status
- ✅ `mesh-disconnect` - Disconnect from mesh
- ✅ `nats-tls-setup` - Generate NATS TLS certificates
- ✅ `registry-start` - Start service registry
- ✅ `registry-status` - Show discovered services
- ✅ `registry-sync` - Force sync across mesh

### Port Management (Phase 2)
- ✅ `ports-auto-detect` - Auto-detect port conflicts
- ✅ `ports-validate` - Check for port conflicts
- ✅ `ports-reset` - Reset port assignments
- ✅ `ports-show` - Show current assignments

## Pending Items

The following need to be implemented:

### Secrets Management (Phase 3)
- ⏳ `secrets-setup-wizard` - Interactive wizard (requires Python script)
- ⏳ `secrets-validate` - Validate all secrets
- ⏳ `secrets-show` - Show loaded secrets
- ⏳ `secrets-import` - Import from YAML file
- ✅ `secrets-chit-encode` - Already exists via CHIT module
- ✅ `secrets-chit-decode` - Already exists via CHIT module

### First-Run Enhancement
- ⏳ Update `first-run` to include all new phases
- ✅ `first-run-multi-host` - Already created

## Implementation Notes

### Adding New Targets

When adding new targets:

1. **Add to PHONY declaration**
   ```makefile
   .PHONY: target-name
   ```

2. **Use consistent naming**
   - verb-noun format: `ports-validate`, `mesh-setup`
   - Lowercase with hyphens

3. **Add description comment**
   ```makefile
   target-name: ## Description for help target
   ```

4. **Use proper dependencies**
   ```makefile
   target-name: ## Description
       @$(MAKE) --no-print-directory dependency
       @echo "Action..."
   ```

5. **Group related targets**
   ```makefile
   # ============================================================================
   # Group Name
   # ============================================================================
   ```

### Target Best Practices

1. **Echo what's happening**
   ```makefile
   @echo "🔍 Checking..."
   ```

2. **Use --no-print-directory** for nested calls
   ```makefile
   @$(MAKE) --no-print-directory target
   ```

3. **Check prerequisites**
   ```makefile
   check-tools:
       @command -v docker >/dev/null || echo "Docker not found"
   ```

4. **Handle errors gracefully**
   ```makefile
   target:
       @command || echo "⚠️  Warning"
   ```

## Validation

After refactoring, validate:

1. **All targets have PHONY**
   ```bash
   grep -E "^[a-z-]+:" Makefile | while read target; do
       name=$(echo $target | cut -d: -f1)
       grep -q "\.PHONY.*$name" Makefile || echo "Missing PHONY: $name"
   done
   ```

2. **Help target is complete**
   ```bash
   make help | grep -c "##"  # Should match number of targets
   ```

3. **No "optional" services**
   ```bash
   grep -i optional Makefile  # Should return nothing
   ```

4. **All documentation exists**
   ```bash
   # Check that each documented service exists
   ```

## See Also

- `docs/MODULAR_ARCHITECTURE.md` - Service architecture
- `docs/MULTI_HOST_DISCOVERY.md` - Multi-host setup
- `docs/DYNAMIC_PORTS_GUIDE.md` - Port management
- `pmoves/Makefile` - Makefile implementation
