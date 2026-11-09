#!/usr/bin/env python3
"""One-shot env.shared fix for lane 3 supabase-stack-default-up.

Replaces ${SERVICE_ROLE_KEY} / ${ANON_KEY} / ${JWT_SECRET} references
with literal values from env.tier-supabase, so docker compose env_file
interpolation works without sourcing with-env.sh first.

Also adds POSTGRES_PASSWORD_URLENCODED so gotrue/postgrest can parse
the password in GOTRUE_DB_DATABASE_URL / PGRST_DB_URI without splitting
on the `/` character.
"""
from pathlib import Path
import re
import urllib.parse

repo = Path(__file__).resolve().parents[1]  # pmoves/
env_shared = repo / "env.shared"
env_tier_supa = repo / "env.tier-supabase"

# Read the canonical secrets from env.tier-supabase
tier_text = env_tier_supa.read_text(encoding="utf-8")
def grab(key):
    m = re.search(rf"^{key}=(.*)$", tier_text, re.MULTILINE)
    return m.group(1).strip() if m else None

jwt_secret = grab("JWT_SECRET")
anon_key = grab("ANON_KEY")
service_role_key = grab("SERVICE_ROLE_KEY")
pg_password = grab("POSTGRES_PASSWORD")

assert jwt_secret and anon_key and service_role_key and pg_password, "missing keys in env.tier-supabase"

# URL-encode the password for use in connection URIs
pg_password_urlencoded = urllib.parse.quote(pg_password, safe="")

# Read env.shared
text = env_shared.read_text(encoding="utf-8")
original = text

# Replace ${SERVICE_ROLE_KEY} with literal service_role_key
text = re.sub(r"\$\{SERVICE_ROLE_KEY\}", service_role_key, text)
# Replace ${ANON_KEY} with literal anon_key
text = re.sub(r"\$\{ANON_KEY\}", anon_key, text)
# Replace ${JWT_SECRET} with literal jwt_secret
text = re.sub(r"\$\{JWT_SECRET\}", jwt_secret, text)

# Set SUPABASE_SERVICE_KEY (was empty) so model-registry compose interpolation succeeds
text = re.sub(r"^SUPABASE_SERVICE_KEY=$", f"SUPABASE_SERVICE_KEY={service_role_key}", text, flags=re.MULTILINE)

# Set POSTGRES_PASSWORD_URLENCODED for safe inclusion in URLs
if "POSTGRES_PASSWORD_URLENCODED=" not in text:
    # Add after POSTGRES_PASSWORD= line
    text = re.sub(
        r"^(POSTGRES_PASSWORD=.*)$",
        rf"\1\nPOSTGRES_PASSWORD_URLENCODED={pg_password_urlencoded}",
        text,
        flags=re.MULTILINE,
        count=1,
    )

if text == original:
    print("NO CHANGES (already in target state)")
else:
    env_shared.write_text(text, encoding="utf-8")
    print(f"OK updated env.shared: 3 {{{{}}}}-refs replaced, SUPABASE_SERVICE_KEY set, POSTGRES_PASSWORD_URLENCODED={pg_password_urlencoded[:24]}...")
