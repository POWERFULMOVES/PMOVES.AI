#!/usr/bin/env python3
"""
TensorZero to Supabase Model Registry Migration Script

This script parses the TensorZero TOML configuration and migrates all models,
providers, and function mappings to the Supabase model registry.

Usage:
    python migrate_tensorzero.py [--config-path /path/to/tensorzero.toml]

Environment Variables:
    SUPABASE_URL: Supabase API URL (default: http://localhost:3010)
    SUPABASE_SERVICE_KEY: Supabase service key for authentication
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import tomli


# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:3010")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Headers for Supabase REST API
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


@dataclass
class ProviderConfig:
    """Provider configuration extracted from TensorZero TOML."""

    name: str
    type: str  # openai, anthropic, ollama, vllm
    api_base: Optional[str] = None
    api_key_env_var: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ModelConfig:
    """Model configuration extracted from TensorZero TOML."""

    name: str  # TensorZero model name (alias)
    model_id: str  # Actual model name for provider
    provider_type: str  # ollama, openai_compatible, etc.
    model_type: str  # chat, embedding
    capabilities: List[str]
    context_length: Optional[int] = None
    description: Optional[str] = None


@dataclass
class FunctionMapping:
    """Function to model mapping from TensorZero TOML."""

    function_name: str
    variant_name: str
    model_name: str
    weight: float = 1.0


class TensorZeroParser:
    """Parse TensorZero TOML configuration file."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load and parse TOML configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "rb") as f:
            return tomli.load(f)

    def extract_providers(self) -> List[ProviderConfig]:
        """Extract unique provider configurations from models."""
        providers = {}
        models_config = self.config.get("models", {})
        embedding_config = self.config.get("embedding_models", {})

        # Process chat models
        for model_name, model_def in models_config.items():
            for provider_name, provider_def in model_def.get("providers", {}).items():
                key = self._provider_key(provider_def)
                if key not in providers:
                    providers[key] = self._parse_provider(provider_name, provider_def)

        # Process embedding models
        for model_name, model_def in embedding_config.items():
            for provider_name, provider_def in model_def.get("providers", {}).items():
                key = self._provider_key(provider_def)
                if key not in providers:
                    providers[key] = self._parse_provider(provider_name, provider_def)

        return list(providers.values())

    def _provider_key(self, provider_def: Dict) -> str:
        """Generate unique key for provider deduplication."""
        return f"{provider_def.get('type', 'unknown')}_{provider_def.get('api_base', '')}"

    def _parse_provider(self, name: str, provider_def: Dict) -> ProviderConfig:
        """Parse provider definition from TOML."""
        provider_type = provider_def.get("type", "openai_compatible")
        api_base = provider_def.get("api_base", "")
        api_key = provider_def.get("api_key_location", "")

        # Normalize provider type
        if provider_type == "openai":
            if "ollama" in api_base.lower():
                provider_type = "ollama"
            elif api_base.startswith("https://api.anthropic.com"):
                provider_type = "anthropic"
            else:
                provider_type = "openai_compatible"

        # Extract env var name if specified
        api_key_env_var = None
        if api_key and api_key.startswith("env::"):
            api_key_env_var = api_key[5:]
        elif api_key == "none":
            api_key_env_var = None

        # Generate description
        description = f"{name} - {provider_type}"
        if api_base:
            host = api_base.replace("https://", "").replace("http://", "").split("/")[0]
            description = f"{name} ({host})"

        return ProviderConfig(
            name=name,
            type=provider_type,
            api_base=api_base or None,
            api_key_env_var=api_key_env_var,
            description=description,
        )

    def extract_models(self) -> List[ModelConfig]:
        """Extract all model configurations."""
        models = []

        # Process chat models
        for model_name, model_def in self.config.get("models", {}).items():
            for provider_name, provider_def in model_def.get("providers", {}).items():
                model_type = provider_def.get("type", "openai")
                is_ollama = "ollama" in provider_def.get("api_base", "").lower()

                models.append(
                    ModelConfig(
                        name=model_name,
                        model_id=provider_def.get("model_name", model_name),
                        provider_type="ollama" if is_ollama else "openai_compatible",
                        model_type="chat",
                        capabilities=self._infer_capabilities(model_name, provider_def.get("model_name", "")),
                        context_length=self._infer_context_length(provider_def.get("model_name", "")),
                        description=f"Chat model: {model_name}",
                    )
                )

        # Process embedding models
        for model_name, model_def in self.config.get("embedding_models", {}).items():
            for provider_name, provider_def in model_def.get("providers", {}).items():
                models.append(
                    ModelConfig(
                        name=model_name,
                        model_id=provider_def.get("model_name", model_name),
                        provider_type="openai_compatible",
                        model_type="embedding",
                        capabilities=["embeddings"],
                        context_length=512,  # Typical for embeddings
                        description=f"Embedding model: {model_name}",
                    )
                )

        return models

    def _infer_capabilities(self, model_name: str, model_id: str) -> List[str]:
        """Infer model capabilities from name patterns."""
        capabilities = ["chat"]

        model_lower = model_name.lower() + " " + model_id.lower()

        if any(x in model_lower for x in ["vl", "vision", "image", "multimodal"]):
            capabilities.append("vision")

        if any(x in model_lower for x in ["coder", "code", "function"]):
            capabilities.append("function_calling")

        if any(x in model_lower for x in ["tool", "agent"]):
            capabilities.extend(["function_calling", "tool_use"])

        if "rerank" in model_lower:
            capabilities.append("reranking")

        return capabilities

    def _infer_context_length(self, model_id: str) -> Optional[int]:
        """Infer context length from model identifier."""
        model_lower = model_id.lower()

        # Known context lengths
        if "32b" in model_lower or "70b" in model_lower:
            return 32768
        elif "14b" in model_lower:
            return 32768
        elif "8b" in model_lower:
            return 32768
        elif "7b" in model_lower or "mini" in model_lower:
            return 16384
        elif "128k" in model_lower:
            return 128000
        elif "32k" in model_lower:
            return 32000

        return None

    def extract_function_mappings(self) -> List[FunctionMapping]:
        """Extract function to model mappings."""
        mappings = []

        for func_name, func_def in self.config.get("functions", {}).items():
            for variant_name, variant_def in func_def.get("variants", {}).items():
                model_name = variant_def.get("model", "")
                weight = variant_def.get("weight", 1.0)

                if model_name:
                    mappings.append(
                        FunctionMapping(
                            function_name=func_name,
                            variant_name=variant_name,
                            model_name=model_name,
                            weight=weight,
                        )
                    )

        return mappings


