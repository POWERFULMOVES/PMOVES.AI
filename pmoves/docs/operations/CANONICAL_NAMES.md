# Canonical Names — Decision Log

**Generated:** 2026-04-26
**Scope:** Authoritative naming decisions for credentials, env vars, identifiers, and gitlinks where the repo has accumulated drift across surfaces.
**Audience:** Both **rabbits** (CodeRabbit) and **owl** (Codex / ontology / formal review) — read this before flagging "drift" to confirm whether something is intentional aliasing-with-sunset vs unintentional drift.
**Sources:** `pmoves/docs/operations/CREDENTIAL_AND_DRIFT_SITREP.md` §5 (the inventory).
**Audit gate:** `pmoves/scripts/audit_naming_drift.py` (Phase 4) — verifies every `${VAR:-...}` empty default in compose is either listed below as a deprecated alias OR carries an explicit "intentional" annotation.

When a canonical decision changes, update this doc *first*, then run the audit gate, then migrate.

---

## How to read each entry

```
### N. <drift site short name>

- Canonical: `<the one true name>`
- Deprecated aliases: `<list>` (sunset: <date or condition>)
- Where the canonical lives: `<file path>`
- Migration path: <one-paragraph plan>
- Verification: <bash command operators run to confirm the canonical wins>
```

A "deprecated alias" means: the audit gate accepts it as a temporary fallback in `${CANONICAL:-${ALIAS:-}}` chains during the sunset window, but the gate fails if a *new* surface introduces an alias-only reference (no canonical).

---

## 1. JWT secret

- **Canonical:** `JWT_SECRET`
- **Deprecated aliases:** `SUPABASE_JWT_SECRET`, `GOTRUE_JWT_SECRET`, `PGRST_JWT_SECRET`, `API_JWT_SECRET`, `AUTH_JWT_SECRET`, `METRICS_JWT_SECRET` (sunset: 2026-05-26 — 30-day window)
- **Where the canonical lives:** `pmoves/bootstrap/registry.json §services.supabase` (declared); `pmoves/scripts/supabase/generate-keys.sh` (generated); `env.tier-supabase` (loaded at runtime)
- **Migration path:** Compose retains the `${JWT_SECRET:-${SUPABASE_JWT_SECRET:-}}` chain through the sunset window so existing operator envs keep working. Each service that internally needs a different *variable name* (Postgrest's `PGRST_JWT_SECRET`, GoTrue's `GOTRUE_JWT_SECRET`) is fine — those are *destination names* used by upstream binaries, not aliases of the source secret. The drift is when both the *source* lookup and the *destination* are aliased; that hides which secret actually wins. After 2026-05-26: drop `SUPABASE_JWT_SECRET` from the fallback chain repo-wide; keep canonical-only at every source.
- **Verification:**
  ```bash
  bash pmoves/scripts/with-env.sh env | grep -E "^JWT_SECRET=" | wc -l   # expect 1
  bash pmoves/scripts/with-env.sh env | grep -E "^SUPABASE_JWT_SECRET=" | wc -l   # post-sunset: expect 0
  ```

## 2. Supabase service-role key

- **Canonical:** `SERVICE_ROLE_KEY`
- **Deprecated aliases:** `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SERVICE_KEY`, `RENDER_WEBHOOK_SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SECRET_KEY` (sunset: 2026-05-26)
- **Where the canonical lives:** `pmoves/bootstrap/registry.json §services.supabase`
- **Migration path:** Same pattern as JWT_SECRET. Compose lines 603/812/877/1003/1446/1483/1696/2477 each carry a different fallback chain; collapse all of them to `${SERVICE_ROLE_KEY:?Set in env.tier-supabase}` after sunset.
- **Verification:**
  ```bash
  bash pmoves/scripts/with-env.sh env | grep -E "^SERVICE_ROLE_KEY=" | wc -l   # expect 1
  ```

## 3. GitHub App private key

- **Canonical:** `GH_APP_PRIVATE_KEY` (PEM, must start `-----BEGIN RSA PRIVATE KEY-----`)
- **Deprecated alias:** `GH_APP_SEC` (this is the OAuth client secret, NOT a PEM; misuse in 4 workflows, see sitrep §2)
- **Where the canonical lives:** GitHub repo secrets; loaded into workflows as `${{ secrets.GH_APP_PRIVATE_KEY }}` at the `private-key:` parameter of `actions/create-github-app-token`
- **Migration path:** Operator uploads PEM as new secret `GH_APP_PRIVATE_KEY`. Then 5 workflow files patch their `private-key:` line from `secrets.GH_APP_SEC` → `secrets.GH_APP_PRIVATE_KEY` (build-images, integrations-ghcr, self-hosted-builds, self-hosted-builds-hardened, test-app-token). `GH_APP_SEC` retained as the OAuth client secret in its actual semantic role. The audit gate should detect *misuse* (passing `GH_APP_SEC` to a `private-key` parameter) and fail.
- **Verification:**
  ```bash
  gh secret list | grep GH_APP_PRIVATE_KEY   # expect a row
  grep -rn "private-key:.*GH_APP_SEC" .github/workflows/   # expect zero
  ```

