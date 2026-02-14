# PMOVES Tooling Overlay Audit
_Generated: 2026-02-14_

## Summary
- PMOVES scripts/tools scanned: **163**
- PMOVES auth/user/login-focused entries: **31**
- Submodule keyword-matched scripts/tools: **33**
- Potential overlap rows: **76**
- Keywords with overlap: **auth, bootstrap, credential, secret, token, user**
- Findings: **0 error(s)**, **0 warning(s)**

## Canonical Workflow Routes
| Keyword | PMOVES Can-Openers |
| --- | --- |
| `auth` | `supabase-boot-user`, `env-setup`, `preflight` |
| `bootstrap` | `first-run`, `env-setup`, `supa-start` |
| `credential` | `supabase-boot-user`, `env-setup`, `preflight` |
| `login` | `supabase-boot-user`, `first-run` |
| `onboard` | `first-run`, `preflight` |
| `password` | `supabase-boot-user`, `first-run` |
| `profile` | `env-setup`, `preflight` |
| `secret` | `env-setup`, `preflight`, `secrets-audit` |
| `token` | `supabase-boot-user`, `preflight` |
| `user` | `supabase-boot-user`, `up-agents-published`, `up-external` |

## Overlap Candidates
| Keyword | Score | PMOVES Script/Tool | Submodule | Submodule Script/Tool | Shared Tokens |
| --- | --- | --- | --- | --- | --- |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/authorizeVercelDeploys.ts` | pmoves, scripts |
| `auth` | 0.22 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/features/mcp_bridge/auth.py` | auth, py |
| `auth` | 0.17 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-BoTZ` | `PMOVES-BoTZ/.claude/skills/hf-tool-builder/references/hf_model_papers_auth.sh` | auth, sh |
| `auth` | 0.10 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-BoTZ` | `PMOVES-BoTZ/features/mcp_bridge/auth.py` | auth |
| `auth` | 0.10 | `pmoves/tools/auth_bootstrap_check.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/extras/authors/generate_authors_api.py` | py |
| `auth` | 0.10 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-supabase` | `PMOVES-supabase/scripts/authorizeVercelDeploys.ts` | pmoves |
| `auth` | 0.08 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/.claude/skills/hf-tool-builder/references/hf_model_papers_auth.sh` | auth |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.38 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.38 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.38 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts |
| `bootstrap` | 0.33 | `pmoves/tools/bootstrap_light_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves |
| `bootstrap` | 0.20 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.20 | `pmoves/tools/credential_setup.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | pmoves, sh |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.09 | `pmoves/tools/credential_fetcher.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | pmoves |
| `credential` | 0.09 | `pmoves/tools/credential_fetcher.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | pmoves |
| `credential` | 0.09 | `pmoves/tools/credential_setup.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | pmoves |
| `credential` | 0.09 | `pmoves/tools/credential_setup.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | pmoves |
| `credential` | 0.09 | `pmoves/tools/credential_setup.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | pmoves |
| `secret` | 0.29 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.11 | `pmoves/tools/push-gh-secrets.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | secrets |
| `secret` | 0.11 | `pmoves/tools/secrets_sync.py` | `PMOVES-supabase` | `PMOVES-supabase/scripts/getSecrets.js` | pmoves |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/api/csrf_token.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.15 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Ultimate-TTS-Studio` | `PMOVES-Ultimate-TTS-Studio/fish_speech/tokenizer.py` | pmoves, py |
| `token` | 0.10 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/tokens.py` | py |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/text_encoders/spiece_tokenizer.py` | py |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/export-metrics.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/run-simulation.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/validate-params.ts` | tools |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.30 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, py, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_convert.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_load.py` | pmoves, py |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/user_manager_test.py` | py, user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/pmoves-nextjs/lighthouserc.js` | pmoves |

## Findings
- No findings.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