class SupabaseMigrator:
    """Migrate parsed TensorZero config to Supabase."""

    def __init__(self):
        self.base_url = SUPABASE_URL.rstrip("/")
        self.provider_ids: Dict[str, str] = {}
        self.model_ids: Dict[str, str] = {}

    async def migrate(
        self,
        providers: List[ProviderConfig],
        models: List[ModelConfig],
        mappings: List[FunctionMapping],
    ) -> Dict[str, int]:
        """Run full migration and return statistics."""
        stats = {
            "providers_created": 0,
            "models_created": 0,
            "mappings_created": 0,
            "errors": [],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Migrate providers first
            for provider in providers:
                try:
                    provider_id = await self._create_provider(client, provider)
                    if provider_id:
                        self.provider_ids[provider.name] = provider_id
                        stats["providers_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"Provider {provider.name}: {e}")

            # Migrate models
            for model in models:
                try:
                    model_id = await self._create_model(client, model)
                    if model_id:
                        self.model_ids[model.name] = model_id
                        stats["models_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"Model {model.name}: {e}")

            # Migrate function mappings
            for mapping in mappings:
                try:
                    if await self._create_mapping(client, mapping):
                        stats["mappings_created"] += 1
                except Exception as e:
                    stats["errors"].append(f"Mapping {mapping.function_name}/{mapping.variant_name}: {e}")

        return stats

    async def _create_provider(self, client: httpx.AsyncClient, provider: ProviderConfig) -> Optional[str]:
        """Create a provider in Supabase."""
        url = f"{self.base_url}/rest/v1/model_providers"

        data = {
            "name": provider.name,
            "type": provider.type,
            "api_base": provider.api_base,
            "api_key_env_var": provider.api_key_env_var,
            "description": provider.description,
            "active": True,
        }

        response = await client.post(url, json=data, headers=HEADERS)

        if response.status_code in (200, 201):
            result = response.json()
            return result[0]["id"] if isinstance(result, list) else result.get("id")
        elif response.status_code == 409:
            # Provider exists, fetch ID
            return await self._get_provider_by_name(client, provider.name)

        print(f"Warning: Failed to create provider {provider.name}: {response.status_code} {response.text}")
        return None

    async def _get_provider_by_name(self, client: httpx.AsyncClient, name: str) -> Optional[str]:
        """Get existing provider ID by name."""
        url = f"{self.base_url}/rest/v1/model_providers"
        params = {"name": f"eq.{name}", "limit": "1"}
        response = await client.get(url, params=params, headers=HEADERS)

        if response.status_code == 200 and response.json():
            return response.json()[0]["id"]
        return None

    async def _create_model(self, client: httpx.AsyncClient, model: ModelConfig) -> Optional[str]:
        """Create a model in Supabase."""
        # Find provider ID (use default provider if no match)
        provider_id = self.provider_ids.get(model.provider_type)
        if not provider_id:
            # Try to find or create a default provider for this type
            provider_id = await self._get_or_create_default_provider(client, model.provider_type)
            if not provider_id:
                print(f"Warning: Could not find provider for {model.provider_type}, skipping model {model.name}")
                return None

        url = f"{self.base_url}/rest/v1/models"

        data = {
            "provider_id": provider_id,
            "name": model.name,
            "model_id": model.model_id,
            "model_type": model.model_type,
            "capabilities": model.capabilities,
            "vram_mb": 0,  # Will be updated by GPU Orchestrator
            "context_length": model.context_length,
            "description": model.description,
            "active": True,
        }

        response = await client.post(url, json=data, headers=HEADERS)

        if response.status_code in (200, 201):
            result = response.json()
            return result[0]["id"] if isinstance(result, list) else result.get("id")
        elif response.status_code == 409:
            # Model exists, fetch ID
            return await self._get_model_by_id(client, model.model_id)

        print(f"Warning: Failed to create model {model.name}: {response.status_code} {response.text}")
        return None

    async def _get_or_create_default_provider(self, client: httpx.AsyncClient, provider_type: str) -> Optional[str]:
        """Get or create a default provider for a type."""
        default_providers = {
            "ollama": {
                "name": "ollama",
                "type": "ollama",
                "api_base": "http://pmoves-ollama:11434",
                "description": "Local Ollama instance",
            },
            "openai_compatible": {
                "name": "openai_compatible_default",
                "type": "openai_compatible",
                "api_base": None,
                "description": "OpenAI-compatible provider",
            },
        }

        config = default_providers.get(provider_type)
        if not config:
            return None

        # Try to get existing
        existing_id = await self._get_provider_by_name(client, config["name"])
        if existing_id:
            self.provider_ids[config["name"]] = existing_id
            return existing_id

        # Create new
        url = f"{self.base_url}/rest/v1/model_providers"
        response = await client.post(url, json={**config, "active": True}, headers=HEADERS)

        if response.status_code in (200, 201):
            result = response.json()
            provider_id = result[0]["id"] if isinstance(result, list) else result.get("id")
            self.provider_ids[config["name"]] = provider_id
            return provider_id

        return None

    async def _get_model_by_id(self, client: httpx.AsyncClient, model_id: str) -> Optional[str]:
        """Get existing model ID by model_id."""
        url = f"{self.base_url}/rest/v1/models"
        params = {"model_id": f"eq.{model_id}", "limit": "1"}
        response = await client.get(url, params=params, headers=HEADERS)

        if response.status_code == 200 and response.json():
            return response.json()[0]["id"]
        return None

    async def _create_mapping(self, client: httpx.AsyncClient, mapping: FunctionMapping) -> bool:
        """Create a function mapping in Supabase."""
        model_id = self.model_ids.get(mapping.model_name)
        if not model_id:
            print(f"Warning: Model {mapping.model_name} not found for mapping {mapping.function_name}/{mapping.variant_name}")
            return False

        url = f"{self.base_url}/rest/v1/service_model_mappings"

        data = {
            "service_name": "tensorzero",
            "function_name": mapping.function_name,
            "model_id": model_id,
            "variant_name": mapping.variant_name,
            "priority": 5,
            "weight": mapping.weight,
        }

        response = await client.post(url, json=data, headers=HEADERS)

        if response.status_code in (200, 201):
            return True
        elif response.status_code == 409:
            return True  # Already exists

        print(f"Warning: Failed to create mapping {mapping.function_name}/{mapping.variant_name}: {response.status_code}")
        return False


async def main():
    """Main migration entry point."""
    parser = argparse.ArgumentParser(description="Migrate TensorZero config to Supabase")
    parser.add_argument(
        "--config-path",
        default="/home/pmoves/PMOVES.AI/pmoves/tensorzero/config/tensorzero.toml",
        help="Path to tensorzero.toml file",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse config without migrating")

    args = parser.parse_args()

    # Check Supabase credentials
    if not SUPABASE_SERVICE_KEY:
        print("Error: SUPABASE_SERVICE_KEY environment variable required")
        sys.exit(1)

    print(f"📂 Parsing TensorZero config: {args.config_path}")

    # Parse TensorZero config
    tz_parser = TensorZeroParser(args.config_path)

    providers = tz_parser.extract_providers()
    print(f"   Found {len(providers)} unique providers")

    models = tz_parser.extract_models()
    print(f"   Found {len(models)} models ({sum(1 for m in models if m.model_type == 'chat')} chat, {sum(1 for m in models if m.model_type == 'embedding')} embedding)")

    mappings = tz_parser.extract_function_mappings()
    print(f"   Found {len(mappings)} function mappings")

    if args.dry_run:
        print("\n🔍 DRY RUN - No migration performed")
        print("\nProviders:")
        for p in providers[:5]:
            print(f"  - {p.name} ({p.type}): {p.api_base}")
        if len(providers) > 5:
            print(f"  ... and {len(providers) - 5} more")
        print("\nModels (first 10):")
        for m in models[:10]:
            print(f"  - {m.name} -> {m.model_id} ({m.model_type})")
        if len(models) > 10:
            print(f"  ... and {len(models) - 10} more")
        return

    # Run migration
    print(f"\n🚀 Starting migration to Supabase at {SUPABASE_URL}")

    migrator = SupabaseMigrator()
    stats = await migrator.migrate(providers, models, mappings)

    # Print results
    print("\n✅ Migration complete!")
    print(f"   Providers created: {stats['providers_created']}")
    print(f"   Models created: {stats['models_created']}")
    print(f"   Mappings created: {stats['mappings_created']}")

    if stats["errors"]:
        print(f"\n⚠️  Errors encountered: {len(stats['errors'])}")
        for error in stats["errors"][:5]:
            print(f"   - {error}")
        if len(stats["errors"]) > 5:
            print(f"   ... and {len(stats['errors']) - 5} more")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
