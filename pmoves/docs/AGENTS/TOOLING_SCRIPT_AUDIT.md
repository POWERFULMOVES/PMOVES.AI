# PMOVES Tooling Overlay Audit
_Generated: 2026-07-14_

## Summary
- PMOVES scripts/tools scanned: **389**
- PMOVES auth/user/login-focused entries: **48**
- Submodule keyword-matched scripts/tools: **53**
- Potential overlap rows: **100**
- Keywords with overlap: **auth, bootstrap, credential, profile, secret, token, user**
- Findings: **0 error(s)**, **4 warning(s)**

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
| `auth` | 0.57 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, bootstrap, pmoves, py |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/packages/server/src/scripts/setup-auth.ts` | auth, scripts, setup |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, pmoves, sh |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/packages/server/src/scripts/setup-auth.ts` | auth, scripts, setup |
| `auth` | 0.38 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, pmoves, py |
| `auth` | 0.38 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, bootstrap, pmoves |
| `auth` | 0.25 | `pmoves/scripts/integration-auth-setup.sh` | `Pmoves-cipher` | `Pmoves-cipher/src/pmoves/auth.ts` | auth, pmoves |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-ottomator-agents/tweet-generator-agent/twitter_auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `Pmoves-cipher` | `Pmoves-cipher/src/pmoves/auth.ts` | auth, pmoves |
| `auth` | 0.25 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-ottomator-agents/tweet-generator-agent/twitter_auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_bootstrap_check.py` | `Pmoves-cipher` | `Pmoves-cipher/src/pmoves/auth.ts` | auth, pmoves |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, pmoves |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/mkdeb.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/authorizeVercelDeploys.ts` | pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-n8n` | `PMOVES-n8n/scripts/bootstrap_n8n_api.py` | bootstrap, pmoves, py, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, bootstrap, pmoves, py |
| `bootstrap` | 0.50 | `pmoves/scripts/bootstrap-node.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/bootstrap_drift_dynamo.py` | `PMOVES-n8n` | `PMOVES-n8n/scripts/bootstrap_n8n_api.py` | bootstrap, pmoves, py, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.44 | `pmoves/scripts/mcp-toolkit-bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.43 | `pmoves/scripts/bootstrap-node.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | bootstrap, pmoves, sh |
| `bootstrap` | 0.43 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | bootstrap, pmoves, py |
| `bootstrap` | 0.43 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | bootstrap, pmoves, sh |
| `bootstrap` | 0.43 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | bootstrap, pmoves, sh |
| `bootstrap` | 0.43 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | bootstrap, pmoves, sh |
| `bootstrap` | 0.43 | `pmoves/tools/integrations/bootstrap_workspace.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | bootstrap, integrations, sh |
| `bootstrap` | 0.38 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-n8n` | `PMOVES-n8n/scripts/bootstrap_n8n_api.py` | bootstrap, pmoves, scripts |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/tools/credential_setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | credential, pmoves, sh |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.29 | `pmoves/scripts/credentials/print_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | scripts, sh |
| `credential` | 0.25 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | scripts, sh |
| `credential` | 0.25 | `pmoves/scripts/fetch_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | scripts, sh |
| `credential` | 0.25 | `pmoves/tools/credential_setup.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | credential, sh |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/set_archon_provider.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | archon, scripts |
| `credential` | 0.22 | `pmoves/tools/credential_fetcher.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | credential, pmoves |
| `credential` | 0.22 | `pmoves/tools/credential_setup.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | credential, pmoves |
| `credential` | 0.22 | `pmoves/tools/credential_urlencoder.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | credential, pmoves |
| `credential` | 0.20 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | archon, scripts |
| `credential` | 0.20 | `pmoves/tools/chit_credential_demo.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/PMOVES-Archon/scripts/git-credential-archon.sh` | credential, pmoves |
| `credential` | 0.20 | `pmoves/tools/credential_setup.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | pmoves, sh |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | pmoves, profile, py |
| `profile` | 0.18 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | profile, py |
| `profile` | 0.09 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | profile |
| `secret` | 0.38 | `pmoves/tools/_secrets_common.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_untrack.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_funnel_populate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.20 | `pmoves/scripts/mcp-toolkit-secrets-sync.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/scripts/populate_github_app_secrets.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/tools/push-gh-secrets.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, secrets |
| `secret` | 0.18 | `pmoves/scripts/mcp-toolkit-secrets-sync.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, secrets |
| `secret` | 0.18 | `pmoves/scripts/populate_github_app_secrets.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, secrets |
| `secret` | 0.18 | `pmoves/tools/_secrets_common.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/extensions/python/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/extensions/python/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/extensions/python/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_untrack.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/extensions/python/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_untrack.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/extensions/python/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `token` | 0.27 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `token` | 0.15 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Ultimate-TTS-Studio` | `PMOVES-Ultimate-TTS-Studio/fish_speech/tokenizer.py` | pmoves, py |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | tokens |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/text_encoders/spiece_tokenizer.py` | py |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/validate-params.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/run-simulation.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/export-metrics.ts` | tools |
| `user` | 0.40 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/tools/notify_user.py` | pmoves, py, tools, user |
| `user` | 0.30 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, py, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_convert.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_load.py` | pmoves, py |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/user_manager_test.py` | py, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/app_test/user_manager_system_user_test.py` | py, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/folder_paths_test/system_user_test.py` | py, user |
| `user` | 0.14 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/system_user_endpoint_test.py` | py, user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/pmoves-nextjs/lighthouserc.js` | pmoves |

## Findings
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'bootstrap_node' found in: pmoves/scripts/bootstrap-node.sh, pmoves/scripts/claws/bootstrap-node.sh
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'fork_sync' found in: pmoves/tools/fork_sync.py, pmoves/tools/_deprecated/fork_sync.py
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-tailscale-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-nats-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

