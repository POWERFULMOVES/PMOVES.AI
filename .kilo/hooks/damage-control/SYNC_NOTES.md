# Pattern Synchronization Notes

**Last Sync:** 2026-07-14  
**Source:** `.claude/hooks/damage-control/patterns.yaml`  
**Target:** `.kilo/hooks/damage-control/patterns.yaml`

---

## Pattern Count Comparison

| Category | Claude Code | KiloCode | Notes |
|----------|-------------|----------|-------|
| Total patterns | 121 | 92 | KiloCode subset focuses on critical security patterns |
| bashToolPatterns | ~85 | ~65 | Core destructive operations + PMOVES-specific |
| zeroAccessPaths | ~50 | ~50 | Fully synchronized (secrets/credentials) |
| chitBypassPatterns | ~50 | ~50 | Fully synchronized (CHIT security tools) |
| chitSafePaths | ~30 | ~30 | Fully synchronized (CHIT operations) |
| readOnlyPaths | ~40 | ~40 | Fully synchronized (system/build artifacts) |
| noDeletePaths | ~30 | ~30 | Fully synchronized (critical project files) |

---

## Included Pattern Categories

### Destructive Operations (Core Security)
- ✅ File operations (`rm -rf`, `sudo rm`)
- ✅ Permission changes (`chmod 777`, `chown root`)
- ✅ Git operations (`reset --hard`, `push --force`, `clean -fd`)
- ✅ System destruction (`mkfs`, `dd of=/dev/`)
- ✅ Process destruction (`kill -9 -1`, `killall`)
- ✅ History manipulation (`history -c`)

### Cloud Provider Operations
- ✅ AWS CLI (`s3 rm --recursive`, `ec2 terminate-instances`, `rds delete-db-instance`)
- ✅ GCP (`gcloud projects delete`, `compute instances delete`, `storage rm -r`)
- ⚠️  Firebase, Vercel, Netlify, Cloudflare (omitted — not used by PMOVES)
- ⚠️  Heroku, Fly.io, DigitalOcean (omitted — not used by PMOVES)

### Infrastructure & Orchestration
- ✅ Docker (`system prune -a`, `volume rm`, `rmi -f`, container sweeps)
- ✅ Kubernetes (`delete namespace`, `delete all --all`, `helm uninstall`)
- ✅ Database CLI (`redis-cli FLUSHALL`, `dropdb`, MongoDB `dropDatabase`)
- ✅ IaC (`terraform destroy`, `pulumi destroy`, `serverless remove`)

### Development Tools
- ✅ GitHub CLI (`gh repo delete`, `gh workflow run`)
- ⚠️  NPM registry (`npm unpublish`) — omitted, not a PMOVES risk vector

### SQL Operations
- ✅ Catastrophic (`DELETE FROM` without WHERE, `TRUNCATE`, `DROP TABLE/DATABASE`)
- ✅ Ask-mode (`DELETE FROM ... WHERE id=...`)

### PMOVES-Specific
- ✅ Docker Compose operations (`down -v`, `prune -a`, `rm -f`)
- ✅ NATS JetStream (`stream purge --all`, `stream delete`, `kv purge`)
- ✅ Git submodules (`update --recursive`, `deinit`)
- ✅ Pipeline bypass detection (`docker compose up -d`, `docker compose restart`)
- ✅ Tailscale IP leakage prevention (real IPs, LAN IPs)
- ✅ Secrets funnel confirmation (`make secrets-funnel`)

### Access Control Lists (Fully Synchronized)
- ✅ **zeroAccessPaths** — Secrets, credentials, SSH keys, cloud config, env files
- ✅ **chitBypassPatterns** — CHIT tools, secrets pipeline, infrastructure scripts
- ✅ **chitSafePaths** — CHIT artifacts, compose overlays, integration configs
- ✅ **bashDeleteAllowlist** — Git lockfile cleanup only
- ✅ **readOnlyPaths** — System dirs, shell config, lock files, build artifacts
- ✅ **noDeletePaths** — KiloCode config, license, docs, git, CI/CD, Docker

---

## Omitted Patterns (Not PMOVES Risk Vectors)

These patterns exist in Claude Code but were omitted from KiloCode as they don't apply to PMOVES infrastructure:

1. **Firebase** (3 patterns) — PMOVES uses Supabase, not Firebase
2. **Vercel** (3 patterns) — Not used
3. **Netlify** (2 patterns) — Not used
4. **Cloudflare Wrangler** (5 patterns) — PMOVES uses raw Cloudflare API, not Wrangler CLI
5. **Heroku** (2 patterns) — Not used
6. **Fly.io** (2 patterns) — Not used
7. **DigitalOcean** (2 patterns) — PMOVES uses Hostinger KVMs, not DO
8. **NPM Registry** (1 pattern) — Not a PMOVES publish target

**Total omitted:** ~20 patterns

**Rationale:** Keep KiloCode patterns focused on PMOVES-relevant operations. If we add Firebase/Vercel/etc. in the future, sync those patterns at that time.

---

## PMOVES-Specific Enhancements

These patterns are PMOVES-specific and appear in both Claude Code and KiloCode:

1. **Docker Compose Pipeline Bypass** (3 patterns)
   - Enforces `make -C pmoves up-<service>` instead of raw `docker compose up -d`
   - Ensures COMPOSE_ENV_FILES injection from secrets-funnel

