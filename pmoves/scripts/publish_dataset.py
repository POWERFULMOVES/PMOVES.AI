"""Publish PMOVES datasets to HuggingFace Hub.

Exports data from Supabase/ClickHouse/MinIO, CHIT-encodes raw data into CGP
packets, packages as Parquet files with dataset cards, and pushes to HuggingFace.

Usage:
    python -m pmoves.scripts.publish_dataset --dataset pmoves-chit-text
    python -m pmoves.scripts.publish_dataset --dataset pmoves-agent-traces --dry-run
    python -m pmoves.scripts.publish_dataset --all

Requires:
    pip install huggingface_hub datasets pyarrow httpx pyyaml

Environment:
    HF_TOKEN            — HuggingFace write token
    SUPABASE_REST_URL   — PostgREST endpoint
    SUPABASE_SERVICE_ROLE_KEY — Supabase service key
    CLICKHOUSE_URL      — ClickHouse HTTP endpoint (for agent traces)
    CLICKHOUSE_USER     — ClickHouse user (default: tensorzero)
    CLICKHOUSE_PASSWORD — ClickHouse password
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml

logger = logging.getLogger("publish_dataset")

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "datasets.yaml"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load datasets.yaml configuration."""
    p = path or _CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Dataset config not found: {p}")
    with open(p) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

