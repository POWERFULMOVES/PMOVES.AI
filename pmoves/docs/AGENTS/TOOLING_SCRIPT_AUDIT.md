# PMOVES Tooling Overlay Audit
_Generated: 2026-08-19_

## Summary
- PMOVES scripts/tools scanned: **493**
- PMOVES auth/user/login-focused entries: **61**
- Submodule keyword-matched scripts/tools: **728**
- Potential overlap rows: **162**
- Keywords with overlap: **auth, bootstrap, credential, onboard, password, profile, secret, token, user**
- Findings: **0 error(s)**, **5 warning(s)**

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
| `auth` | 0.57 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, bootstrap, pmoves, py |
| `auth` | 0.50 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/auth-monitor.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/termux-auth-widget.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/claude-auth-status.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.44 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/termux-quick-auth.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.40 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/ci-hydrate-live-auth.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Archon` | `PMOVES-Archon/packages/server/src/scripts/setup-auth.ts` | auth, scripts, setup |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, pmoves, sh |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/packages/server/src/scripts/setup-auth.ts` | auth, scripts, setup |
| `auth` | 0.38 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, pmoves, py |
| `auth` | 0.38 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, bootstrap, pmoves |
| `auth` | 0.33 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/mobile-reauth.sh` | pmoves, scripts, sh |
| `auth` | 0.33 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.33 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.27 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/prepare-codex-ci-auth.ts` | auth, pmoves, scripts |
| `auth` | 0.25 | `pmoves/scripts/integration-auth-setup.sh` | `Pmoves-cipher` | `Pmoves-cipher/src/pmoves/auth.ts` | auth, pmoves |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-ottomator-agents/tweet-generator-agent/twitter_auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/auth.py` | auth, py |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `Pmoves-cipher` | `Pmoves-cipher/src/pmoves/auth.ts` | auth, pmoves |
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
| `bootstrap` | 0.57 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, bootstrap, pmoves, py |
| `bootstrap` | 0.50 | `pmoves/scripts/bootstrap-hermes-crush.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.50 | `pmoves/scripts/hermes-fleet-bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
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
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/nvidia/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/zai/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/xai/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/cerebras/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/minimax/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/longcat/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/tencent/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/kilocode/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/opencode/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/meta/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/fal/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/qianfan/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/baseten/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/deepseek/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/huggingface/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/moonshot/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/pixverse/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/cohere/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/chutes/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/openrouter/onboard.ts` | onboard |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_change.js` | password |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_generate.js` | password |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | pmoves, profile, py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_backpressure.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_backpressure.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_language_filter.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_config_regression.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/src/jcodemunch_mcp/tools/get_pr_risk_profile.py` | profile, py, tools |
| `profile` | 0.27 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_language_filter.py` | pmoves, profile, py |
| `profile` | 0.27 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_config_regression.py` | pmoves, profile, py |
| `profile` | 0.27 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/src/jcodemunch_mcp/tools/get_pr_risk_profile.py` | profile, py, tools |
| `profile` | 0.18 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | profile, py |
| `profile` | 0.18 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_backpressure.py` | profile, py |
| `profile` | 0.18 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/src/jcodemunch_mcp/tools/get_pr_risk_profile.py` | profile, tools |
| `profile` | 0.17 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_language_filter.py` | profile, py |
| `profile` | 0.17 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_config_regression.py` | profile, py |
| `profile` | 0.17 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/src/jcodemunch_mcp/tools/get_pr_risk_profile.py` | profile, py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES.YT` | `PMOVES.YT/yt_dlp/extractor/eroprofile.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/episode_profiles.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/speaker_profiles.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/claws/openclaw-profile.ts` | profile |
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
| `secret` | 0.33 | `pmoves/tools/secrets_self_generated.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.30 | `pmoves/tools/docker_mcp_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.30 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.shared.ts` | runtime, secrets, tools |
| `secret` | 0.30 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools.types.ts` | runtime, secrets, tools |
| `secret` | 0.30 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools-fallback.runtime.ts` | runtime, secrets, tools |
| `secret` | 0.30 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools-manifest.runtime.ts` | runtime, secrets, tools |
| `secret` | 0.27 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-web-tools-selection.types.ts` | runtime, secrets, tools |
| `secret` | 0.22 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/secrets/runtime-command-secrets.ts` | runtime, secrets |
| `secret` | 0.20 | `pmoves/scripts/populate_github_app_secrets.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `secret` | 0.20 | `pmoves/scripts/populate_github_app_secrets.sh` | `PMOVES-supabase` | `PMOVES-supabase/scripts/getSecrets.js` | pmoves, scripts |
| `token` | 0.30 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.30 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/harness/capture_token_baseline.py` | capture, py, token |
| `token` | 0.27 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.22 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.22 | `pmoves/scripts/mint_cipher_token.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/harness/capture_token_baseline.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.17 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Ultimate-TTS-Studio` | `PMOVES-Ultimate-TTS-Studio/fish_speech/tokenizer.py` | pmoves, py |
| `token` | 0.15 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Ultimate-TTS-Studio` | `PMOVES-Ultimate-TTS-Studio/fish_speech/tokenizer.py` | pmoves, py |
| `token` | 0.11 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/auto-reply/tokens.ts` | tokens |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | tokens |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | tokens |
| `token` | 0.10 | `pmoves/scripts/claws/rotate-tokens.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/auto-reply/tokens.test.ts` | tokens |
| `token` | 0.10 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/utils/token-format.ts` | token |
| `token` | 0.10 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/infra/pairing-token.ts` | token |
| `user` | 0.40 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/tools/notify_user.py` | pmoves, py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.30 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, py, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_convert.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_load.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-space-agent` | `PMOVES-space-agent/commands/user.js` | pmoves, user |
| `user` | 0.17 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/src/pipecat/turns/user_start/transcription_user_turn_start_strategy.py` | py, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/user_manager_test.py` | py, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/app_test/user_manager_system_user_test.py` | py, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/folder_paths_test/system_user_test.py` | py, user |
| `user` | 0.14 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-n8n-mcp/scripts/test-user-id-persistence.ts` | pmoves, user |
| `user` | 0.14 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/system_user_endpoint_test.py` | py, user |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-postman-mcp-server/src/tools/getAuthenticatedUser.ts` | tools |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-postman-mcp-server/src/tools/getCollectionsForkedByUser.ts` | tools |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/username.py` | py |
| `user` | 0.09 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/state/user-profiles.ts` | user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/pmoves-nextjs/lighthouserc.js` | pmoves |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/state/user-profiles.test.ts` | user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/state/user-profiles-schema.ts` | user |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/src/infra/sqlite-user-version.ts` | user |

## Findings
- [WARN] `SUBMODULE_SCAN_CAPPED` `PMOVES-ClawZ`: Scan capped at 600 matched files for this submodule.
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'bootstrap_node' found in: pmoves/scripts/bootstrap-node.sh, pmoves/scripts/claws/bootstrap-node.sh
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'fork_sync' found in: pmoves/tools/fork_sync.py, pmoves/tools/_deprecated/fork_sync.py
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-tailscale-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-nats-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

