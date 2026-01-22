# Docker DNS Case Sensitivity

**Date:** 2025-12-22
**Source:** PR #345 CodeRabbit review

## Issue

Mixed hostname casing in docker-compose.yml caused inconsistent DNS resolution:
- `supabase_kong_PMOVES.AI` (uppercase)
- `supabase_kong_pmoves.ai` (lowercase)

Docker DNS behavior varies by configuration - some resolve case-insensitively, others don't.

## Pattern

**Always use lowercase for Docker hostnames.**

```yaml
# Bad - inconsistent casing
- SUPABASE_URL=http://supabase_kong_PMOVES.AI:8000
- SUPABASE_REALTIME_URL=ws://supabase_kong_PMOVES.AI:8000/realtime/v1

# Good - consistent lowercase
- SUPABASE_URL=http://supabase_kong_pmoves.ai:8000
- SUPABASE_REALTIME_URL=ws://supabase_kong_pmoves.ai:8000/realtime/v1
```

## Detection

```bash
# Find mixed casing in docker-compose files
grep -n "supabase_kong" pmoves/docker-compose.yml | sort -u
```

## Fix

Use `replace_all` to normalize:
```bash
sed -i 's/supabase_kong_PMOVES\.AI/supabase_kong_pmoves.ai/g' pmoves/docker-compose.yml
```

## Related

- `.claude/learnings/docker-entrypoint-patterns-2025.md`