def fetch_supabase_rows(
    table: str,
    filter_str: str = "",
    limit: int = 10000,
) -> List[Dict[str, Any]]:
    """Fetch rows from Supabase PostgREST."""
    base_url = os.environ.get("SUPABASE_REST_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url:
        logger.warning("SUPABASE_REST_URL not set — returning empty")
        return []

    headers = {
        "Accept": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    params: Dict[str, str] = {
        "limit": str(limit),
        "order": "created_at.desc",
    }
    # Parse filter like "payload->>spec=eq.chit.cgp.v0.2"
    if filter_str and "=" in filter_str:
        col, val = filter_str.split("=", 1)
        params[col] = val

    url = f"{base_url}/{table}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_clickhouse_rows(query: str, limit: int = 10000) -> List[Dict[str, Any]]:
    """Fetch rows from ClickHouse via HTTP interface."""
    ch_url = os.environ.get("CLICKHOUSE_URL", "http://localhost:8123")
    ch_user = os.environ.get("CLICKHOUSE_USER", "tensorzero")
    ch_pass = os.environ.get("CLICKHOUSE_PASSWORD", "")

    full_query = f"{query.strip().rstrip(';')} LIMIT {limit} FORMAT JSONEachRow"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            ch_url,
            content=full_query,
            headers={"Content-Type": "text/plain"},
            params={"user": ch_user, "password": ch_pass},
        )
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().split("\n"):
            if line:
                rows.append(json.loads(line))
        return rows


# ---------------------------------------------------------------------------
# Dataset builders
# ---------------------------------------------------------------------------

def build_chit_text_dataset(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build rows for pmoves-chit-text from Supabase CGP records."""
    ds_config = config["datasets"]["pmoves-chit-text"]
    source = ds_config.get("supabase_source", {})
    table = source.get("table", "geometry_cgp_v1").replace("pmoves_core.", "")
    filter_str = source.get("filter", "")

    raw_rows = fetch_supabase_rows(table, filter_str)
    rows = []
    for raw in raw_rows:
        payload = raw.get("payload", {})
        if not isinstance(payload, dict):
            continue

        # Extract geometry parameters from packet metadata
        meta = payload.get("meta", {}) or {}
        hyperbolic = payload.get("hyperbolic", {}) or {}

        # Extract text from super_nodes → constellations → points
        texts = []
        for sn in payload.get("super_nodes", []):
            for const in sn.get("constellations", []):
                for pt in const.get("points", []):
                    if pt.get("text"):
                        texts.append(pt["text"])

        original_text = " ".join(texts) if texts else meta.get("summary", "")
        if not original_text:
            continue

        rows.append({
            "cgp_packet": json.dumps(payload),
            "original_text": original_text,
            "reconstruction": original_text,  # Identity reconstruction for now
            "delta": hyperbolic.get("curvature", meta.get("delta", 0.0)),
            "kappa": meta.get("kappa", 0.0),
            "hz": meta.get("hz", 0.0),
            "fidelity_score": meta.get("fidelity", 1.0),
            "evoswarm_pack_id": meta.get("evoswarm_pack_id", "seed-v0"),
        })

    logger.info("Built %d rows for pmoves-chit-text", len(rows))
    return rows


def build_agent_traces_dataset(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build rows for pmoves-agent-traces from ClickHouse inference logs."""
    ds_config = config["datasets"]["pmoves-agent-traces"]
    ch_source = ds_config.get("clickhouse_source", {})
    query = ch_source.get("query", "")
    if not query:
        logger.warning("No ClickHouse query configured for agent traces")
        return []

    raw_rows = fetch_clickhouse_rows(query)
    rows = []
    for raw in raw_rows:
        rows.append({
            "agent_id": raw.get("agent_id", "agent_zero"),
            "function": raw.get("function", "orchestrator"),
            "prompt": raw.get("prompt", ""),
            "chosen_response": raw.get("chosen_response", ""),
            "rejected_response": "",  # DPO pairs require offline labeling
            "reward_signal": 0.5,     # Neutral until scored
            "model_id": raw.get("model_id", ""),
            "latency_ms": float(raw.get("latency_ms", 0)),
            "token_count": int(raw.get("token_count", 0)),
        })

    logger.info("Built %d rows for pmoves-agent-traces", len(rows))
    return rows


_BUILDERS = {
    "pmoves-chit-text": build_chit_text_dataset,
    "pmoves-agent-traces": build_agent_traces_dataset,
}


# ---------------------------------------------------------------------------
# HuggingFace publishing
# ---------------------------------------------------------------------------

def publish_to_huggingface(
    dataset_name: str,
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
    dry_run: bool = False,
) -> Optional[str]:
    """Push dataset rows to HuggingFace Hub as Parquet."""
    try:
        from datasets import Dataset
        from huggingface_hub import HfApi
    except ImportError:
        logger.error("Install: pip install datasets huggingface_hub")
        return None

    ds_config = config["datasets"][dataset_name]
    hf_id = ds_config["hf_id"]
    pub_config = config.get("publishing", {})

    if not rows:
        logger.warning("No rows to publish for %s", dataset_name)
        return None

    # Build HF Dataset
    dataset = Dataset.from_list(rows)
    logger.info("Dataset %s: %d rows, columns=%s", dataset_name, len(dataset), dataset.column_names)

    if dry_run:
        logger.info("[DRY RUN] Would publish %d rows to %s", len(rows), hf_id)
        # Write sample to temp for inspection
        sample_path = Path(tempfile.gettempdir()) / f"{dataset_name}_sample.json"
        with open(sample_path, "w") as f:
            json.dump(rows[:5], f, indent=2, default=str)
        logger.info("[DRY RUN] Sample written to %s", sample_path)
        return str(sample_path)

    # Push to Hub
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        logger.error("HF_TOKEN not set — cannot publish")
        return None

    dataset.push_to_hub(
        hf_id,
        token=token,
        private=False,
    )
    logger.info("Published %d rows to %s", len(rows), hf_id)

    # Update dataset card
    api = HfApi(token=token)
    card_content = _build_dataset_card(dataset_name, ds_config, pub_config, len(rows))
    api.upload_file(
        path_or_fileobj=card_content.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=hf_id,
        repo_type="dataset",
    )
    logger.info("Updated dataset card for %s", hf_id)

    return hf_id


def _build_dataset_card(
    name: str,
    ds_config: Dict[str, Any],
    pub_config: Dict[str, Any],
    row_count: int,
) -> str:
    """Generate a HuggingFace dataset card from config."""
    template = pub_config.get("card_template", "# {title}\n\n{description}")
    license_id = pub_config.get("default_license", "apache-2.0")
    tags = pub_config.get("default_tags", ["pmoves"])

    modality = ds_config.get("modality", "text")
    if isinstance(modality, list):
        tags.extend(modality)
    else:
        tags.append(modality)

    return template.format(
        title=name,
        description=ds_config.get("description", ""),
        hf_id=ds_config["hf_id"],
        license=license_id,
        tags=json.dumps(tags),
        row_count=row_count,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Publish PMOVES datasets to HuggingFace Hub",
    )
    parser.add_argument(
        "--dataset",
        choices=list(_BUILDERS.keys()),
        help="Which dataset to publish",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Publish all configured datasets",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build dataset but don't push to HuggingFace",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to datasets.yaml (default: pmoves/config/datasets.yaml)",
    )
    args = parser.parse_args()

    if not args.dataset and not args.all:
        parser.error("Specify --dataset or --all")

    config = load_config(args.config)
    targets = list(_BUILDERS.keys()) if args.all else [args.dataset]
    results = {}

    for name in targets:
        builder = _BUILDERS.get(name)
        if not builder:
            logger.warning("No builder for dataset: %s (skipping)", name)
            continue

        logger.info("Building dataset: %s", name)
        rows = builder(config)
        result = publish_to_huggingface(name, rows, config, dry_run=args.dry_run)
        results[name] = result

    # Summary
    logger.info("--- Publishing Summary ---")
    for name, result in results.items():
        status = "OK" if result else "SKIPPED"
        logger.info("  %s: %s (%s)", name, status, result or "no rows / error")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
