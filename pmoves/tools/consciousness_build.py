#!/usr/bin/env python3

"""
PMOVES • Consciousness Harvest Builder

Transforms the scaffold created by consciousness_downloader.{sh,ps1}
into PMOVES-ready artifacts:
  - processed-for-rag/embeddings-ready/consciousness-chunks.jsonl
  - processed-for-rag/supabase-import/consciousness-schema.sql
  - processed-for-rag/supabase-import/consciousness-seed.jsonl
  - geometry/geometry_payload.json (sample CGP packet)

This script is intentionally lightweight and avoids external dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


HARVEST_SUFFIX = "pmoves/data/consciousness/Constellation-Harvest-Regularization"

# Kuhn's Landscape of Consciousness Taxonomy - 10 major categories
# Based on "A landscape of consciousness: Toward a taxonomy of explanations and implications" (2024)
CONSCIOUSNESS_TAXONOMY = {
    "Materialism-Theories": {
        "description": "Theories holding that consciousness arises from or is identical to physical brain processes.",
        "subcategories": {
            "Neurobiological": [
                ("Global Workspace Theory", "Bernard Baars, Stanislas Dehaene", "Consciousness arises when information is broadcast globally across the brain."),
                ("Neural Correlates of Consciousness", "Christof Koch, Francis Crick", "Identifying specific neural patterns that correlate with conscious experience."),
                ("Predictive Processing", "Karl Friston, Andy Clark", "Brain constantly generates predictions; consciousness emerges from prediction error minimization."),
            ],
            "Computational-Informational": [
                ("Attention Schema Theory", "Michael Graziano", "Brain constructs a model of attention, which we experience as consciousness."),
                ("Global Neuronal Workspace", "Stanislas Dehaene", "Consciousness involves global information integration via cortical workspace."),
            ],
            "Embodied-Enactive": [
                ("Enactivism", "Francisco Varela, Evan Thompson", "Consciousness arises through sensorimotor coupling with the world."),
                ("Extended Mind", "Andy Clark, David Chalmers", "Cognitive processes extend beyond the brain into body and environment."),
            ],
        }
    },
    "Non-Reductive-Physicalism": {
        "description": "Mental properties are physical but not reducible to lower-level physical descriptions.",
        "theories": [
            ("Emergentism", "C.D. Broad", "Consciousness is an emergent property not predictable from physical components."),
            ("Anomalous Monism", "Donald Davidson", "Mental events are physical but not governed by strict psychophysical laws."),
        ]
    },
    "Quantum-Theories": {
        "description": "Consciousness involves or requires quantum mechanical processes.",
        "theories": [
            ("Orchestrated Objective Reduction", "Roger Penrose, Stuart Hameroff", "Consciousness arises from quantum computations in microtubules."),
            ("Quantum Mind", "Henry Stapp", "Quantum mechanics essential for understanding consciousness and free will."),
        ]
    },
    "Integrated-Information-Theory": {
        "description": "Consciousness is integrated information (Phi) in a system.",
        "theories": [
            ("IIT 3.0/4.0", "Giulio Tononi", "Consciousness is identical to integrated information; Phi measures consciousness."),
        ]
    },
    "Panpsychisms": {
        "description": "Consciousness or proto-consciousness is a fundamental feature of reality.",
        "theories": [
            ("Constitutive Panpsychism", "Philip Goff", "Macro-consciousness constituted by micro-level consciousness."),
            ("Cosmopsychism", "Itay Shani", "Universe itself is conscious; individual minds are aspects of cosmic mind."),
            ("Russellian Monism", "Bertrand Russell, Galen Strawson", "Physical properties are structural; intrinsic nature is experiential."),
        ]
    },
    "Monisms": {
        "description": "Reality is fundamentally one kind of substance.",
        "theories": [
            ("Neutral Monism", "William James, Bertrand Russell", "Reality is neither mental nor physical but neutral."),
            ("Double-Aspect Monism", "Baruch Spinoza", "Mind and matter are two aspects of one substance."),
        ]
    },
    "Dualisms": {
        "description": "Mind and matter are fundamentally distinct substances or properties.",
        "theories": [
            ("Property Dualism", "David Chalmers", "Mental properties are non-physical properties of physical substances."),
            ("Interactionist Dualism", "Karl Popper, John Eccles", "Mind and brain causally interact."),
        ]
    },
    "Idealisms": {
        "description": "Reality is fundamentally mental or consciousness-based.",
        "theories": [
            ("Analytic Idealism", "Bernardo Kastrup", "Reality is mental; matter is appearance of mental processes."),
            ("Conscious Realism", "Donald Hoffman", "Consciousness is fundamental; spacetime and objects are user interfaces."),
        ]
    },
    "Anomalous-Altered-States": {
        "description": "Consciousness studies informed by altered states, near-death experiences, meditation.",
        "theories": [
            ("Psychedelic Consciousness", "Robin Carhart-Harris", "Psychedelics reveal aspects of consciousness through entropic brain states."),
            ("Contemplative Science", "Richard Davidson", "Contemplative practices transform conscious experience."),
        ]
    },
    "Challenge-Theories": {
        "description": "Theories that challenge or question standard assumptions about consciousness.",
        "theories": [
            ("Illusionism", "Keith Frankish", "Consciousness as we conceive it is an illusion."),
            ("Mysterianism", "Colin McGinn", "Human minds may be constitutionally incapable of understanding consciousness."),
            ("The Hard Problem", "David Chalmers", "Why is there subjective experience at all?"),
        ]
    },
}


@dataclass
class Chunk:
    chunk_id: str
    title: str
    url: Optional[str]
    category: str
    content: str


def deterministic_id(content: str, prefix: str, max_len: int = 12) -> str:
    """Generate deterministic ID from content using SHA-256.

    This ensures idempotent chunk generation - re-running the script
    produces identical IDs for the same content.
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:max_len]
    return f"{prefix}-{content_hash}"


