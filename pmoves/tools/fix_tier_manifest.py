#!/usr/bin/env python3
"""DEPRECATED -- do not extend. Update CHIT secrets manifest to output to tier env files.

WHY THIS IS A WORKAROUND, NOT A MECHANISM
-----------------------------------------
This script carries a hardcoded TIER_MAPPING and rewrites the secrets manifest
from it. Nothing invokes it: it is referenced by no Make target and no workflow
(verified 2026-08-25). So the manifest's tier routing is a frozen snapshot of
whatever this dict said the last time a human ran it by hand.

The same routing is ALSO encoded, separately, in tools/generate_chit_v2.py --
another orphan with its own map. Two hardcoded copies of one fact, neither
executed by the pipeline, both able to drift from the manifest they describe and
from each other.

The observable consequence: a provider key can be present in .example, present
in both maps, and absent from the runtime tier file, so every consumer reading
that tier gets nothing while every declaration says it should work. Z_AI_API_KEY
did exactly that -- crush-env.sh loads env.tier-llm, the key is mapped to
env.tier-llm here and in generate_chit_v2, and sourcing that loader yields an
empty value. SPARK hit the same shape with Hermes. An operator ended up pasting
an API key into ~/.config/crush/crush.json by hand.

RETIREMENT PATH
---------------
1. Reconcile TIER_MAPPING and generate_chit_v2's map INTO secrets_manifest_v2.yaml
   so the manifest declares its own tier outputs -- one declaration, in the file
   the funnel already reads.
2. Make `secrets-funnel-sync` honour that declaration for every secret, so adding
   a provider needs no script edit.
3. Ratchet `check_tier_envs.py --strict` into the pipeline once the backlog of
   drifted keys is cleared, so a future gap fails instead of being reported.
4. Delete this file and generate_chit_v2's map.

Until step 1 lands, adding a key here does not make it reach a node -- it only
makes the declaration look complete. Prefer fixing the manifest directly.
"""

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
    "ALIBABA_PRO_CODING_PLAN": ["env.tier-llm"],
    "ANTHROPIC_API_KEY": ["env.tier-llm"],
    "COHERE_API_KEY": ["env.tier-llm"],
    "DEEPSEEK_API_KEY": ["env.tier-llm"],
    "ELEVENLABS_API_KEY": ["env.tier-llm"],
    "FIREWORKS_AI_API_KEY": ["env.tier-llm"],
    "GEMINI_API_KEY": ["env.tier-llm"],
    "GOOGLE_API_KEY": ["env.tier-llm"],
    "GROQ_API_KEY": ["env.tier-llm"],
    "HF_TOKEN": ["env.tier-llm"],
    "KILOCODE_API_KEY": ["env.tier-llm"],
    "MISTRAL_API_KEY": ["env.tier-llm"],
    "MOONSHOT_API_KEY": ["env.tier-llm"],
    "OPENAI_API_KEY": ["env.tier-llm"],
    "OPENAI_API_BASE": ["env.tier-llm"],
    "OPENAI_COMPATIBLE_BASE_URL": ["env.tier-llm"],
    "OPENROUTER_API_KEY": ["env.tier-llm"],
    "PERPLEXITYAI_API_KEY": ["env.tier-llm"],
    "TOGETHER_AI_API_KEY": ["env.tier-llm"],
    "VOYAGE_API_KEY": ["env.tier-llm"],
    "XAI_API_KEY": ["env.tier-llm"],
    "Z_AI_API_KEY": ["env.tier-llm"],
    "DASHSCOPE_API_KEY": ["env.tier-llm"],

    # env.tier-llm also gets TensorZero and Ollama config
    "OLLAMA_BASE_URL": ["env.tier-llm"],
    "OLLAMA_API_KEY": ["env.tier-llm"],
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
