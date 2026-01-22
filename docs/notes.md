This file previously contained sensitive credentials (Discord webhook, GitHub PAT, Docker PAT, OpenAI/Anthropic API keys, YouTube API key, and Google OAuth secret). All values have been intentionally removed.

Do not store secrets in the repository. Use the secret managers outlined in AGENTS.md and pmoves/AGENTS.md instead (GitHub Actions secrets, Docker/Compose secrets, local env files that are never committed).

Action items (must do now):
- Rotate every credential that was present in the prior version of this file (Discord webhook, GitHub PAT, Docker PAT, OpenAI key, Anthropic key, YouTube API key, Google OAuth client secret).
- Delete any cached copies (local clones, CI artifacts, backups) that may still contain the leaked values.
- After rotation, add the new values only to GitHub/Docker secrets and local untracked env files.