def strip_html(html: str) -> str:
    """Very small HTML → text helper; removes scripts/styles and tags."""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", html)
    cleaned = re.sub(r"(?is)<(head|header|footer).*?>.*?(</\1>)", "", cleaned)
    cleaned = re.sub(r"(?is)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?is)</p>", "\n\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\n\s+", "\n", cleaned)
    return cleaned.strip()


def collect_taxonomy_chunks() -> List[Chunk]:
    """Generate chunks from the Kuhn consciousness taxonomy."""
    chunks: List[Chunk] = []

    for category, cat_data in CONSCIOUSNESS_TAXONOMY.items():
        # Category description chunk
        chunk_id = f"consciousness-cat-{category.lower()}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                title=f"{category.replace('-', ' ')} - Category Overview",
                url=None,
                category=category,
                content=f"{category.replace('-', ' ')}: {cat_data['description']}",
            )
        )

        # Subcategory theories
        for subcat_name, theories in cat_data.get("subcategories", {}).items():
            for theory_name, proponents, desc in theories:
                # Use theory name + category for deterministic ID
                id_source = f"{theory_name}:{category}:{subcat_name}"
                chunk_id = deterministic_id(id_source, "consciousness-theory")
                content = (
                    f"{theory_name} is a consciousness theory in the {subcat_name} subcategory of {category.replace('-', ' ')}. "
                    f"Key proponents: {proponents}. {desc}"
                )
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        title=theory_name,
                        url=None,
                        category=category,
                        content=content,
                    )
                )

        # Direct theories (no subcategory)
        for theory_name, proponents, desc in cat_data.get("theories", []):
            # Use theory name + category for deterministic ID
            id_source = f"{theory_name}:{category}"
            chunk_id = deterministic_id(id_source, "consciousness-theory")
            content = (
                f"{theory_name} is a consciousness theory in the {category.replace('-', ' ')} category. "
                f"Key proponents: {proponents}. {desc}"
            )
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    title=theory_name,
                    url=None,
                    category=category,
                    content=content,
                )
            )

    return chunks


def collect_chunks(base: Path) -> List[Chunk]:
    chunks: List[Chunk] = []

    # First, add taxonomy chunks
    chunks.extend(collect_taxonomy_chunks())

    # Research papers
    research_dir = base / "research-papers"
    if research_dir.exists():
        for html_path in sorted(research_dir.glob("*.html")):
            try:
                text = strip_html(html_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception as exc:  # pragma: no cover
                print(f"[warn] Failed to process {html_path}: {exc}", file=sys.stderr)
                continue
            if not text:
                continue
            title = html_path.stem.replace("_", " ").replace("-", " ").title()
            # Use filename for deterministic ID (stable across runs)
            chunk_id = deterministic_id(html_path.name, "consciousness-paper")
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    title=title,
                    url=None,
                    category="research-paper",
                    content=text,
                )
            )

    # Discovered links (from Selenium helper)
    links_path = base / "data-exports" / "discovered-links.json"
    if links_path.exists():
        try:
            links = json.loads(links_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            links = []
        for entry in links:
            url = entry.get("Url") or entry.get("url")
            label = entry.get("Text") or entry.get("text") or url
            if not label:
                continue
            # Use URL for deterministic ID (unique per link)
            chunk_id = deterministic_id(url or label, "consciousness-link")
            content = f"Discovered theory/category link: {label} ({url})"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    title=label.strip(),
                    url=url,
                    category="link",
                    content=content,
                )
            )

    # Fallback: create placeholder chunk if nothing harvested
    if not chunks:
        chunks.append(
            Chunk(
                chunk_id="consciousness-placeholder-empty",
                title="Landscape of Consciousness (placeholder)",
                url=str(research_dir),
                category="placeholder",
                content="No harvestable content was found. Ensure the downloader scripts run on a host with access to the source site.",
            )
        )
    return chunks


