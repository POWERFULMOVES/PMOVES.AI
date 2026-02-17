Bootstrap tier env files for first-time setup or after a fresh clone.

This creates missing `env.tier-*` files from their `.example` counterparts and populates them with defaults from `env.shared` and `.env.local`.

## When to Use

- **First-time clone** — no tier files exist yet
- **After adding a new tier** — `.example` exists but runtime file doesn't
- **CI environments** — need skeleton tier files for config validation

## Order of Operations

```
1. bootstrap-tier-envs   — Create missing env.tier-* from .example files
2. populate-tier-envs    — Fill tier files with defaults from env.shared / .env.local
3. secrets-funnel        — (Optional) Regenerate from CHIT source for full production values
```

## Implementation

Execute the following steps:

1. **Ensure env.shared exists:**
   ```bash
   make -C pmoves ensure-env-shared
   ```

2. **Bootstrap and populate tier files:**
   ```bash
   make -C pmoves bootstrap-tier-envs && make -C pmoves populate-tier-envs
   ```

   `bootstrap-tier-envs` creates any missing tier files from `.example` templates.
   `populate-tier-envs` merges defaults from `env.shared` into them.

3. **Verify all tier files exist:**
   ```bash
   python pmoves/tools/check_tier_envs.py
   ```

   Should print `OK: All tier env files exist.`

4. **(Recommended) Run full secrets funnel to get production values:**
   ```bash
   make -C pmoves secrets-funnel
   ```

   The bootstrap gives you skeleton files; the secrets funnel fills them with real values from your CHIT bundle.

## Notes

- Tiers: `data`, `supabase`, `api`, `llm`, `worker`, `media`, `agent`, `ui`
- `.example` files are checked into git; runtime files are gitignored
- `populate-tier-envs` depends on `bootstrap-tier-envs` (runs it automatically)
- For production deployments, always follow up with `/deploy:secrets-funnel`
