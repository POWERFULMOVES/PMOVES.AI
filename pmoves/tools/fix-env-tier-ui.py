#!/usr/bin/env python3
"""Set SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET in env.tier-ui
to the real values from env.tier-supabase (lane 3 supabase-stack-default-up fix).

env.tier-ui's empty values override env.shared's values when both are loaded via
docker compose env_file (last file wins). So we need real values here.
"""
from pathlib import Path
import re

repo = Path(__file__).resolve().parents[1]  # pmoves/
env_tier_ui = repo / "env.tier-ui"
env_tier_supa = repo / "env.tier-supabase"

# Read the canonical secrets
tier_text = env_tier_supa.read_text(encoding="utf-8")
def grab(key):
    m = re.search(rf"^{key}=(.*)$", tier_text, re.MULTILINE)
    return m.group(1).strip() if m else None

jwt_secret = grab("JWT_SECRET")
anon_key = grab("ANON_KEY")
service_role_key = grab("SERVICE_ROLE_KEY")

assert jwt_secret and anon_key and service_role_key

# Read env.tier-ui
text = env_tier_ui.read_text(encoding="utf-8")
original = text

# Replace empty SUPABASE_ANON_KEY= with real value
text = re.sub(
    r"^SUPABASE_ANON_KEY=$",
    f"SUPABASE_ANON_KEY={anon_key}",
    text,
    flags=re.MULTILINE,
)
text = re.sub(
    r"^SUPABASE_SERVICE_ROLE_KEY=$",
    f"SUPABASE_SERVICE_ROLE_KEY={service_role_key}",
    text,
    flags=re.MULTILINE,
)
text = re.sub(
    r"^SUPABASE_JWT_SECRET=$",
    f"SUPABASE_JWT_SECRET={jwt_secret}",
    text,
    flags=re.MULTILINE,
)

if text == original:
    print("NO CHANGES")
else:
    env_tier_ui.write_text(text, encoding="utf-8")
    print(f"OK updated env.tier-ui with real SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET")
