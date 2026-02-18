# Submodule Fork Architecture

**Canonical reference for the PMOVES.AI vendor-to-fork migration and integration overlay pattern.**

## Overview

PMOVES.AI maintains a dual-path submodule registry. All submodule repos are POWERFULMOVES-owned forks hosted under the `POWERFULMOVES` GitHub org. Many were originally registered under `pmoves/vendor/` or `research/` paths and have been promoted to canonical top-level paths. Each fork:

1. **Stays synced** with its upstream source via periodic merges to `main`
2. **Adds PMOVES.AI integration overlays** — service provisions, NATS event hooks, security hardening, Docker Compose profiles, and cross-service wiring
3. **Tracks the `PMOVES.AI-Edition-Hardened` branch** for production stability
4. **Preserves the legacy vendor/research path** during the migration period for backward compatibility

## Contribution Flow

```
Upstream (vendor)
    │
    ▼
PMOVES Fork (PMOVES.AI-Edition-Hardened branch)
    │
    ├── Upstream sync merges (vendor → fork)
    ├── PMOVES.AI integration overlays (unique to fork)
    ├── Security hardening & Docker profiles
    └── Cross-service wiring (NATS, Supabase, MinIO)
    │
    ▼
PMOVES.AI parent repo (gitlink pointer)
    ├── Top-level path: PMOVES-<name>/       (canonical)
    └── Legacy path:    pmoves/vendor/<name>/ (kept until migration complete)
```

### Upstream Sync

Forks pull changes from upstream via:
```bash
# Inside the fork repo
git remote add upstream <original-repo-url>
git fetch upstream
git merge upstream/main --no-edit
```

### PMOVES.AI Contributions

Enhancements go to the fork's `PMOVES.AI-Edition-Hardened` branch. When applicable, improvements are contributed back upstream via PRs to the original repo.

## Fork Registry

### E2B Ecosystem

| Fork (Canonical Path) | Vendor (Legacy Path) | Integration Overlays |
|---|---|---|
| `PMOVES-E2B-Danger-Room/` | — | NATS sandbox events, security hardening, PMOVES agent provisioning |
| `PMOVES-E2B-Danger-Room-Desktop/` | `pmoves/vendor/e2b-desktop/` | Desktop sandbox integration, Agent Zero MCP bridge |
| `PMOVES-Danger-infra/` | `pmoves/vendor/e2b-infra/` | PMOVES infrastructure provisioning, Tailscale mesh overlay |
| `PMOVES-E2b-Spells/` | `pmoves/vendor/e2b-spells/` | PMOVES spell templates, custom sandbox recipes |
| `pmoves-e2b-mcp-server/` | `pmoves/vendor/e2b-mcp-server/` | Extended MCP tools, PMOVES auth integration |
| `PMOVES-surf/` + `pmoves-surf/` | `pmoves/vendor/e2b-surf/` | Browser automation enhancements, PMOVES session management |

### Agent Training

| Fork (Canonical Path) | Vendor (Legacy Path) | Integration Overlays |
|---|---|---|
| `PMOVES-AgentGym/` | `pmoves/vendor/agentgym/` | PMOVES environment configs, Agent Zero training pipelines |
| `Pmoves-AgentGym-RL/` | `pmoves/vendor/agentgym-rl/` | RL reward shaping for PMOVES tasks, evaluation harness |

### Research

| Fork (Canonical Path) | Legacy Path | Integration Overlays |
|---|---|---|
| `PMOVES-A2UI/` | `research/A2UI/` | A2UI research prototype, PMOVES UI generation |

### Multi-Mount (Same Repo, Different Integration Context)

| Fork Path | Integration Mount | Same Repo | Purpose |
|---|---|---|---|
| `PMOVES-Archon/` | `pmoves/integrations/archon/` | Yes | Agent service (top-level) vs integration context (mounted for cross-service wiring) |
| `PMOVES-surf/` | `pmoves-surf/` | Yes | Top-level reference vs integration-ready path |

## Legacy Vendor Path Migration

The `pmoves/vendor/` and `research/` paths are kept active during the transition:

```gitmodules
# .gitmodules comment:
# Keep these active until the legacy vendor/research paths are fully removed.
```

