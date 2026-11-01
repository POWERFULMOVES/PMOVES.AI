# ACP Registry Manifest — pmoves-agent-zero (DRAFT, gated on PyPI packaging)

**Date:** 2026-10-07 | **Status:** READY (git-URL distribution — PyPI NOT required; validated live: `uvx --from git+...@feat/acp-auth-methods agent-zero-acp --version` -> 1.19)
**Upstream PR:** 3clyp50/a0_acp#1 (auth methods + bootstrap fix + packaging scaffold @ 61c4c6a) — merge is the only remaining gate
**Trade-off note:** registry hourly auto-update tracks PyPI/npm/GitHub-Releases only — a git-distribution entry updates via manual PRs (acceptable: we control the fork)

## pmoves-agent-zero/agent.json (for POWERFULMOVES/PMOVES-registry PR)

```json
{
  "id": "pmoves-agent-zero",
  "name": "PMOVES Agent Zero",
  "version": "1.19.0",
  "description": "Agent Zero as an ACP stdio agent: editor-native sessions with workspace prompts, streaming updates, session resume/fork, and env-var API-key authentication. Fleet-hardened PMOVES edition.",
  "repository": "https://github.com/3clyp50/a0_acp",
  "authors": ["3clyp50", "POWERFULMOVES"],
  "license": "MIT",
  "distribution": {
    "uvx": {
      "package": "git+https://github.com/POWERFULMOVES/a0_acp.git",
      "args": [],
      "env": {
        "AGENT_ZERO_HOME": "<local Agent Zero checkout>"
      }
    }
  }
}
```

## Publication checklist (updated 2026-10-07 — PyPI no longer required)
1. [ ] Merge 3clyp50/a0_acp#1 (authMethods + bootstrap fix + packaging scaffold; pyproject @ 61c4c6a)
2. [x] Packaging scaffold landed (pyproject + acp_adapter.py console script; uvx git build proven live)
3. [x] Distribution resolved: `uvx` package = git URL (schema-valid: package is any non-empty string; CI verify_uvx runs `uvx <package> <args>` — git spec supported by uv natively)
4. [ ] Fork POWERFULMOVES/PMOVES-registry, add `pmoves-agent-zero/agent.json`, PR per CONTRIBUTING.md (CI verifies authMethods handshake — now satisfiable: EnvVarAuthMethod advertised when AGENT_ZERO_API_KEY set)
5. [ ] Optional: SVG 16x16 monochrome currentColor icon; optional PyPI publication later for hourly auto-update tracking

## Auth contract (implemented + validated 2026-10-07)
- `initialize` advertises `env_var` authMethod `agent-zero-api-key` iff `AGENT_ZERO_API_KEY` is set; vars: AGENT_ZERO_API_KEY (secret, required)
- `authenticate` validates presented bearer credential against the instance key; PermissionError on mismatch
- Without key: `authMethods=[]`, permissive local editor use (backwards-compatible, measured)
