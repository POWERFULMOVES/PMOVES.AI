#!/usr/bin/env python3
"""Generate CHIT secrets_manifest_v2.yaml with tier mappings and GitHub/Docker targets."""

from pathlib import Path
import yaml

# Tier mapping for each secret
TIER_MAPPING = {
    # Tier 1: Data (infrastructure credentials)
    "POSTGRES_PASSWORD": "data",
    "POSTGRES_DB": "data",
    "POSTGRES_HOSTNAME": "data",
    "POSTGRES_PORT": "data",
    "NEO4J_AUTH": "data",
    "MEILI_MASTER_KEY": "data",
    "MINIO_PASSWORD": "data",
    "MINIO_USER": "data",
    "SERVICE_PASSWORD_ADMIN": "data",
    "SERVICE_PASSWORD_POSTGRES": "data",
    "SERVICE_USER_ADMIN": "data",
    "CHIT_PASSPHRASE": "data",

    # Tier 2: API (internal service URLs)
    "SUPABASE_JWT_SECRET": "api",
    "SUPABASE_SERVICE_ROLE_KEY": "api",
    "PRESIGN_SHARED_SECRET": "api",
    "GH_PAT_PUBLISH": "api",
    "GHCR_USERNAME": "api",
    "DOCKERHUB_PAT": "api",
    "DOCKERHUB_USERNAME": "api",

    # Tier 3: LLM (external provider keys)
    "OPENAI_API_KEY": "llm",
    "OPENAI_API_BASE": "llm",
    "OPENAI_COMPATIBLE_BASE_URL": "llm",
    "ANTHROPIC_API_KEY": "llm",
    "GEMINI_API_KEY": "llm",
    "GOOGLE_API_KEY": "llm",
    "GROQ_API_KEY": "llm",
    "MISTRAL_API_KEY": "llm",
    "COHERE_API_KEY": "llm",
    "DEEPSEEK_API_KEY": "llm",
    "TOGETHER_AI_API_KEY": "llm",
    "OPENROUTER_API_KEY": "llm",
    "PERPLEXITYAI_API_KEY": "llm",
    "XAI_API_KEY": "llm",
    "VOYAGE_API_KEY": "llm",
    "ELEVENLABS_API_KEY": "llm",
    "FIREWORKS_AI_API_KEY": "llm",
    "OLLAMA_BASE_URL": "llm",
    "TENSORZERO_API_KEY": "llm",

    # Tier 4: Media (media processing)
    "JELLYFIN_API_KEY": "media",
    "JELLYFIN_PUBLISHED_URL": "media",
    "JELLYFIN_URL": "media",
    "JELLYFIN_USER_ID": "media",
    "REPLICATE_API_TOKEN": "media",
    "TINIFY_API_KEY": "media",
    "CLOUDINARY_API_KEY": "media",
    "CLOUDINARY_API_SECRET": "media",
    "CLOUDINARY_CLOUD_NAME": "media",
    "AIRTABLE_API_KEY": "media",
    "AIRTABLE_BASE_ID": "media",

    # Tier 5: Agent (service coordination)
    "AGENT_ZERO_EVENTS_TOKEN": "agent",
    "DISCORD_AVATAR_URL": "agent",
    "DISCORD_USERNAME": "agent",
    "DISCORD_WEBHOOK_URL": "agent",
    "FIREFLY_ACCESS_TOKEN": "agent",
    "FIREFLY_APP_KEY": "agent",
    "FIREFLY_CMD_LN_TOKEN": "agent",
    "FIREFLY_PA_TOKEN_NAME": "agent",
    "FIREFLY_PORT": "agent",
    "N8N_API_KEY": "agent",
    "N8N_RUNNERS_AUTH_TOKEN": "agent",
    "NEXT_PUBLIC_BACKEND_API_KEY": "agent",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "agent",
    "NEXT_PUBLIC_SUPABASE_URL": "agent",
    "OPEN_NOTEBOOK_API_TOKEN": "agent",
    "OPEN_NOTEBOOK_API_URL": "agent",
    "OPEN_NOTEBOOK_PASSWORD": "agent",
    "SURREAL_ADDRESS": "agent",
    "SURREAL_DATABASE": "agent",
    "SURREAL_NAMESPACE": "agent",
    "SURREAL_PASS": "agent",
    "SURREAL_PORT": "agent",
    "SURREAL_URL": "agent",
    "SURREAL_USER": "agent",
    "VALID_API_KEYS": "agent",
    "WGER_API_TOKEN": "agent",
    "TAILSCALE_AUTHKEY": "agent",
    "TELEGRAM_BOT_TOKEN": "agent",
    "CLAUDE_SESSION_CHANNEL_ID": "agent",
    "HOSTINGER_API_TOKEN": "agent",
    "HOSTINGER_SSH_PRIVATE_KEY": "agent",
    "HOSTINGER_SSH_HOST": "agent",
    "HOSTINGER_SSH_USER": "agent",
}

def generate_docker_secret_name(label: str) -> str:
    """Generate Docker secret name from label."""
    return f"pmoves_{label.lower()}"

def main():
    manifest_path = Path(__file__).parent.parent / "chit" / "secrets_manifest.yaml"
    v2_path = Path(__file__).parent.parent / "chit" / "secrets_manifest_v2.yaml"

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Update to version 2
    manifest["version"] = 2
    manifest["tier_layout"] = True
    manifest["github_sync"] = True
    manifest["docker_secrets"] = True

    # Add tier field and additional targets to each entry
    for entry in manifest["entries"]:
        label = entry["source"]["label"]
        tier = TIER_MAPPING.get(label, "agent")  # Default to agent if not mapped
        entry["tier"] = tier

        # Add tier file target if not already present
        has_tier_target = any("tier-" in t.get("file", "") for t in entry["targets"])
        if not has_tier_target:
            tier_file = f"env.tier-{tier}"
            entry["targets"].append({"file": tier_file, "key": label})

        # Add GitHub secret target
        entry["targets"].append({"github_secret": label})

        # Add Docker secret target
        docker_secret = generate_docker_secret_name(label)
        entry["targets"].append({"docker_secret": docker_secret})

    # Write v2 manifest
    with open(v2_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    print(f"Generated {v2_path} with {len(manifest['entries'])} entries")
    print(f"Version: {manifest['version']}")
    print(f"Tier layout: {manifest['tier_layout']}")
    print(f"GitHub sync: {manifest['github_sync']}")
    print(f"Docker secrets: {manifest['docker_secrets']}")

if __name__ == "__main__":
    main()