**Migration status:**
- Vendor paths point to the **same fork repos** as top-level paths (not upstream)
- Both paths track `PMOVES.AI-Edition-Hardened`
- Legacy paths will be removed once all references (Docker Compose, CI, imports) are updated to use canonical top-level paths

### Identifying Legacy References

Search for vendor path usage that needs migration:
```bash
# Find references to legacy vendor paths
grep -r "pmoves/vendor/" docker-compose*.yml Makefile .github/ pmoves/services/
grep -r "research/A2UI" docker-compose*.yml Makefile .github/
```

## Integration Overlay Standard

Each fork SHOULD contain a `PMOVES_INTEGRATION.md` in its root documenting:

1. **Upstream source** — Original repo URL and sync branch
2. **PMOVES.AI provisions** — What was added/modified beyond upstream
3. **Service dependencies** — Which PMOVES.AI services this fork connects to
4. **NATS subjects** — Event subjects published or consumed
5. **Docker Compose profile** — Which profile(s) include this service
6. **Cross-links** — Links to:
   - Parent repo context: `PMOVES.AI/.claude/context/submodules.md`
   - Service catalog: `PMOVES.AI/.claude/context/services-catalog.md`
   - Integration docs: `PMOVES.AI/pmoves/docs/SUBMODULE_FORK_ARCHITECTURE.md` (this file)
   - Related forks that share the upstream

### Template

```markdown
# PMOVES.AI Integration — <Fork Name>

## Upstream
- **Source:** <upstream-repo-url>
- **Sync branch:** main → PMOVES.AI-Edition-Hardened (periodic merge)
- **Last sync:** <date>

## PMOVES.AI Provisions
- <List what was added/modified>

## Service Dependencies
- <List PMOVES.AI services this connects to>

## NATS Subjects
| Subject | Direction | Description |
|---|---|---|
| `<subject>` | publish/subscribe | <what it does> |

## Docker Compose
- **Profile:** `<profile-name>`
- **Port(s):** `<port>`

## Cross-Links
- [Submodule Catalog](https://github.com/POWERFULMOVES/PMOVES.AI/blob/PMOVES.AI-Edition-Hardened/.claude/context/submodules.md)
- [Fork Architecture](https://github.com/POWERFULMOVES/PMOVES.AI/blob/PMOVES.AI-Edition-Hardened/pmoves/docs/SUBMODULE_FORK_ARCHITECTURE.md)
- [Services Catalog](https://github.com/POWERFULMOVES/PMOVES.AI/blob/PMOVES.AI-Edition-Hardened/.claude/context/services-catalog.md)
```

## Branch Strategy

All forks follow the same branch model:

| Branch | Purpose |
|---|---|
| `main` | Upstream sync target — merges from vendor |
| `PMOVES.AI-Edition-Hardened` | Production branch — upstream + PMOVES overlays + security hardening |
| `codex/*` | Codex-generated integration work |
| `feat/*` | Feature branches for PMOVES-specific work |

The parent repo's `.gitmodules` tracks `PMOVES.AI-Edition-Hardened` for all submodules. Gitlink pointers are updated when the Hardened branch advances.

## Search Traversal

To find how a fork integrates with PMOVES.AI:

1. **Start at the fork** — Read `PMOVES_INTEGRATION.md` (if present) or the fork's README
2. **Check parent context** — `.claude/context/submodules.md` has the full catalog with ports, profiles, and integration points
3. **Check service catalog** — `.claude/context/services-catalog.md` maps ports to services
4. **Check NATS subjects** — `.claude/context/nats-subjects.md` shows event wiring
5. **Check Docker Compose** — `docker-compose.yml` shows service definitions, profiles, and dependencies
6. **Check this document** — Fork registry table shows vendor↔fork mapping and overlay summary

## See Also

- [Submodule Catalog](../.claude/../.claude/context/submodules.md) — Full submodule reference
- [Services Catalog](../.claude/../.claude/context/services-catalog.md) — Port allocations and service details
- [NATS Subjects](../.claude/../.claude/context/nats-subjects.md) — Event bus documentation
- [CLAUDE.md](../../.claude/CLAUDE.md) — Main developer context
