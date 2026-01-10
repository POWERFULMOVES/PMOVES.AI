#!/usr/bin/env python3
import os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "env.shared"
ENV_GEN = ROOT / ".env.generated"

DEFAULTS = {
    # Storage / presign
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
    # Search (will be strengthened below if too short)
    "MEILI_MASTER_KEY": "master_key",
    # Geometry graph (compose reads NEO4J_AUTH; we set URL, user, and generate password if missing)
    "NEO4J_URL": "bolt://neo4j:7687",
    "NEO4J_USER": "neo4j",
    # Invidious companion (keys will be strengthened below)
    "INVIDIOUS_HMAC_KEY": "localhack",
    "INVIDIOUS_COMPANION_KEY": "localhack",
    # REST bases
    "SUPA_REST_URL": "http://host.docker.internal:54321/rest/v1",
    "SUPA_REST_INTERNAL_URL": "http://host.docker.internal:54321/rest/v1",
    # Presign/Render webhook secrets (demo defaults – replace for production)
    "PRESIGN_SHARED_SECRET": "change_me",
    "RENDER_WEBHOOK_SHARED_SECRET": "change_me",
}

def _strong_random(n_bytes: int) -> str:
    try:
        import secrets
        return secrets.token_urlsafe(n_bytes)
    except Exception:
        # Fallback to a simple hex string of requested bytes
        import os
        return os.urandom(n_bytes).hex()


def _rand_exact_len(n_chars: int) -> str:
    # URL-safe base64 may overshoot; trim/pad deterministically
    s = _strong_random(max(12, n_chars))
    if len(s) < n_chars:
        s = (s * ((n_chars // len(s)) + 1))[:n_chars]
    return s[:n_chars]


def _set_kv(text: str, key: str, value: str) -> str:
    pat = rf"^(\s*{re.escape(key)}\s*=).*$"
    if re.search(pat, text, re.M):
        return re.sub(pat, lambda m: m.group(1) + value, text, flags=re.M)
    else:
        return text + f"\n{key}={value}\n"


def upsert_env(path: Path, pairs: dict) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for k, v in pairs.items():
        if re.search(rf"^\s*{re.escape(k)}\s*=.*$", text, re.M):
            # keep existing non-empty values
            m = re.search(rf"^\s*{re.escape(k)}\s*=(.*)$", text, re.M)
            current = (m.group(1).strip() if m else "").strip()
            if current:
                continue
            text = _set_kv(text, k, v)
        else:
            text += f"\n{k}={v}\n"

    # Strengthen keys if weak/short
    # Meilisearch requires >= 16 bytes; use a 32+ char token when short
    m = re.search(r"^\s*MEILI_MASTER_KEY\s*=(.*)$", text, re.M)
    if not m or len(m.group(1).strip()) < 16:
        text = _set_kv(text, "MEILI_MASTER_KEY", _strong_random(24))

    # Invidious companion requires exactly 16 chars for SERVER_SECRET_KEY
    m = re.search(r"^\s*INVIDIOUS_COMPANION_KEY\s*=(.*)$", text, re.M)
    if not m or len(m.group(1).strip()) != 16:
        key16 = _rand_exact_len(16)
        text = _set_kv(text, "INVIDIOUS_COMPANION_KEY", key16)

    # Prefer longer HMAC key for Invidious proper
    m = re.search(r"^\s*INVIDIOUS_HMAC_KEY\s*=(.*)$", text, re.M)
    if not m or len(m.group(1).strip()) < 32:
        text = _set_kv(text, "INVIDIOUS_HMAC_KEY", _strong_random(24))
    # Ensure NEO4J_PASSWORD exists; generate if missing/empty
    pwdm = re.search(r"^\s*NEO4J_PASSWORD\s*=(.*)$", text, re.M)
    needs_pw = True
    if pwdm:
        current = pwdm.group(1).strip()
        if current:
            needs_pw = False
    if needs_pw:
        try:
            import secrets
            neo_pw = "pm_" + secrets.token_urlsafe(16)
        except Exception:
            neo_pw = "pmovesLocal!"  # fallback
        if pwdm:
            text = re.sub(r"^(\s*NEO4J_PASSWORD\s*=).*$", rf"\1 {neo_pw}", text, flags=re.M)
        else:
            text += f"\nNEO4J_PASSWORD={neo_pw}\n"
    neo4j_pw = re.search(r"^\s*NEO4J_PASSWORD\s*=(.*)$", text, re.M).group(1).strip()
    text = _set_kv(text, "NEO4J_AUTH", f"neo4j/{neo4j_pw}")
    path.write_text(text, encoding="utf-8")
    # Mirror NEO4J_AUTH into .env.generated for compose-only consumers
    gen = ENV_GEN.read_text(encoding="utf-8") if ENV_GEN.exists() else ""
    gen = _set_kv(gen, "NEO4J_AUTH", f"neo4j/{neo4j_pw}")
    ENV_GEN.write_text(gen, encoding="utf-8")

def main() -> int:
    ENV.parent.mkdir(parents=True, exist_ok=True)
    if not ENV.exists():
        ENV.write_text("", encoding="utf-8")
    upsert_env(ENV, DEFAULTS)
    print(f"✔ Branded defaults applied to {ENV}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
