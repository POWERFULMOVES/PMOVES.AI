#!/usr/bin/env python3
import argparse
import re
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_DEFAULT = ROOT / "env.shared"
ENV_GEN_DEFAULT = ROOT / ".env.generated"

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
    # Presign/Render webhook secrets (demo defaults; replace in production)
    "PRESIGN_SHARED_SECRET": "change_me",
    "RENDER_WEBHOOK_SHARED_SECRET": "change_me",
}

PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change_me",
    "SURREAL_USER_HERE",
    "SURREAL_PASS_HERE",
    "root",
    "pmoves4482",
}


def _normalize_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _strong_random(n_bytes: int) -> str:
    return secrets.token_urlsafe(n_bytes)


def _rand_exact_len(n_chars: int) -> str:
    s = _strong_random(max(12, n_chars))
    if len(s) < n_chars:
        s = (s * ((n_chars // len(s)) + 1))[:n_chars]
    return s[:n_chars]


def _rand_alnum(n_chars: int) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n_chars))


def _get_kv(text: str, key: str) -> str:
    m = re.search(rf"^\s*{re.escape(key)}\s*=(.*)$", text, re.M)
    raw = (m.group(1).strip() if m else "").strip()
    return _normalize_env_value(raw)


def _set_kv(text: str, key: str, value: str) -> str:
    pat = rf"^(\s*{re.escape(key)}\s*=).*$"
    if re.search(pat, text, re.M):
        return re.sub(pat, lambda m: m.group(1) + value, text, flags=re.M)
    return text + f"\n{key}={value}\n"


def _is_blank_or_placeholder(value: str) -> bool:
    normalized = _normalize_env_value(value)
    return not normalized or normalized in PLACEHOLDER_VALUES


def _first_real(text: str, keys: list[str]) -> str:
    for key in keys:
        value = _get_kv(text, key)
        if not _is_blank_or_placeholder(value):
            return value
    return ""


def _ensure_notebook_and_surreal_credentials(text: str) -> str:
    notebook_secret = _first_real(text, ["OPEN_NOTEBOOK_PASSWORD", "OPEN_NOTEBOOK_API_TOKEN"])
    if not notebook_secret:
        notebook_secret = "pm_nb_" + _strong_random(16)
    text = _set_kv(text, "OPEN_NOTEBOOK_PASSWORD", notebook_secret)
    text = _set_kv(text, "OPEN_NOTEBOOK_API_TOKEN", notebook_secret)

    surreal_user = _first_real(text, ["OPEN_NOTEBOOK_SURREAL_USER", "SURREAL_USER"])
    if not surreal_user:
        surreal_user = "pm_surreal_" + _rand_alnum(8)
    surreal_pass = _first_real(text, ["OPEN_NOTEBOOK_SURREAL_PASS", "SURREAL_PASS"])
    if not surreal_pass:
        surreal_pass = "pm_sr_" + _strong_random(16)

    text = _set_kv(text, "SURREAL_USER", surreal_user)
    text = _set_kv(text, "SURREAL_PASS", surreal_pass)
    text = _set_kv(text, "OPEN_NOTEBOOK_SURREAL_USER", surreal_user)
    text = _set_kv(text, "OPEN_NOTEBOOK_SURREAL_PASS", surreal_pass)
    return text


def upsert_env(path: Path, env_gen_path: Path, pairs: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for key, value in pairs.items():
        current = _get_kv(text, key)
        if current and current not in PLACEHOLDER_VALUES:
            continue
        text = _set_kv(text, key, value)

    # Strengthen keys if weak/short
    meili_key = _get_kv(text, "MEILI_MASTER_KEY")
    if len(meili_key) < 16:
        text = _set_kv(text, "MEILI_MASTER_KEY", _strong_random(24))

    companion_key = _get_kv(text, "INVIDIOUS_COMPANION_KEY")
    if len(companion_key) != 16:
        text = _set_kv(text, "INVIDIOUS_COMPANION_KEY", _rand_exact_len(16))

    hmac_key = _get_kv(text, "INVIDIOUS_HMAC_KEY")
    if len(hmac_key) < 32:
        text = _set_kv(text, "INVIDIOUS_HMAC_KEY", _strong_random(24))

    neo4j_password = _get_kv(text, "NEO4J_PASSWORD")
    if _is_blank_or_placeholder(neo4j_password):
        neo4j_password = "pm_" + _strong_random(16)
        text = _set_kv(text, "NEO4J_PASSWORD", neo4j_password)
    text = _set_kv(text, "NEO4J_AUTH", f"neo4j/{neo4j_password}")

    # Generate Open Notebook + Surreal credentials per install if missing.
    text = _ensure_notebook_and_surreal_credentials(text)

    path.write_text(text, encoding="utf-8")

    # Mirror NEO4J_AUTH into .env.generated for compose-only consumers.
    env_gen_path.parent.mkdir(parents=True, exist_ok=True)
    gen = env_gen_path.read_text(encoding="utf-8") if env_gen_path.exists() else ""
    gen = _set_kv(gen, "NEO4J_AUTH", f"neo4j/{neo4j_password}")
    env_gen_path.write_text(gen, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply branded env defaults.")
    parser.add_argument("--env-file", type=Path, default=ENV_DEFAULT, help="Path to env file.")
    parser.add_argument(
        "--generated-env-file",
        type=Path,
        default=ENV_GEN_DEFAULT,
        help="Path to generated env file for compose mirrors.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_path = args.env_file
    env_gen_path = args.generated_env_file
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")
    upsert_env(env_path, env_gen_path, DEFAULTS)
    print(f"Branded defaults applied to {env_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
