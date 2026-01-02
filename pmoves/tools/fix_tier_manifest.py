#!/usr/bin/env python3
"""Update CHIT secrets manifest to output to tier env files."""

import yaml
from pathlib import Path

# Mapping of secret labels to their tier files
# Based on the 6-tier security architecture
TIER_MAPPING = {
    # env.tier-data: Infrastructure credentials
    "MEILI_MASTER_KEY": ["env.tier-data"],
    "MINIO_PASSWORD": ["env.tier-data"],
    "MINIO_USER": ["env.tier-data"],
    "POSTGRES_DB": ["env.tier-data"],
    "POSTGRES_HOSTNAME": ["env.tier-data"],
    "POSTGRES_PORT": ["env.tier-data"],
    "SERVICE_PASSWORD_ADMIN": ["env.tier-data"],
    "SERVICE_PASSWORD_POSTGRES": ["env.tier-data"],
    "SERVICE_USER_ADMIN": ["env.tier-data"],

    # env.tier-api: Data access APIs (internal)
    "SUPABASE_JWT_SECRET": ["env.tier-api"],

    # env.tier-llm: ALL external LLM provider API keys (security fence)
    "ANTHROPIC_API_KEY": ["env.tier-llm"],
    "COHERE_API_KEY": ["env.tier-llm"],
    "DEEPSEEK_API_KEY": ["env.tier-llm"],
    "ELEVENLABS_API_KEY": ["env.tier-llm"],
    "FIREWORKS_AI_API_KEY": ["env.tier-llm"],
    "GEMINI_API_KEY": ["env.tier-llm"],
    "GOOGLE_API_KEY": ["env.tier-llm"],
    "GROQ_API_KEY": ["env.tier-llm"],
    "MISTRAL_API_KEY": ["env.tier-llm"],
    "OPENAI_API_KEY": ["env.tier-llm"],
    "OPENAI_API_BASE": ["env.tier-llm"],
    "OPENAI_COMPATIBLE_BASE_URL": ["env.tier-llm"],
    "OPENROUTER_API_KEY": ["env.tier-llm"],
    "PERPLEXITYAI_API_KEY": ["env.tier-llm"],
    "TOGETHER_AI_API_KEY": ["env.tier-llm"],
    "VOYAGE_API_KEY": ["env.tier-llm"],
    "XAI_API_KEY": ["env.tier-llm"],

    # env.tier-llm also gets TensorZero and Ollama config
    "OLLAMA_BASE_URL": ["env.tier-llm"],
    "TENSORZERO_API_KEY": ["env.tier-llm"],

    # env.tier-agent: Agent orchestration
    "AGENT_ZERO_EVENTS_TOKEN": ["env.tier-agent"],
    "DISCORD_AVATAR_URL": ["env.tier-agent"],
    "DISCORD_USERNAME": ["env.tier-agent"],
    "DISCORD_WEBHOOK_URL": ["env.tier-agent"],
    "JELLYFIN_API_KEY": ["env.tier-agent"],
    "JELLYFIN_PUBLISHED_URL": ["env.tier-agent"],
    "JELLYFIN_URL": ["env.tier-agent"],
    "JELLYFIN_USER_ID": ["env.tier-agent"],
    "N8N_API_KEY": ["env.tier-agent"],
    "N8N_RUNNERS_AUTH_TOKEN": ["env.tier-agent"],
    "OPEN_NOTEBOOK_API_TOKEN": ["env.tier-agent"],
    "OPEN_NOTEBOOK_API_URL": ["env.tier-agent"],
    "OPEN_NOTEBOOK_PASSWORD": ["env.tier-agent"],
    "SURREAL_ADDRESS": ["env.tier-agent"],
    "SURREAL_DATABASE": ["env.tier-agent"],
    "SURREAL_NAMESPACE": ["env.tier-agent"],
    "SURREAL_PASS": ["env.tier-agent"],
    "SURREAL_PORT": ["env.tier-agent"],
    "SURREAL_URL": ["env.tier-agent"],
    "WGER_API_TOKEN": ["env.tier-agent"],
    "FIREFLY_ACCESS_TOKEN": ["env.tier-agent"],
    "FIREFLY_APP_KEY": ["env.tier-agent"],
    "FIREFLY_CMD_LN_TOKEN": ["env.tier-agent"],
    "FIREFLY_PA_TOKEN_NAME": ["env.tier-agent"],
    "FIREFLY_PORT": ["env.tier-agent"],

    # Supabase keys go to multiple tiers (api, agent, worker, media)
    "NEXT_PUBLIC_BACKEND_API_KEY": ["env.tier-agent"],
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": ["env.tier-agent"],
    "NEXT_PUBLIC_SUPABASE_URL": ["env.tier-agent"],
}


def add_tier_targets(manifest_path: Path, output_path: Path) -> None:
    """Add tier env file targets to each manifest entry."""
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    print(f"Processing {len(manifest['entries'])} entries...")

    for entry in manifest["entries"]:
        source_label = entry["source"]["label"]
        existing_targets = entry.get("targets", [])

        # Build list of existing target files (to avoid duplicates)
        existing_files = {t["file"] for t in existing_targets}

        # Determine which tier files this entry should target
        tier_files = TIER_MAPPING.get(source_label, [])

        # Add new tier targets
        for tier_file in tier_files:
            if tier_file not in existing_files:
                # Find the key to use (usually same as label)
                key = source_label
                # Special cases where key differs from label
                if source_label == "SERVICE_PASSWORD_POSTGRES":
                    key = "POSTGRES_PASSWORD"

                new_target = {"file": tier_file, "key": key}
                existing_targets.append(new_target)
                print(f"  Added {tier_file}: {key} for {source_label}")

        entry["targets"] = existing_targets

    # Write updated manifest
    with open(output_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    print(f"\nUpdated manifest written to {output_path}")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "pmoves" / "chit" / "secrets_manifest.yaml"
    output_path = repo_root / "pmoves" / "chit" / "secrets_manifest.yaml"

    print(f"Reading manifest from: {manifest_path}")
    add_tier_targets(manifest_path, output_path)