2. **Docker Volume Management** (2 patterns)
   - Enforces `make -C pmoves volume-reset SERVICE=<name>` instead of raw `docker volume rm`
   - Prevents indiscriminate `docker volume prune`

3. **Tailscale IP Leakage** (2 patterns)
   - Blocks committing real Tailscale IPs (100.64-127.x.x)
   - Blocks committing LAN IPs (192.168.x.x)
   - Guides to use hostnames (pmoves-z890, pmoves-5090)

4. **NATS JetStream Operations** (3 patterns, ask-mode)
   - Confirms `nats stream purge --all`
   - Confirms `nats kv purge --all`
   - Confirms `nats stream delete`

5. **Git Submodule Operations** (2 patterns, ask-mode)
   - Confirms `git submodule update --recursive` (updates all 50+ submodules)
   - Confirms `git submodule deinit` (removes submodule)

6. **Secrets Funnel** (1 pattern, ask-mode)
   - Confirms `make secrets-funnel` (regenerates tier env files from CHIT source)

7. **GitHub Workflow Trigger** (1 pattern, ask-mode)
   - Confirms `gh workflow run` (triggers CI/CD)

8. **Host Network Configuration** (1 pattern, ask-mode)
   - Enforces `make -C pmoves z890-host-setup` instead of raw `netsh interface portproxy`

9. **Direct Database Access** (2 patterns, ask-mode)
   - Warns against `psql` (bypasses Supabase RLS + PostgREST)
   - Warns against `clickhouse-client` (bypasses TensorZero observability layer)

---

## CHIT Security Integration

The CHIT bypass patterns allow trusted PMOVES infrastructure tools to access secrets while still blocking destructive operations:

### Allowed CHIT Operations
- `pmoves/tools/chit_*` — CHIT encoding/decoding/security tools
- `pmoves/tools/secrets_sync` — Secrets pipeline orchestration
- `pmoves/tools/secrets_local_hydrate` — Local secrets bootstrap
- `make secrets-funnel` — Canonical secrets propagation path
- `git add/diff/status/log secrets_manifest` — Git operations on CHIT manifests
- `z890_host_setup`, `laptop_4090_host_harden` — Infrastructure hardening scripts
- `pmoves_cipher` — Cipher Memory operations (Neo4j-backed, not filesystem secrets)

### Still Blocked (Even for CHIT Tools)
- `rm -rf`, `rm -f` — Destructive file operations
- `git push --force` — Force pushes
- `DROP DATABASE`, `DELETE FROM` without WHERE — Catastrophic SQL

**Design principle:** CHIT tools can READ/WRITE env files for encoding/rotation, but destructive filesystem/git/SQL operations remain blocked.

---

## Known Roads Enforcement

Many PMOVES operations have "Known Roads" — canonical Make targets that handle the full lifecycle (stop → operation → restart, env injection, health verification). Patterns detect raw command usage and guide the agent to the correct path:

| Raw Command | Known Road | Make Target |
|-------------|-----------|-------------|
| `docker system prune -a` | Safe cleanup | `make -C pmoves docker-prune` or `docker-prune-all` |
| `docker volume rm <vol>` | Service-aware reset | `make -C pmoves volume-reset SERVICE=<name>` |
| `docker compose up -d` | Env injection | `make -C pmoves up-<service>` |
| `docker compose restart` | Fresh env | `make -C pmoves up-<service>` (recreates containers) |
| `netsh interface portproxy` | Host networking | `make -C pmoves z890-host-setup` |
| Raw `psql`/`clickhouse-client` | API layer | Use Supabase REST/TensorZero API |

Each Known Road pattern includes:
1. **KNOWN ROADS BYPASS** — Explains what the raw command bypasses
2. **Correct path** — The Make target or skill to use
3. **INTEGRITY CHECK** — Adversarial detection guidance
4. **ACTION** — What the agent should do (report suspected bypass)

---

## Synchronization Checklist

When syncing patterns from Claude Code:

- [ ] Run `diff .claude/hooks/damage-control/patterns.yaml .kilo/hooks/damage-control/patterns.yaml`
- [ ] Review changes for PMOVES-relevance (omit Firebase/Vercel/etc. if still not used)
- [ ] Copy updated sections to `.kilo/hooks/damage-control/patterns.yaml`
- [ ] Update "Last sync" comment at top of patterns.yaml
- [ ] Update this SYNC_NOTES.md with pattern count and new categories
- [ ] Run `make -C pmoves kilo-parity-check` (should pass with 0 gaps, 1 blocked item)
- [ ] Commit with sync note: `chore(kilocode): sync damage-control patterns (YYYY-MM-DD)`

---

## References

- **Claude Code patterns:** `.claude/hooks/damage-control/patterns.yaml` (1243 lines, 121 patterns)
- **KiloCode patterns:** `.kilo/hooks/damage-control/patterns.yaml` (801 lines, 92 patterns)
- **Known Roads:** `pmoves/mk/infra.mk`, `pmoves/mk/codex.mk`, `pmoves/Makefile`
- **CHIT security:** `pmoves/docs/security/CHIT_INTEGRATION_STATUS.md`
- **Issue:** #2120 — feat(kilocode): damage-control hooks for KiloCode GLM
