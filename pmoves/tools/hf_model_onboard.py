#!/usr/bin/env python3
"""
HuggingFace Model Onboarding Pipeline

Fetches model card from HF Hub, extracts metadata,
generates CGP-compatible agent-card fragment, and
optionally upserts to Supabase persona_framework.

Usage:
    python pmoves/tools/hf_model_onboard.py MODEL_ID [--dry-run] [--json]

Make target:
    make -C pmoves hf-onboard MODEL=org/model-name

Examples:
    python pmoves/tools/hf_model_onboard.py Qwen/Qwen2.5-7B-Instruct
    python pmoves/tools/hf_model_onboard.py meta-llama/Llama-3.1-8B-Instruct --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ModelCard:
    """Extracted model card metadata."""

    model_id: str
    name: str
    author: str
    pipeline_tag: Optional[str] = None
    task: Optional[str] = None
    params: Optional[int] = None
    context_length: Optional[int] = None
    license: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    downloads: int = 0
    likes: int = 0
    library_name: Optional[str] = None
    hf_url: str = ""
    created_at: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass
class AgentCardFragment:
    """CGP-compatible agent card fragment for a model binding."""

    version: str = "cgp.v2"
    type: str = "model_binding"
    model_id: str = ""
    name: str = ""
    author: str = ""
    task: Optional[str] = None
    params: Optional[int] = None
    context_length: Optional[int] = None
    license: Optional[str] = None
    tier: str = "medium"
    capabilities: List[str] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)
    hf_url: str = ""
    checksum: str = ""
    onboarded_at: str = ""


def classify_tier(params: Optional[int]) -> str:
    """Classify model into hardware tier based on parameter count."""
    if params is None:
        return "unknown"
    if params < 4_000_000_000:
        return "small"
    if params < 15_000_000_000:
        return "medium"
    if params < 80_000_000_000:
        return "large"
    return "xlarge"


def extract_capabilities(model_card: ModelCard) -> List[str]:
    """Extract capabilities from model metadata."""
    caps = []

    tag_map = {
        "text-generation": "text_generation",
        "text2text-generation": "text_generation",
        "feature-extraction": "embeddings",
        "sentence-similarity": "embeddings",
        "fill-mask": "fill_mask",
        "question-answering": "qa",
        "summarization": "summarization",
        "translation": "translation",
        "text-classification": "classification",
        "token-classification": "ner",
        "image-classification": "vision",
        "object-detection": "vision",
        "image-to-text": "vision_language",
        "visual-question-answering": "vision_language",
        "automatic-speech-recognition": "asr",
        "text-to-speech": "tts",
        "text-to-image": "image_generation",
    }

    if model_card.pipeline_tag and model_card.pipeline_tag in tag_map:
        caps.append(tag_map[model_card.pipeline_tag])

    for tag in model_card.tags:
        tag_lower = tag.lower()
        if "code" in tag_lower or "coder" in tag_lower:
            caps.append("coding")
        if "chat" in tag_lower or "instruct" in tag_lower:
            caps.append("chat")
        if "embed" in tag_lower:
            caps.append("embeddings")
        if "rerank" in tag_lower:
            caps.append("reranking")
        if "vision" in tag_lower or "vl" in tag_lower:
            caps.append("vision_language")
        if "math" in tag_lower:
            caps.append("math")
        if "tool" in tag_lower or "function" in tag_lower:
            caps.append("tool_use")

    return list(set(caps))


def estimate_params(model_id: str, tags: List[str]) -> Optional[int]:
    """Estimate parameter count from model name or tags."""
    # Try extracting from model name
    name_lower = model_id.lower()
    patterns = [
        (r"(\d+\.?\d*)b", 1_000_000_000),
        (r"(\d+\.?\d*)m", 1_000_000),
    ]

    for pattern, multiplier in patterns:
        match = re.search(pattern, name_lower)
        if match:
            return int(float(match.group(1)) * multiplier)

    return None


def fetch_model_card(model_id: str) -> ModelCard:
    """Fetch model card from HuggingFace Hub."""
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        info = api.model_info(model_id)

        # Extract parameter count
        params = None
        if hasattr(info, "safetensors") and info.safetensors:
            params_info = info.safetensors.get("total", None)
            if params_info:
                params = params_info
        if params is None:
            params = estimate_params(model_id, info.tags or [])

        # Extract context length from config if available
        context_length = None
        if hasattr(info, "config") and info.config:
            for key in ("max_position_embeddings", "max_seq_len", "n_positions"):
                if key in (info.config or {}):
                    context_length = info.config[key]
                    break

        return ModelCard(
            model_id=info.modelId,
            name=info.modelId.split("/")[-1],
            author=info.modelId.split("/")[0] if "/" in info.modelId else "",
            pipeline_tag=info.pipeline_tag,
            task=info.pipeline_tag,
            params=params,
            context_length=context_length,
            license=info.card_data.get("license") if info.card_data else None,
            tags=info.tags or [],
            languages=info.card_data.get("language", []) if info.card_data else [],
            downloads=info.downloads or 0,
            likes=info.likes or 0,
            library_name=info.library_name,
            hf_url=f"https://huggingface.co/{info.modelId}",
            created_at=str(info.created_at) if info.created_at else None,
            last_modified=str(info.last_modified) if info.last_modified else None,
        )

    except ImportError:
        print("huggingface_hub not installed. Install with: uv pip install huggingface_hub", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch model card for {model_id}: {e}", file=sys.stderr)
        sys.exit(1)


def generate_agent_card_fragment(model_card: ModelCard) -> AgentCardFragment:
    """Generate a CGP-compatible agent card fragment from model card."""
    capabilities = extract_capabilities(model_card)
    tier = classify_tier(model_card.params)
    now = datetime.now(timezone.utc).isoformat()

    # Generate checksum from model metadata
    checksum_data = json.dumps(
        {"model_id": model_card.model_id, "params": model_card.params, "task": model_card.task},
        sort_keys=True,
    )
    checksum = hashlib.sha256(checksum_data.encode()).hexdigest()[:16]

    return AgentCardFragment(
        version="cgp.v2",
        type="model_binding",
        model_id=model_card.model_id,
        name=model_card.name,
        author=model_card.author,
        task=model_card.task,
        params=model_card.params,
        context_length=model_card.context_length,
        license=model_card.license,
        tier=tier,
        capabilities=capabilities,
        performance={},  # Filled by benchmark runner
        hf_url=model_card.hf_url,
        checksum=checksum,
        onboarded_at=now,
    )


def upsert_to_supabase(fragment: AgentCardFragment) -> bool:
    """Upsert agent card fragment to Supabase persona_framework table."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for upsert", file=sys.stderr)
        return False

    try:
        import httpx

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

        data = {
            "model_id": fragment.model_id,
            "name": fragment.name,
            "author": fragment.author,
            "task": fragment.task,
            "params": fragment.params,
            "context_length": fragment.context_length,
            "license": fragment.license,
            "tier": fragment.tier,
            "capabilities": fragment.capabilities,
            "performance": fragment.performance,
            "hf_url": fragment.hf_url,
            "cgp_fragment": asdict(fragment),
            "onboarded_at": fragment.onboarded_at,
        }

        resp = httpx.post(
            f"{supabase_url}/rest/v1/model_bindings",
            headers=headers,
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return True

    except ImportError:
        print("httpx not installed. Install with: uv pip install httpx", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Supabase upsert failed: {e}", file=sys.stderr)
        return False


def publish_nats_event(fragment: AgentCardFragment) -> bool:
    """Publish model onboarding event to NATS."""
    import asyncio

    async def _publish():
        try:
            import nats

            nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@localhost:4222")
            nc = nats.NATS()
            await nc.connect(nats_url)
            event = {
                "model_id": fragment.model_id,
                "name": fragment.name,
                "tier": fragment.tier,
                "capabilities": fragment.capabilities,
                "onboarded_at": fragment.onboarded_at,
            }
            await nc.publish(
                "hf.model.onboarded.v1",
                json.dumps(event).encode(),
            )
            await nc.close()
            return True
        except Exception as e:
            print(f"NATS publish failed: {e}", file=sys.stderr)
            return False

    return asyncio.run(_publish())


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HuggingFace Model Onboarding")
    parser.add_argument("model_id", help="HuggingFace model ID (e.g., Qwen/Qwen2.5-7B-Instruct)")
    parser.add_argument("--dry-run", action="store_true", help="Print fragment without upserting")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-nats", action="store_true", help="Skip NATS event publication")
    parser.add_argument("--no-supabase", action="store_true", help="Skip Supabase upsert")

    args = parser.parse_args()

    # Fetch model card
    print(f"Fetching model card for {args.model_id}...", file=sys.stderr)
    model_card = fetch_model_card(args.model_id)

    # Generate agent card fragment
    fragment = generate_agent_card_fragment(model_card)

    if args.json or args.dry_run:
        output = {
            "model_card": asdict(model_card),
            "agent_card_fragment": asdict(fragment),
        }
        print(json.dumps(output, indent=2, default=str))

        if args.dry_run:
            return 0

    # Upsert to Supabase
    if not args.no_supabase:
        if upsert_to_supabase(fragment):
            print(f"Upserted {fragment.model_id} to Supabase", file=sys.stderr)
        else:
            print("Supabase upsert skipped (missing credentials or error)", file=sys.stderr)

    # Publish NATS event
    if not args.no_nats:
        if publish_nats_event(fragment):
            print(f"Published onboarding event for {fragment.model_id}", file=sys.stderr)
        else:
            print("NATS publish skipped", file=sys.stderr)

    print(f"Onboarded: {fragment.model_id} (tier={fragment.tier}, caps={fragment.capabilities})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