def write_jsonl(chunks: Iterable[Chunk], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(
                json.dumps(
                    {
                        "id": chunk.chunk_id,
                        "title": chunk.title,
                        "url": chunk.url,
                        "category": chunk.category,
                        "content": chunk.content,
                        "namespace": "pmoves.consciousness",
                        "created_at": datetime.utcnow().isoformat() + "Z",
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")


def write_schema(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = textwrap.dedent(
        """
        -- Generated by consciousness_build.py
        create table if not exists public.consciousness_theories (
            id text primary key,
            title text not null,
            url text,
            category text not null default 'research-paper',
            content text not null,
            namespace text not null default 'pmoves.consciousness',
            created_at timestamp with time zone not null default now()
        );

        create index if not exists consciousness_theories_category_idx on public.consciousness_theories(category);
        create index if not exists consciousness_theories_namespace_idx on public.consciousness_theories(namespace);
        """
    ).strip()
    dest.write_text(schema_sql + "\n", encoding="utf-8")


def write_seed_sql(chunks: Iterable[Chunk], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    statements = []
    for chunk in chunks:
        content_sql = chunk.content.replace("'", "''")
        title_sql = chunk.title.replace("'", "''")
        category_sql = chunk.category.replace("'", "''")
        url_value = "null"
        if chunk.url:
            url_value = "'" + chunk.url.replace("'", "''") + "'"

        statements.append(
            "insert into public.consciousness_theories (id, title, url, category, content, namespace) "
            f"values ('{chunk.chunk_id}', '{title_sql}', {url_value}, "
            f"'{category_sql}', '{content_sql}', 'pmoves.consciousness') "
            "on conflict (id) do update set title=excluded.title, url=excluded.url, category=excluded.category, "
            "content=excluded.content, namespace=excluded.namespace;"
        )
    dest.write_text("\n".join(statements) + "\n", encoding="utf-8")


def write_geometry_sample(chunks: List[Chunk], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    sample = chunks[0]
    geometry = {
        "type": "geometry.cgp.v1",
        "data": {
            "id": f"cgp-{sample.chunk_id}",
            "namespace": "pmoves.consciousness",
            "label": sample.title[:96],
            "meta": {
                "category": sample.category,
                "source_url": sample.url,
                "generator": "pmoves.consciousness.harvest",
            },
            "summary": sample.content[:512],
            "anchors": [
                {
                    "label": "primary",
                    "vector": [0.0, 1.0, 0.0],
                }
            ],
        },
    }
    dest.write_text(json.dumps(geometry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=HARVEST_SUFFIX,
        help="Harvest directory (default: %(default)s relative to repo root)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    base = (repo_root / args.root).resolve()
    if not base.exists():
        print(f"[error] Harvest directory not found: {base}", file=sys.stderr)
        return 1

    chunks = collect_chunks(base)
    chunks_sorted = sorted(chunks, key=lambda c: c.chunk_id)

    write_jsonl(
        chunks_sorted,
        base / "processed-for-rag" / "embeddings-ready" / "consciousness-chunks.jsonl",
    )
    write_seed_sql(
        chunks_sorted,
        base / "processed-for-rag" / "supabase-import" / "consciousness-seed.sql",
    )
    write_schema(base / "processed-for-rag" / "supabase-import" / "consciousness-schema.sql")
    write_geometry_sample(
        chunks_sorted,
        base / "processed-for-rag" / "supabase-import" / "consciousness-geometry-sample.json",
    )

    print(f"[ok] Generated artifacts from {len(chunks_sorted)} chunks at {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
