# PMOVES Tooling Overlay Audit
_Generated: 2026-09-03_

## Summary
- PMOVES scripts/tools scanned: **529**
- PMOVES auth/user/login-focused entries: **68**
- Submodule keyword-matched scripts/tools: **861**
- Potential overlap rows: **188**
- Keywords with overlap: **auth, bootstrap, credential, onboard, password, profile, secret, session, token, user**
- Findings: **0 error(s)**, **6 warning(s)**

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
| `auth` | 0.44 | `pmoves/tools/yt_oauth_flow.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/mcp_oauth.py` | oauth, pmoves, py, tools |
| `auth` | 0.40 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/ci-hydrate-live-auth.sh` | auth, pmoves, scripts, sh |
| `auth` | 0.40 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/microsoft_graph_auth.py` | auth, pmoves, py, tools |
| `auth` | 0.40 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/microsoft_graph_auth.py` | auth, pmoves, py, tools |
| `auth` | 0.40 | `pmoves/tools/yt_oauth_flow.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/mcp_dashboard_oauth.py` | oauth, pmoves, py, tools |
| `auth` | 0.40 | `pmoves/tools/yt_oauth_flow.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/mcp_oauth_manager.py` | oauth, pmoves, py, tools |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, pmoves, sh |
| `auth` | 0.38 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, pmoves, py |
| `auth` | 0.38 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, bootstrap, pmoves |
| `auth` | 0.33 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/mobile-reauth.sh` | pmoves, scripts, sh |
| `auth` | 0.33 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/skills/github/github-auth/scripts/gh-env.sh` | auth, scripts, sh |
| `auth` | 0.33 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.33 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.33 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/auth.py` | auth, pmoves, py |
| `bootstrap` | 0.67 | `pmoves/scripts/bootstrap-node.sh` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/scripts/lib/node-bootstrap.sh` | bootstrap, node, scripts, sh |
| `bootstrap` | 0.67 | `pmoves/scripts/claws/bootstrap-node.sh` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/scripts/lib/node-bootstrap.sh` | bootstrap, node, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap-node.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-n8n` | `PMOVES-n8n/scripts/bootstrap_n8n_api.py` | bootstrap, pmoves, py, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/tools/credential_fetcher.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/credential_files.py` | credential, pmoves, py, tools |
| `credential` | 0.50 | `pmoves/tools/credential_setup.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/credential_files.py` | credential, pmoves, py, tools |
| `credential` | 0.50 | `pmoves/tools/credential_urlencoder.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/credential_files.py` | credential, pmoves, py, tools |
| `credential` | 0.44 | `pmoves/tools/chit_credential_demo.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/credential_files.py` | credential, pmoves, py, tools |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Spark-VSS` | `PMOVES-Spark-VSS/skills/vss-deploy-profile/scripts/check_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/tools/credential_fetcher.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/credential_pool.py` | credential, pmoves, py |
| `credential` | 0.38 | `pmoves/tools/credential_fetcher.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/credential_sources.py` | credential, pmoves, py |
| `credential` | 0.38 | `pmoves/tools/credential_fetcher.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/credential_persistence.py` | credential, pmoves, py |
| `onboard` | 0.43 | `pmoves/tools/onboarding_helper.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/onboarding.py` | onboarding, pmoves, py |
| `onboard` | 0.22 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/onboarding.py` | pmoves, py |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/opencode/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/xai/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/google/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/fal/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/fireworks/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/moonshot/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/qianfan/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/together/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/qwen/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/deepseek/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/stepfun/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/pixverse/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/mistral/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/tencent/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/chutes/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/venice/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/huggingface/onboard.ts` | onboard |
| `onboard` | 0.11 | `pmoves/tools/hf_model_onboard.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/extensions/cerebras/onboard.ts` | onboard |
| `password` | 0.17 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/onepassword_secrets_cli.py` | pmoves, py |
| `password` | 0.17 | `pmoves/tools/rotate_db_role_password.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/onepassword_secrets_cli.py` | pmoves, py |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_change.js` | password |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_generate.js` | password |
| `password` | 0.09 | `pmoves/scripts/set_open_notebook_password.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/secret_sources/onepassword.py` | py |
| `password` | 0.09 | `pmoves/tools/rotate_db_role_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_change.js` | password |
| `password` | 0.09 | `pmoves/tools/rotate_db_role_password.py` | `PMOVES-space-agent` | `PMOVES-space-agent/server/api/password_generate.js` | password |
| `password` | 0.09 | `pmoves/tools/rotate_db_role_password.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/secret_sources/onepassword.py` | py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | pmoves, profile, py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_backpressure.py` | pmoves, profile, py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/gateway/profile_routing.py` | pmoves, profile, py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/scripts/profile-tui.py` | pmoves, profile, py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/profile_describer.py` | pmoves, profile, py |
| `profile` | 0.33 | `pmoves/tools/profile_loader.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/profile_distribution.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/scripts/profile-tui.py` | profile, py, scripts |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/agent_profile_set.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_backpressure.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/gateway/profile_routing.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/scripts/profile-tui.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/profile_describer.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/launcher_profile_select.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/profile_distribution.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/models/apply_profile.sh` | `PMOVES-Spark-VSS` | `PMOVES-Spark-VSS/skills/vss-deploy-profile/scripts/probe_remote_models.sh` | models, profile, sh |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_language_filter.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/profile_config_regression.py` | pmoves, profile, py |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/src/jcodemunch_mcp/tools/get_pr_risk_profile.py` | profile, py, tools |
| `profile` | 0.30 | `pmoves/tools/profile_loader.py` | `PMOVES-OrcaSlicer` | `PMOVES-OrcaSlicer/scripts/orca_extra_profile_check.py` | pmoves, profile, py |
| `profile` | 0.27 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Spark-VSS` | `PMOVES-Spark-VSS/skills/vss-deploy-profile/scripts/normalize_resolved_yml.py` | profile, py, scripts |
| `profile` | 0.27 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-OrcaSlicer` | `PMOVES-OrcaSlicer/scripts/orca_extra_profile_check.py` | profile, py, scripts |
| `secret` | 0.38 | `pmoves/tools/_secrets_common.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/_secrets_common.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_harvest.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_harvest.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_sync.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_untrack.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.38 | `pmoves/tools/secrets_untrack.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/_secrets_common.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/onepassword_secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/check_required_secrets.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_local_hydrate.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_self_generated.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/secrets.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_self_generated.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/secrets_cli.py` | pmoves, py, secrets |
| `secret` | 0.33 | `pmoves/tools/secrets_sync.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/onepassword_secrets_cli.py` | pmoves, py, secrets |
| `session` | 0.40 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/scripts/docker_rebootstrap_nous_session.py` | pmoves, py, scripts, session |
| `session` | 0.38 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/agent/session_activity.py` | pmoves, py, session |
| `session` | 0.38 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/gateway/session.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/acp_adapter/session.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/gateway/session_state.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/gateway/session_stall.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/gateway/session_context.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_listing.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_recap.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_filters.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_export.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_recovery.py` | pmoves, py, session |
| `session` | 0.33 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/pty_session.py` | pmoves, py, session |
| `session` | 0.30 | `pmoves/scripts/session_check.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-n8n-mcp/scripts/test-single-session.sh` | pmoves, scripts, session |
| `session` | 0.30 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tools/session_search_tool.py` | pmoves, py, session |
| `session` | 0.30 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/tui_gateway/methods_session.py` | pmoves, py, session |
| `session` | 0.30 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_export_html.py` | pmoves, py, session |
| `session` | 0.30 | `pmoves/scripts/session_check.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/session_export_md.py` | pmoves, py, session |
| `session` | 0.25 | `pmoves/scripts/session_check.py` | `PMOVES-ClawZ` | `PMOVES-ClawZ/scripts/proof-73706-message-sending-session-key.ts` | pmoves, scripts, session |
| `session` | 0.22 | `pmoves/scripts/session_check.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/features/agent_sdk/session_manager.py` | py, session |
| `token` | 0.30 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.30 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/skills/github/github-auth/scripts/git-credential-token.py` | py, scripts, token |
| `token` | 0.30 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/harness/capture_token_baseline.py` | capture, py, token |
| `token` | 0.27 | `pmoves/tools/cf_dns_token_provision.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.27 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/api/csrf_token.py` | pmoves, py, token |
| `token` | 0.22 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.22 | `pmoves/scripts/mint_cipher_token.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/harness/capture_token_baseline.py` | py, token |
| `token` | 0.20 | `pmoves/scripts/mint_cipher_token.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/dashboard_auth/token_auth.py` | py, token |
| `token` | 0.20 | `pmoves/tools/cf_dns_token_provision.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.20 | `pmoves/tools/cf_dns_token_provision.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.18 | `pmoves/tools/cf_dns_token_provision.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `token` | 0.18 | `pmoves/tools/cf_dns_token_provision.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.18 | `pmoves/tools/cf_dns_token_provision.py` | `PMOVES-jcodemunch-mcp` | `PMOVES-jcodemunch-mcp/benchmarks/harness/capture_token_baseline.py` | py, token |
| `token` | 0.18 | `pmoves/tools/cf_dns_token_provision.py` | `PMOVES-hermes-agent` | `PMOVES-hermes-agent/hermes_cli/dashboard_auth/token_auth.py` | py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/helpers/tokens.py` | pmoves, py |
| `user` | 0.40 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/tools/notify_user.py` | pmoves, py, tools, user |
| `user` | 0.33 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-Spark-VSS` | `PMOVES-Spark-VSS/deploy/docker/services/vios/scripts/user_additional_install.sh` | scripts, sh, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.30 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-Spark-VSS` | `PMOVES-Spark-VSS/deploy/helm/services/vios/charts/vios-nvstreamer/scripts/user_additional_install.sh` | scripts, sh, user |
| `user` | 0.30 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-Spark-VSS` | `PMOVES-Spark-VSS/services/vios/deployment/stream-processing/docker-compose/scripts/user_additional_install.sh` | scripts, sh, user |
| `user` | 0.30 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, py, user |
| `user` | 0.25 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-n8n-mcp/scripts/test-user-id-persistence.ts` | pmoves, scripts, user |
| `user` | 0.22 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-pinokio` | `PMOVES-pinokio/user-agent.js` | pmoves, user |
| `user` | 0.20 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, user |
| `user` | 0.20 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-space-agent` | `PMOVES-space-agent/commands/user.js` | pmoves, user |
| `user` | 0.20 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-pinokio` | `PMOVES-pinokio/user-agent.js` | pmoves, user |
| `user` | 0.18 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/tools/notify_user.py` | pmoves, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_load.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_convert.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-space-agent` | `PMOVES-space-agent/commands/user.js` | pmoves, user |
| `user` | 0.17 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-pinokio` | `PMOVES-pinokio/script/run-user-agent-diagnostic.js` | pmoves, user |
| `user` | 0.17 | `pmoves/scripts/sso-create-user.sh` | `PMOVES-pinokio` | `PMOVES-pinokio/script/run-user-agent-test.js` | pmoves, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/app_test/user_manager_system_user_test.py` | py, user |

## Findings
- [WARN] `SUBMODULE_SCAN_CAPPED` `PMOVES-ClawZ`: Scan capped at 600 matched files for this submodule.
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'bootstrap_node' found in: pmoves/scripts/bootstrap-node.sh, pmoves/scripts/claws/bootstrap-node.sh
- [WARN] `DUPLICATE_SCRIPT_STEM`: Potential duplicate/ad-hoc tooling stem 'fork_sync' found in: pmoves/tools/fork_sync.py, pmoves/tools/_deprecated/fork_sync.py
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-nats-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.
- [WARN] `ORPHAN_PMOVES_DIR` `pmoves-tailscale-mcp`: Directory looks like a PMOVES module but is not mapped in .gitmodules.
- [WARN] `MISSING_WORKFLOW_ROUTE`: No canonical workflow route defined for keyword 'session'.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

