# Secrets Onboarding & Sharing

Purpose: keep PATs/API keys out of the repo while making collaboration easy.

What goes where
- GitHub Actions secrets (preferred): `GH_PAT_PUBLISH`, `GHCR_USERNAME`, `DOCKERHUB_PAT`, `DOCKERHUB_USERNAME`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, `GOOGLE_OAUTH_CLIENT_SECRET`, `DISCORD_WEBHOOK` (and any other third‑party keys).
- Environment scoping: use repo environments (Dev/Prod) for least privilege and required reviewers.
- Human retrieval: store the same values in the team vault (1Password/Bitwarden/etc.) for onboarding; never in tracked files.

Onboarding steps (new collaborator)
1) Get vault access and retrieve required secrets.
2) Copy `.env.example` → `.env.local` (or `pmoves/.env.local`) and paste values; keep these files untracked.
3) If rotating PATs/API keys, run `gh auth login` then set secrets:
   ```bash
   printf '%s' '<ghcr-pat>' | gh secret set GH_PAT_PUBLISH --repo POWERFULMOVES/PMOVES.AI
   printf '%s' '<docker-pat>' | gh secret set DOCKERHUB_PAT --repo POWERFULMOVES/PMOVES.AI
   ```
   Use environment-scoped secrets (`--env Dev`) when appropriate.
4) For local hardened runs, write secrets to `/run/secrets/*` and use the `*_FILE` env pattern shown below.
5) If using the local credentials-entry script, see `docs/SECRETS_ENTRY_SCRIPT.md` for how to keep outputs untracked and push values into GitHub secrets.

Compose/runtime pattern (hardened images)
- Preferred: mount secrets as files and reference them with `*_FILE` envs (example in `pmoves/docker-compose.hardened.yml`).
- Avoid inline env values for long secrets; use files for anything high-sensitivity (JWT secrets, service role keys, API keys).

Rotation
- Rotate any credential that ever touched a tracked file (including old `docs/notes.md` contents) before reuse.
- Set a 90‑day reminder for PAT/API keys; regenerate Discord webhooks instead of reusing.

Checklist before shipping a PR
- No secrets in `git diff` or `git status`.
- Secrets only in GitHub secrets, Docker secrets, vault, or untracked env files.
- If a new secret is introduced, add its name to this doc and the CI workflow variables.
