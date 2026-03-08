# PMOVES Tooling Overlay Audit
_Generated: 2026-03-08_

## Summary
- PMOVES scripts/tools scanned: **219**
- PMOVES auth/user/login-focused entries: **35**
- Submodule keyword-matched scripts/tools: **178**
- Potential overlap rows: **124**
- Keywords with overlap: **auth, bootstrap, credential, profile, secret, token, user**
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
| `auth` | 0.57 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, bootstrap, pmoves, py |
| `auth` | 0.38 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, pmoves, sh |
| `auth` | 0.38 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, pmoves, py |
| `auth` | 0.38 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.sh` | auth, bootstrap, pmoves |
| `auth` | 0.33 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.33 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-ottomator-agents/tweet-generator-agent/twitter_auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_alignment_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/auth.py` | auth, py |
| `auth` | 0.25 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-ottomator-agents/tweet-generator-agent/twitter_auth.py` | auth, pmoves, py |
| `auth` | 0.25 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/auth.py` | auth, py |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `Pmoves-hyperdimensions` | `Pmoves-hyperdimensions/portal/portal-auth.js` | auth, pmoves |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, pmoves |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-supabase/scripts/authorizeVercelDeploys.ts` | pmoves, scripts |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/mkdeb.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/deb/prerm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postinst.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/postrm.sh` | auth, sh |
| `auth` | 0.22 | `pmoves/scripts/integration-auth-setup.sh` | `PMOVES-Tailscale` | `PMOVES-Tailscale/cmd/nginx-auth/rpm/prerm.sh` | auth, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/bootstrap_env.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, env, pmoves, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.ps1` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/codex_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/neo4j_bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/proxmox/pmoves-bootstrap.sh` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.sh` | bootstrap, pmoves, scripts, sh |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-BoTZ` | `PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/scripts/windows_bootstrap.ps1` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-BoTZ/scripts/bootstrap_env.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.57 | `pmoves/tools/auth_bootstrap_check.py` | `PMOVES-transcribe-and-fetch` | `PMOVES-transcribe-and-fetch/pmoves-integrations/auth/bootstrap.py` | auth, bootstrap, pmoves, py |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `bootstrap` | 0.50 | `pmoves/scripts/codex_bootstrap.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | bootstrap, pmoves, ps1, scripts |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.50 | `pmoves/scripts/fetch_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, pmoves, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.ps1` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, ps1, scripts |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.38 | `pmoves/scripts/credentials/print_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | credentials, scripts, sh |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.33 | `pmoves/scripts/fetch_credentials.sh` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.ps1` | credentials, pmoves, scripts |
| `credential` | 0.25 | `pmoves/scripts/credentials/set_archon_provider.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/credentials.py` | credentials, py |
| `credential` | 0.25 | `pmoves/tools/credential_fetcher.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/domain/credential.py` | credential, py |
| `credential` | 0.25 | `pmoves/tools/credential_setup.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/domain/credential.py` | credential, py |
| `credential` | 0.25 | `pmoves/tools/credential_urlencoder.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/domain/credential.py` | credential, py |
| `profile` | 0.18 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/episode_profiles_service.py` | pmoves, py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES.YT` | `PMOVES.YT/yt_dlp/extractor/eroprofile.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/episode_profiles.py` | py |
| `profile` | 0.11 | `pmoves/tools/profile_loader.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/speaker_profiles.py` | py |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES.YT` | `PMOVES.YT/yt_dlp/extractor/eroprofile.py` | py |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/episode_profiles.py` | py |
| `profile` | 0.10 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/routers/speaker_profiles.py` | py |
| `profile` | 0.08 | `pmoves/scripts/supabase/apply_env_profile.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/api/episode_profiles_service.py` | py |
| `secret` | 0.29 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/chit_decode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/chit_encode_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/runtime_secrets_hydrate.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.25 | `pmoves/tools/secrets_hardening_audit.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.18 | `pmoves/tools/secrets_sync.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/extensions/tool_execute_after/_10_mask_secrets.py` | py, secrets |
| `secret` | 0.17 | `pmoves/tools/check_required_secrets.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/extensions/tool_execute_before/_10_unmask_secrets.py` | py, secrets |
| `token` | 0.22 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Archon` | `PMOVES-Archon/python/.venv/Lib/site-packages/tokenizers/tools/visualizer.py` | py, tools |
| `token` | 0.22 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Archon` | `PMOVES-Archon/python/.venv/Lib/site-packages/tokenizers/tools/__init__.py` | py, tools |
| `token` | 0.22 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/.venv/Lib/site-packages/tokenizers/tools/visualizer.py` | py, tools |
| `token` | 0.22 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/.venv/Lib/site-packages/tokenizers/tools/__init__.py` | py, tools |
| `token` | 0.22 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/.venv/Lib/site-packages/tokenizers/tools/visualizer.py` | py, tools |
| `token` | 0.22 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/.venv/Lib/site-packages/tokenizers/tools/__init__.py` | py, tools |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/api/csrf_token.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/open_notebook/utils/token_utils.py` | py, token |
| `token` | 0.20 | `pmoves/tools/youtube_po_token_capture.py` | `Pmoves-Health-wger` | `Pmoves-Health-wger/wger/utils/api_token.py` | py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Archon` | `PMOVES-Archon/python/.venv/Lib/site-packages/prompt_toolkit/token.py` | py, token |
| `token` | 0.18 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-HiRAG` | `PMOVES-HiRAG/eval/cal_tokens.py` | pmoves, py |
| `token` | 0.15 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Ultimate-TTS-Studio` | `PMOVES-Ultimate-TTS-Studio/fish_speech/tokenizer.py` | pmoves, py |
| `token` | 0.10 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/helpers/tokens.py` | py |
| `token` | 0.10 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/.venv/Lib/site-packages/setuptools/_vendor/packaging/_tokenizer.py` | py |
| `token` | 0.10 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/.venv/Lib/site-packages/setuptools/_vendor/wheel/vendored/packaging/_tokenizer.py` | py |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/text_encoders/spiece_tokenizer.py` | py |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/export-metrics.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/run-simulation.ts` | tools |
| `token` | 0.08 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/.claude/skills/tokenism-analysis/tools/validate-params.ts` | tools |
| `token` | 0.07 | `pmoves/tools/youtube_po_token_capture.py` | `PMOVES-Archon` | `PMOVES-Archon/python/.venv/Lib/site-packages/anthropic/types/message_count_tokens_tool_param.py` | py |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Agent-Zero` | `PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Archon` | `PMOVES-Archon/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.33 | `pmoves/tools/create_supabase_boot_user.py` | `pmoves/integrations/archon` | `pmoves/integrations/archon/external/PMOVES-Agent-Zero/python/tools/notify_user.py` | py, tools, user |
| `user` | 0.30 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/app/user_manager.py` | pmoves, py, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Open-Notebook` | `PMOVES-Open-Notebook/.venv/Lib/site-packages/requests_toolbelt/utils/user_agent.py` | py, user |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_convert.py` | pmoves, py |
| `user` | 0.18 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/comfy/diffusers_load.py` | pmoves, py |
| `user` | 0.17 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/src/pipecat/turns/user_start/transcription_user_turn_start_strategy.py` | py, user |
| `user` | 0.17 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/src/pipecat/turns/user_stop/transcription_user_turn_stop_strategy.py` | py, user |
| `user` | 0.15 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Creator` | `PMOVES-Creator/tests-unit/prompt_server_test/user_manager_test.py` | py, user |
| `user` | 0.14 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-n8n-mcp/scripts/test-user-id-persistence.ts` | pmoves, user |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-postman-mcp-server/src/tools/getAuthenticatedUser.ts` | tools |
| `user` | 0.10 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-DoX` | `PMOVES-DoX/external/PMOVES-postman-mcp-server/src/tools/getCollectionsForkedByUser.ts` | tools |
| `user` | 0.09 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-Pipecat` | `PMOVES-Pipecat/.venv/Lib/site-packages/mpmath/usertools.py` | py |
| `user` | 0.08 | `pmoves/tools/create_supabase_boot_user.py` | `PMOVES-ToKenism-Multi` | `PMOVES-ToKenism-Multi/pmoves-nextjs/lighthouserc.js` | pmoves |

## Findings
- No findings.

## Operator Guidance
1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers.
2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits.
3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets.

