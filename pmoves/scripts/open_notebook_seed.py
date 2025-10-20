#!/usr/bin/env python3
"""
Seed Open Notebook model catalog and defaults based on available provider keys.

This helper inspects the current environment (typically populated via
`.env.local`) and registers a small set of language/embedding/audio models for
each configured provider.  It also assigns sensible defaults so the UI can be
used immediately without manual SurrealDB edits.

Supported providers mirror the upstream Esperanto factory list.  We only seed
providers when the expected API key / base URL env vars are present.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple


API_ROOT = os.environ.get("OPEN_NOTEBOOK_API_URL", "http://localhost:5055").rstrip("/")
AUTH_TOKEN = os.environ.get("OPEN_NOTEBOOK_API_TOKEN") or os.environ.get("OPEN_NOTEBOOK_PASSWORD")

if not AUTH_TOKEN:
    sys.stderr.write(
        "ERROR: Set OPEN_NOTEBOOK_API_TOKEN or OPEN_NOTEBOOK_PASSWORD before running this helper.\n"
    )
    sys.exit(2)

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


ProviderSpec = Dict[str, object]

PROVIDERS: Dict[str, ProviderSpec] = {
    "openai": {
        "env": ["OPENAI_API_KEY"],
        "models": [
            ("gpt-5-mini", "language"),
            ("gpt-5", "language"),
            ("text-embedding-3-small", "embedding"),
            ("whisper-1", "speech_to_text"),
            ("gpt-4o-mini-tts", "text_to_speech"),
        ],
        "defaults": {
            "default_chat_model": "gpt-5-mini",
            "default_tools_model": "gpt-5",
            "default_embedding_model": "text-embedding-3-small",
            "default_speech_to_text_model": "whisper-1",
            "default_text_to_speech_model": "gpt-4o-mini-tts",
        },
    },
    "groq": {
        "env": ["GROQ_API_KEY"],
        "models": [
            ("llama3-70b-8192", "language"),
            ("mixtral-8x7b-32768", "language"),
        ],
    },
    "anthropic": {
        "env": ["ANTHROPIC_API_KEY"],
        "models": [
            ("claude-3-5-sonnet-latest", "language"),
        ],
    },
    "google": {
        "env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "models": [
            ("gemini-2.0-flash", "language"),
            ("text-embedding-004", "embedding"),
            ("gemini-2.0-flash-tts", "text_to_speech"),
        ],
        "defaults": {
            "large_context_model": "gemini-2.0-flash",
        },
    },
    "mistral": {
        "env": ["MISTRAL_API_KEY"],
        "models": [
            ("mistral-large-latest", "language"),
        ],
    },
    "deepseek": {
        "env": ["DEEPSEEK_API_KEY"],
        "models": [
            ("deepseek-r1", "language"),
        ],
    },
    "openrouter": {
        "env": ["OPENROUTER_API_KEY"],
        "models": [
            ("openrouter/anthropic/claude-3-haiku", "language"),
        ],
    },
    "ollama": {
        "env": ["OLLAMA_API_BASE"],
        "models": [
            ("llama3.1", "language"),
            ("mxbai-embed-large", "embedding"),
        ],
    },
    "elevenlabs": {
        "env": ["ELEVENLABS_API_KEY"],
        "models": [
            ("eleven_turbo_v2", "text_to_speech"),
        ],
    },
    "voyage": {
        "env": ["VOYAGE_API_KEY"],
        "models": [
            ("voyage-large-2", "embedding"),
        ],
    },
    "xai": {
        "env": ["XAI_API_KEY"],
        "models": [
            ("grok-2", "language"),
        ],
    },
}


def have_provider_env(env_keys: List[str]) -> bool:
    return any(os.environ.get(key) for key in env_keys)


def request(method: str, path: str, payload: Optional[dict] = None) -> Tuple[int, str]:
    url = f"{API_ROOT}/api{path}"
    data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data_bytes, method=method, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def get_json(method: str, path: str) -> dict:
    status, body = request(method, path)
    if status >= 400:
        raise RuntimeError(f"{method} {path} failed ({status}): {body}")
    return json.loads(body) if body else {}


def post_json(path: str, payload: dict) -> dict:
    status, body = request("POST", path, payload)
    if status >= 400:
        raise RuntimeError(f"POST {path} failed ({status}): {body}")
    return json.loads(body) if body else {}


def put_json(path: str, payload: dict) -> dict:
    status, body = request("PUT", path, payload)
    if status >= 400:
        raise RuntimeError(f"PUT {path} failed ({status}): {body}")
    return json.loads(body) if body else {}


def ensure_models(models_by_provider: Dict[str, List[dict]]) -> Dict[str, dict]:
    current = get_json("GET", "/models")
    indexed = {(m["name"], m["provider"]): m for m in current}
    created: Dict[str, dict] = {}

    for provider, model_list in models_by_provider.items():
        for model in model_list:
            key = (model["name"], provider)
            if key in indexed:
                created[model["name"]] = indexed[key]
                continue
            payload = {
                "name": model["name"],
                "provider": provider,
                "type": model["type"],
            }
            created_model = post_json("/models", payload)
            created[model["name"]] = created_model
            print(f"↳ Added {provider}:{model['name']} ({model['type']})")

    return created


def update_defaults(defaults: Dict[str, str], created_models: Dict[str, dict]) -> None:
    if not defaults:
        return

    payload: Dict[str, Optional[str]] = {}
    for field, model_name in defaults.items():
        model = created_models.get(model_name)
        if model:
            payload[field] = model["id"]

    if not payload:
        return

    updated = put_json("/models/defaults", payload)
    print("✔ Updated default models:", json.dumps(updated, indent=2))


def main() -> None:
    eligible: Dict[str, List[dict]] = {}
    defaults: Dict[str, str] = {}

    for provider, spec in PROVIDERS.items():
        env_keys = spec.get("env", [])
        if not env_keys:
            continue
        if not have_provider_env(env_keys):
            continue

        model_specs = [
            {"name": name, "type": model_type}
            for name, model_type in spec.get("models", [])
        ]
        if not model_specs:
            continue
        eligible[provider] = model_specs

        defaults.update(spec.get("defaults", {}))

    if not eligible:
        print("No provider API keys detected; nothing to seed.")
        return

    created = ensure_models(eligible)

    if defaults:
        update_defaults(defaults, created)

    providers = ", ".join(sorted(eligible.keys()))
    print(f"✔ Open Notebook providers configured: {providers or 'none'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(1)
