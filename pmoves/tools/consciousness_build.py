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
import json
import os
import re
import sys
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


HARVEST_SUFFIX = "pmoves/data/consciousness/Constellation-Harvest-Regularization"
TAXONOMY_SUFFIX = "pmoves/data/consciousness/kuhn_full_taxonomy.json"


def load_full_taxonomy(repo_root: Path) -> dict:
    """Load the full Kuhn consciousness taxonomy from JSON file."""
    taxonomy_path = repo_root / TAXONOMY_SUFFIX
    if taxonomy_path.exists():
        try:
            with taxonomy_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[warn] Failed to load taxonomy from {taxonomy_path}: {e}", file=sys.stderr)
    return {}


@dataclass
class Chunk:
    chunk_id: str
    title: str
    url: Optional[str]
    category: str
    content: str


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


def collect_taxonomy_chunks(taxonomy: dict) -> List[Chunk]:
    """Generate chunks from the Kuhn consciousness taxonomy JSON.

    Supports the full JSON taxonomy format with:
    - categories: dict of category objects
    - Each category has: id, description, theories (optional), subcategories (optional)
    - Each subcategory has: description, theories
    - Each theory has: name, proponents (list), description
    """
    chunks: List[Chunk] = []
    categories = taxonomy.get("categories", {})

    if not categories:
        print("[warn] No categories found in taxonomy", file=sys.stderr)
        return chunks

    for cat_key, cat_data in categories.items():
        # Normalize category name for display
        category_id = cat_data.get("id", cat_key.replace("_", "-").lower())
        category_name = cat_key.replace("_", " ").lstrip("0123456789").strip()
        cat_description = cat_data.get("description", "")

        # Category description chunk
        chunk_id = f"consciousness-cat-{category_id}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                title=f"{category_name} - Category Overview",
                url=None,
                category=category_id,
                content=f"{category_name}: {cat_description}",
            )
        )

        # Process subcategories
        for subcat_key, subcat_data in cat_data.get("subcategories", {}).items():
            subcat_name = subcat_key.replace("_", " ").lstrip("0123456789.").strip()
            subcat_description = subcat_data.get("description", "")

            # Subcategory chunk
            subcat_id = f"consciousness-subcat-{subcat_key.lower().replace(' ', '-').replace('.', '-')[:40]}"
            chunks.append(
                Chunk(
                    chunk_id=subcat_id,
                    title=f"{subcat_name} - Subcategory",
                    url=None,
                    category=category_id,
                    content=f"{subcat_name} is a subcategory of {category_name}. {subcat_description}",
                )
            )

            # Theories in subcategory
            for theory in subcat_data.get("theories", []):
                theory_name = theory.get("name", "Unknown Theory")
                proponents = theory.get("proponents", [])
                proponents_str = ", ".join(proponents) if isinstance(proponents, list) else str(proponents)
                desc = theory.get("description", "")

                # Create stable ID from theory name
                theory_slug = theory_name.lower().replace(" ", "-").replace("'", "").replace("/", "-")[:35]
                chunk_id = f"consciousness-theory-{theory_slug}-{uuid.uuid4().hex[:6]}"

                content = (
                    f"{theory_name} is a consciousness theory in the {subcat_name} subcategory of {category_name}. "
                    f"Key proponents: {proponents_str}. {desc}"
                )
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        title=theory_name,
                        url=None,
                        category=category_id,
                        content=content,
                    )
                )

        # Direct theories (no subcategory)
        for theory in cat_data.get("theories", []):
            theory_name = theory.get("name", "Unknown Theory")
            proponents = theory.get("proponents", [])
            proponents_str = ", ".join(proponents) if isinstance(proponents, list) else str(proponents)
            desc = theory.get("description", "")

            theory_slug = theory_name.lower().replace(" ", "-").replace("'", "").replace("/", "-")[:35]
            chunk_id = f"consciousness-theory-{theory_slug}-{uuid.uuid4().hex[:6]}"

            content = (
                f"{theory_name} is a consciousness theory in the {category_name} category. "
                f"Key proponents: {proponents_str}. {desc}"
            )
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    title=theory_name,
                    url=None,
                    category=category_id,
                    content=content,
                )
            )

    return chunks


def collect_chunks(base: Path, taxonomy: dict) -> List[Chunk]:
    chunks: List[Chunk] = []

    # First, add taxonomy chunks from JSON
    chunks.extend(collect_taxonomy_chunks(taxonomy))

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
            chunk_id = f"consciousness-paper-{uuid.uuid4().hex[:12]}"
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
            chunk_id = f"consciousness-link-{uuid.uuid4().hex[:12]}"
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
                chunk_id=f"consciousness-placeholder-{uuid.uuid4().hex[:12]}",
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
                        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
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
    parser.add_argument(
        "--taxonomy",
        default=TAXONOMY_SUFFIX,
        help="Taxonomy JSON file (default: %(default)s relative to repo root)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    base = (repo_root / args.root).resolve()
    if not base.exists():
        print(f"[error] Harvest directory not found: {base}", file=sys.stderr)
        return 1

    # Load full taxonomy from JSON
    taxonomy = load_full_taxonomy(repo_root)
    if not taxonomy:
        # Fallback: try from base directory
        taxonomy_in_base = base.parent / "kuhn_full_taxonomy.json"
        if taxonomy_in_base.exists():
            try:
                taxonomy = json.loads(taxonomy_in_base.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass

    if not taxonomy:
        print("[warn] No taxonomy loaded, will only process research papers", file=sys.stderr)

    chunks = collect_chunks(base, taxonomy)
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
