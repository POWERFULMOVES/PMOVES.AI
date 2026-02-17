# Branch Consolidation & Security Audit Learnings — February 2026

**Session date:** 2026-02-16
**PRs reviewed/merged:** #633, #634, #640, #641, #642, #643, #644, #645, #646
**Submodule audited:** PMOVES-transcribe-and-fetch

---

## Pattern 1: DoX Branch Reset (386-commit divergence)

When a feature branch diverges by hundreds of commits from its base:

1. Close the existing PR
2. Create a backup branch (`dox-backup-YYYYMMDD`)
3. Reset the feature branch to base tip
4. Cherry-pick only the functional commits (not merge commits)
5. Force-push with `--force-with-lease`
6. Open a new PR

**Applied to:** Agent Zero DoX branch — PR #4 closed, PR #5 created with Hardened + 3 DoX commits.

## Pattern 2: Dependency-Ordered PR Merging

When PRs have implicit dependencies (e.g., one adds Make targets that another's docs reference):

- Merge the **target PR first** (the one that adds infrastructure)
- Then merge the **doc/reference PR** (reviewer comments about "target doesn't exist" resolve naturally)

**Applied to:** #643 (submodule sync targets) merged before #641 (branch strategy docs).

## Pattern 3: CodeQL Fix Patterns

### Path injection allowlisting
When CodeQL flags path variables as "user-controlled":
- Use allowlist regex validation: `if not re.match(r'^[a-zA-Z0-9_\-/.]+$', user_path): raise ValueError`
- Never concatenate unvalidated paths into shell commands

### URL sanitization (XSS via img.src)
- Validate URL scheme before setting `img.src`: only allow `http://`, `https://`, `data:image/`
- Reject `javascript:`, `vbscript:`, and other executable schemes
- **Commit:** `9c3a58a0` — `fix(security): sanitize avatar URL to prevent XSS via img.src`

## Pattern 4: GitHub Actions CI Patterns

### Self-hosted runners need sudo
- `[self-hosted, ai-lab]` runners are non-root
- `apt-get install` requires `sudo` prefix
- **Fix:** PR #646 added `sudo` to ripgrep install in chit-contract verify

### Recursive submodule checkout fails on private repos
- `submodules: recursive` in `actions/checkout` fails silently if a submodule is private
- Need PAT or deploy keys for private submodule access
- **Affected:** `PMOVES-transcribe-and-fetch` is private

### GitHub Actions env blocks
- `env:` blocks cannot self-reference other vars defined at the same level
- `secrets` context not available in step-level `if:` — use job-level or env vars

## Pattern 5: transcribe-and-fetch Security Audit Findings

### CRITICAL (3)
1. **Real Supabase JWT in .env.example** — committed service-role key with 2124-year expiry
2. **Real credentials in monitoring/*.env** — Langfuse, MinIO passwords in tracked files
3. **Hardcoded local paths** — `c:/Users/russe/...` in 6 files (PII exposure)

### HIGH (6)
1. **Auth bypass (fail-open)** — `verify_token()` returns anonymous on missing JWT secret
2. **Default passwords** — `admin123`, `langfuse123`, `redis123` in docker-compose
3. **RLS policies wide-open** — `USING (true) WITH CHECK (true)` on all tables
4. **Unsigned JWT decode** — second `verify_token()` decodes without signature verification
5. **4 competing requirements files** — divergent dependency versions
6. **openai v2 breaking change** — `pmoves_upserter.py` uses v1 API

### MEDIUM (8)
1. Typo'd `compse.yml` duplicate
2. Tracked `.code-workspace` file
3. `version: '3.8'` in 11 docker-compose files
4. `package-lock.json` in `.gitignore` breaks Docker frontend build
5. Tailwind v4 config uses v3 patterns
6. 4 `.new` temp files tracked
7. Missing `.gitignore` entries for dynamic files
8. `NATS_URL` missing credentials in some env files

## Pattern 6: Agent Zero Settings Architecture

- `get_default_value(name)` reads `A0_SET_<name>` from dotenv
- `normalize_settings()` always overwrites `mcp_server_token` — don't duplicate `create_auth_token()` in `get_default_settings()`
- Use `get_default_value("mcp_server_token") or create_auth_token()` for fallback

## Pattern 7: ServiceTier Canonical Definition

7 tiers: `data`, `api`, `llm`, `worker`, `media`, `agent`, `ui`

The `ui` tier is often missed in tooling that enumerates tiers.

---

## Cross-References

- Main MEMORY.md: `~/.claude/projects/.../memory/MEMORY.md`
- Submodule review learnings: `./submodule-review-learnings.md`
- PR reviews INDEX: `./INDEX.md`
- CODEX audit: `pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md`
