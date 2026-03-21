# PMOVES Tooling Overlay Audit
_Generated: 2026-03-21_

## Summary
- PMOVES scripts/tools scanned: **251**
- PMOVES auth/user/login-focused entries: **37**
- Submodule keyword-matched scripts/tools: **565**
- Potential overlap rows: **144**
- Keywords with overlap: **auth, bootstrap, credential, onboard, profile, secret, token, user**
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
| `auth` | 0.62 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/setup-auth-system.sh` | auth, pmoves, scripts, setup, sh |
| `auth` | 0.50 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/auth-monitor.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/claude-auth-status.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/termux-auth-widget.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/termux-quick-auth.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.33 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/mobile-reauth.sh` | pmoves, scripts, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/mkdeb.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/features/mcp_bridge/auth.py` | auth, py |
| `auth` | 0.22 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/features/mcp_bridge/auth.py` | auth, py |
| `auth` | 0.20 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/auth-monitor.sh` | auth, pmoves |
| `auth` | 0.20 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/tools/whatsapp-target-auth.ts` | auth, tools |
| `auth` | 0.20 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/auth-monitor.sh` | auth, pmoves |
| `auth` | 0.20 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/tools/whatsapp-target-auth.ts` | auth, tools |
| `auth` | 0.18 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/claude-auth-status.sh` | auth, pmoves |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-n8n` | `PMOVES-n8n/scripts/bootstrap_n8n_api.py` | bootstrap, pmoves, py, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.20 | `pmoves/tools/credential_setup.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | pmoves, sh |
| `credential` | 0.20 | `pmoves/tools/credential_setup.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | pmoves, sh |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.18 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts |
| `credential` | 0.18 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/generate-secretref-credential-matrix.ts` | pmoves, scripts |
| `credential` | 0.18 | `pmoves/tools/credential_fetcher.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/generate-secretref-credential-matrix.ts` | credential, pmoves |
| `onboard` | 0.12 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/plugin-sdk/onboarding.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.completion.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.finalize.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.test.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.types.ts` | onboarding |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/e2e/onboard-docker.sh` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-auth.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-channels.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-config.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-custom.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-helpers.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-hooks.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-interactive.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-remote.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-search.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-skills.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-types.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard.test.ts` | onboard |
| `profile` | 0.17 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/run-main.profile-env.test.ts` | env, profile |
| `profile` | 0.12 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/models-config.uses-first-github-copilot-profile-env-tokens.test.ts` | models, profile |
| `profile` | 0.12 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.ts` | profile |
| `profile` | 0.12 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.ts` | profile |
| `profile` | 0.12 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/models-config.uses-first-github-copilot-profile-env-tokens.test.ts` | env, profile |
| `profile` | 0.11 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/profile-capabilities.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile-utils.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.test.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/profile-capabilities.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile-utils.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.test.ts` | profile |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/profile-capabilities.ts` | profile |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile-utils.ts` | profile |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.test.ts` | profile |
| `profile` | 0.10 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/model-ref-profile.ts` | profile |
| `profile` | 0.10 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/chrome.profile-decoration.ts` | profile |
| `profile` | 0.10 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/model-ref-profile.ts` | profile |
| `profile` | 0.10 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/chrome.profile-decoration.ts` | profile |
| `profile` | 0.09 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/model-ref-profile.ts` | profile |
| `secret` | 0.33 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | runtime, secrets, tools |
| `secret` | 0.30 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | runtime, secrets, tools |
| `secret` | 0.29 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.22 | `pmoves/tools/secrets_sync.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/check_required_secrets.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/push-gh-secrets.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-auth-collectors.ts` | runtime, secrets |
| `secret` | 0.20 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/secrets_sync.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | secrets, tools |
| `secret` | 0.18 | `pmoves/tools/check_required_secrets.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | secrets, tools |
| `secret` | 0.18 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | secrets, tools |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/api/csrf_token.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.10 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/tokens.py` | py |
| `token` | 0.09 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/auth-token.ts` | token |
| `token` | 0.09 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/infra/pairing-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/gateway-install-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/infra/pairing-token.test.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/line/channel-access-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/providers/github-copilot-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/compaction.token-sanitize.test.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/doctor-gateway-auth-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/gateway-install-token.test.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/config/slack-token-validation.test.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/providers/github-copilot-token.test.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/test-utils/auth-token-assertions.ts` | token |
| `token` | 0.07 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/anthropic.setup-token.live.test.ts` | token |
| `token` | 0.07 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/control-auth.auto-token.test.ts` | token |
| `token` | 0.07 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/doctor-gateway-auth-token.test.ts` | token |
| `token` | 0.07 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/gateway/server.auth.default-token.suite.ts` | token |
| `token` | 0.07 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/gateway/server.auth.default-token.test.ts` | token |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.07 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/chrome-user-data-dir.test-harness.ts` | user |
| `user` | 0.05 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/providers/google-shared.ensures-function-call-comes-after-user-turn.test.ts` | user |

## Findings
- No findings.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