## 4. Transcribe-and-fetch gitlink

- **Canonical:** `aef3a86e817bc2d266b8b0845b6b118062e8dc7a` (current `origin/HEAD` of `https://github.com/POWERFULMOVES/PMOVES-transcribe-and-fetch`)
- **Deprecated:** `322f05f7a` (ghost SHA; never reachable on remote)
- **Where the canonical lives:** `.gitmodules` + the gitlink commit (recorded by PR #1371)
- **Migration path:** PR #1371 closes this. Verified reachable: `git ls-remote https://github.com/POWERFULMOVES/PMOVES-transcribe-and-fetch.git HEAD` returns `aef3a86…`. CodeRabbit's anonymous probe hit RPC error 52 (private repo) — that surface failure was a false-positive; thread resolution on PR #1371 documents the verification.
- **Verification:**
  ```bash
  git -C PMOVES-transcribe-and-fetch ls-remote origin HEAD | head -1   # expect aef3a86…
  git submodule update --init --recursive PMOVES-transcribe-and-fetch
  ```

## 5. MCP server token in Compose

- **Canonical:** *do not set in compose env list at all* — let `env_file: env.tier-agent` provide `A0_SET_mcp_server_token` when the operator has pinned a token; otherwise let Agent Zero auto-generate.
- **Deprecated pattern:** `- A0_SET_mcp_server_token=${MCP_SERVER_TOKEN:-}` (the empty default silently overrides the env_file value when `MCP_SERVER_TOKEN` is unset in the host shell)
- **Where the canonical lives:** `env.tier-agent` (one line) + comment block in compose explaining the omission
- **Migration path:** PR #1371 closes the canonical compose file (`pmoves/docker-compose.yml`); the agents overlay (`pmoves/docker-compose.agents.yml`) needs the same edit but is blocked by readOnlyPaths until patterns.yaml is extended. Audit gate flags: *"any `A0_SET_*=${X:-}` empty default in compose without an explicit `# host-leak-guard` comment is drift."*
- **Verification:**
  ```bash
  grep -n "A0_SET_mcp_server_token" pmoves/docker-compose*.yml  # expect 0 matches OR commented-out lines only
  ```

## 6. Health endpoints

- **Canonical:** **per-service entry in `pmoves/config/agent_registry.yaml` is authoritative**. There is no global health-endpoint claim.
- **Deprecated pattern:** any global "all services expose `/healthz`" sentence in docs/catalogs
- **Where the canonical lives:** `pmoves/config/agent_registry.yaml` (each agent declares its `health:` field)
- **Migration path:** PR #1385 fixes `.claude/CATALOG.md` to point readers at per-service entries. `services-catalog.md`, the `/healthz`-style smoke tests in `pmoves/scripts/codex_health_quick.py`, and the Prometheus blackbox probe config all need to source health paths from `agent_registry.yaml` instead of assuming `/healthz`.
- **Verification:**
  ```bash
  uv run --with pyyaml python -c "import yaml; r=yaml.safe_load(open('pmoves/config/agent_registry.yaml')); print({a['name']: a.get('health') for a in r['agents']})"
  ```

## 7. NATS broker URL

- **Canonical:** `NATS_URL` sourced from `env.tier-agent` only — no embedded credentials in compose defaults
- **Deprecated pattern:** `${NATS_URL:-nats://nats:pmoves@nats:4222}` (hardcoded password leaks into git history)
- **Where the canonical lives:** `env.tier-agent` (one line); `pmoves/bootstrap/registry.json §services.nats` (declares the variable)
- **Migration path:** Compose lines 2344/2372/2461 drop the embedded fallback. Operators with no `env.tier-agent` value fail loudly (`${NATS_URL:?Set NATS_URL in env.tier-agent}`) instead of silently using the leaked default.
- **Verification:**
  ```bash
  grep -nE 'NATS_URL.*://nats:[^@]+@' pmoves/docker-compose*.yml   # expect 0
  ```

## 8. WHISPER_DIARIZE handling

- **Canonical:** single helper `_env_truthy("WHISPER_DIARIZE")` consulted by both `/transcribe` (JSON) and `/transcribe_file` (multipart) endpoints; client `diarize` field overrides when present
- **Deprecated pattern:** hardcoded `Form(False)` or `Form(True)` defaults that never read the env
- **Where the canonical lives:** `pmoves/services/ffmpeg-whisper/server.py` (helper near line ~227, used by both endpoints)
- **Migration path:** PR #1390 closes this. After merge, any new endpoint added to the service that takes a `diarize` parameter must use the helper, not a literal default.
- **Verification:**
  ```bash
  grep -nE 'diarize.*=.*Form\(' pmoves/services/ffmpeg-whisper/server.py
  # expect 0 lines with literal True/False; only `Form(None)` with helper resolution downstream
  ```

## 9. PAT secret aliases

- **Canonical (interim):** `GH_PAT` for general repo access; per-alias scope documented in `pmoves/secrets/CHIT_MANIFEST.md`
- **Other names** retained with documented per-name scope: `GH_PAT_PUBLISH` (publish-only), `PMOVES_GITBOT_PAT` (bot ops), `CATACLYSMSTUDIOS_GH_PAT` + `HUNNINBEAR_GH_PAT` (cross-org), `DOCKER_PAT` (Docker registry)
- **Long-term canonical:** *no PAT* — GitHub App token replaces all programmatic uses (post §3 above)
- **Where the canonical lives:** GitHub repo secrets; manifest at `pmoves/secrets/CHIT_MANIFEST.md` (after manifest update)
- **Migration path:** Phase 1 — document scope-per-alias in CHIT_MANIFEST.md. Phase 2 — once `GH_APP_PRIVATE_KEY` ships and 5 workflows migrate, audit which PAT aliases still have *any* runtime use; retire those that don't. Phase 3 — runner registration moves to App-token JWT generation; retire the runner-PAT path.
- **Verification:**
  ```bash
  gh secret list | grep -iE "PAT|TOKEN" | sort
  ```

## 10. Port reservations

- **Canonical:** Agent Zero owns port `8080` (host) — it predates VoxCPM and other containers in compose ordering.
- **Deprecated pattern:** `agent_registry.yaml:349` documents VoxCPM "conflicts with Agent Zero, use different port" but no remap was applied; this is a documented-but-unenforced collision.
- **Migration path:** Pick a free port for VoxCPM (audit gate suggests one from `agent_registry.yaml` unused range); update both registry + compose mapping. Add a port-collision check to the audit gate that walks all `ports:` entries across compose files and fails on duplicate host-side bindings.
- **Verification:**
  ```bash
  uv run --with pyyaml python -c "
  import yaml, sys
  from collections import Counter
  ports = []
  for p in ['pmoves/docker-compose.yml','pmoves/docker-compose.agents.yml']:
      d = yaml.safe_load(open(p))
      for svc, body in (d.get('services') or {}).items():
          for entry in body.get('ports') or []:
              ports.append((str(entry).split(':')[0], svc, p))
  counts = Counter(p[0] for p in ports)
  dupes = {k: [s for s in ports if s[0] == k] for k, c in counts.items() if c > 1}
  if dupes: sys.exit(1)
  "
  ```

---

## What this document does NOT decide

- Schema versioning convention (e.g., `chit.cgp.v1.0` vs `cgp.v1` vs `geometry.cgp.v1`) — see CLAUDE.md "CGP Schema Version Naming" already-canonical entry; not in scope here.
- Which submodules are launch-blocking — see `pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml` (Stage 0 deliverable from prior plan).
- The 5×5 trail handshake invariant — see `pmoves/docs/operations/SIGNING_IDENTITY_CARDS.md`.

This decision log + the sitrep + the cards form the trio that the Phase 4 audit gate reads to verify all four channels (rabbit / owl / trail / remote) agree.

The audit gate prefers the durable `canonical_aliases` block in `pmoves/bootstrap/registry.json` and only falls back to parsing this markdown when the registry block is absent. When you add or change a canonical decision, update **both** surfaces (registry first, then this doc) and re-run `make -C pmoves naming-drift-check` to confirm the gate sees the new mapping.

<!-- GRAPHITI_MARK: CLAUDE-OPUS::CANONICAL-NAMES-DECISIONS::2026-04-26 -->
<!-- GRAPHITI_MARK: Z890-CLAUDE::CREDENTIAL-AUDIT-REVIEW::2026-04-26 -->

## Provider keys (2026-07-02)

Canonical env names for LLM provider credentials follow `pmoves/config/provider_catalog.yaml` (single source of truth). Structured form lives in `pmoves/bootstrap/registry.json` → `canonical_aliases`.

| Canonical | Deprecated aliases | Sunset |
|-----------|-------------------|--------|
| `MOONSHOT_API_KEY` | `KIMI_API_KEY` | 2026-10-01 |
| `ALIBABA_PRO_CODING_PLAN` | `ALIBABA_API_KEY`, `DASHSCOPE_API_KEY` | 2026-10-01 |
| `Z_AI_API_KEY` | `ZAI_API_KEY` | 2026-10-01 |
| `HF_TOKEN` | `HUGGINGFACE_TOKEN` | 2026-10-01 |

New providers added with the cloud-hybrid tier (2026-07-02): `KILOCODE_API_KEY`, `OLLAMA_API_KEY` (Ollama Pro cloud — distinct from `OLLAMA_BASE_URL` local) — no aliases, born canonical.
