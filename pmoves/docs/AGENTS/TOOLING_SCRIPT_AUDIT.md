# PMOVES Tooling Overlay Audit
_Generated: 2026-06-26_

## Summary
- PMOVES scripts/tools scanned: **365**
- PMOVES auth/user/login-focused entries: **46**
- Submodule keyword-matched scripts/tools: **628**
- Potential overlap rows: **158**
- Keywords with overlap: **auth, bootstrap, credential, onboard, password, profile, secret, token, user**
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
| `auth` | 0.62 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/setup-auth-system.sh` | auth, pmoves, scripts, setup, sh |
| `auth` | 0.50 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/auth-monitor.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/termux-auth-widget.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/claude-auth-status.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/termux-quick-auth.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Archon` | `PMOVES-Archon/packages/server/src/scripts/setup-auth.ts` | auth, scripts, setup |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/packages/server/src/scripts/setup-auth.ts` | auth, scripts, setup |
| `auth` | 0.33 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/mobile-reauth.sh` | pmoves, scripts, sh |
| `auth` | 0.33 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.33 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/auth.py` | auth, py |
| `auth` | 0.25 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/auth.py` | auth, py |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-supabase/scripts/authorizeVercelDeploys.ts` | pmoves, scripts |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/mkdeb.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postrm.sh` | auth, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap-node.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-n8n` | `PMOVES-n8n/scripts/bootstrap_n8n_api.py` | bootstrap, pmoves, py, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/scripts/git-credential-archon.sh` | pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/tools/credential_setup.sh` | `PMOVES-Archon` | `PMOVES-Archon/scripts/git-credential-archon.sh` | credential, pmoves, sh |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.29 | `pmoves/scripts/credentials/print_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | scripts, sh |
| `credential` | 0.25 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/scripts/git-credential-archon.sh` | scripts, sh |
| `credential` | 0.25 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/credentials.py` | credentials, py |
| `credential` | 0.25 | `pmoves/scripts/fetch_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | scripts, sh |
| `credential` | 0.25 | `pmoves/tools/credential_fetcher.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/domain/credential.py` | credential, py |
| `credential` | 0.25 | `pmoves/tools/credential_setup.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/domain/credential.py` | credential, py |
| `credential` | 0.25 | `pmoves/tools/credential_setup.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/scripts/git-credential-archon.sh` | credential, sh |
| `credential` | 0.25 | `pmoves/tools/credential_urlencoder.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/domain/credential.py` | credential, py |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `credential` | 0.22 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, scripts |
| `onboard` | 0.12 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/plugin-sdk/onboarding.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.types.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.completion.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.finalize.ts` | onboarding |
| `onboard` | 0.11 | `pmoves/tools/onboarding_helper.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/wizard/onboarding.test.ts` | onboarding |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard.test.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-helpers.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-hooks.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-interactive.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-search.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-auth.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-custom.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-types.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-remote.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-skills.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-config.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/onboard-channels.ts` | onboard |
| `onboard` | 0.10 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/e2e/onboard-docker.sh` | onboard |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_change.js` | password |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_generate.js` | password |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | pmoves, profile, py |
| `profile` | 0.18 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | profile, py |
| `profile` | 0.18 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/episode_profiles_service.py` | pmoves, py |
| `profile` | 0.17 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/run-main.profile-env.test.ts` | env, profile |
| `profile` | 0.12 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.ts` | profile |
| `profile` | 0.12 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/models-config.uses-first-github-copilot-profile-env-tokens.test.ts` | models, profile |
| `profile` | 0.12 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.ts` | profile |
| `profile` | 0.12 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/agents/models-config.uses-first-github-copilot-profile-env-tokens.test.ts` | env, profile |
| `profile` | 0.11 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/profile-capabilities.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.test.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile-utils.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES.YT` | `PMOVES.YT/yt_dlp/extractor/eroprofile.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/episode_profiles.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/speaker_profiles.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/profile-capabilities.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile.test.ts` | profile |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/cli/profile-utils.ts` | profile |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES.YT` | `PMOVES.YT/yt_dlp/extractor/eroprofile.py` | py |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/episode_profiles.py` | py |
| `secret` | 0.38 | `pmoves/tools/_secrets_common.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | runtime, secrets, tools |
| `secret` | 0.33 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.30 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | runtime, secrets, tools |
| `secret` | 0.22 | `pmoves/tools/_secrets_common.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.22 | `pmoves/tools/secrets_sync.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/scripts/mcp-toolkit-secrets-sync.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/scripts/mcp-toolkit-secrets-sync.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/scripts/populate_github_app_secrets.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/scripts/populate_github_app_secrets.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/tools/_secrets_common.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/check_required_secrets.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.ts` | secrets, tools |
| `secret` | 0.20 | `pmoves/tools/secrets_sync.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.test.ts` | secrets, tools |
| `token` | 0.27 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.15 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Ultimate-TTS-Studio` | `PMOVES-Ultimate-TTS-Studio/fish_speech/tokenizer.py` | pmoves, py |
| `token` | 0.11 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/auto-reply/tokens.ts` | tokens |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | tokens |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | tokens |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/auto-reply/tokens.test.ts` | tokens |
| `token` | 0.09 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/infra/pairing-token.ts` | token |
| `token` | 0.09 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/auth-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/text_encoders/spiece_tokenizer.py` | py |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/validate-params.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/run-simulation.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/export-metrics.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/providers/github-copilot-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/infra/pairing-token.test.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/line/channel-access-token.ts` | token |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/commands/gateway-install-token.ts` | token |
| `user` | 0.40 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/tools/notify_user.py` | pmoves, py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.30 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, py, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_convert.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_load.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-space-agent` | `PMOVES-space-agent/commands/user.js` | pmoves, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/user_manager_test.py` | py, user |
| `user` | 0.14 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-n8n-mcp/scripts/test-user-id-persistence.ts` | pmoves, user |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-postman-mcp-server/src/tools/getAuthenticatedUser.ts` | tools |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-postman-mcp-server/src/tools/getCollectionsForkedByUser.ts` | tools |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/pmoves-nextjs/lighthouserc.js` | pmoves |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/user_self_info.js` | user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/user_crypto_bootstrap.js` | user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/user_crypto_session_key.js` | user |
| `user` | 0.07 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/browser/chrome-user-data-dir.test-harness.ts` | user |
| `user` | 0.05 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/providers/google-shared.ensures-function-call-comes-after-user-turn.test.ts` | user |

## Findings
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'bootstrap_node' found in: pmoves/scripts/bootstrap-node.sh, pmoves/scripts/claws/bootstrap-node.sh
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'fork_sync' found in: pmoves/tools/fork_sync.py, pmoves/tools/_deprecated/fork_sync.py
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-tailscale-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-nats-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

