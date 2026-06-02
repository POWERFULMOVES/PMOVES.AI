#!/usr/bin/env python3
"""CHIT CGP Auto-Mapper — transforms consciousness-chunks JSONL into a CGP geometry packet.

Reads a consciousness-chunks.jsonl file, embeds chunk content with sentence-transformers,
clusters embeddings per category into constellations via KMeans, and emits a validated
CGP v1 JSON packet matching cgp.v1.schema.json.

Usage:
    python pmoves/tools/chit_backend.py \
        --input consciousness-chunks.jsonl \
        --output geometry_payload.json \
        --K 3 --bins 8 --backend all-MiniLM-L6-v2
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator, validate as jsonschema_validate
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans


def eprint(*args, **kwargs):
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


def load_chunks(path: Path) -> list[dict]:
    """Load JSONL file, returning list of parsed dicts."""
    chunks: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError as exc:
                eprint(f"WARN: skipping malformed line {line_num}: {exc}")
    return chunks


def group_by_category(chunks: list[dict]) -> dict[str, list[dict]]:
    """Group chunks by their 'category' field."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        cat = chunk.get("category", "unknown")
        groups[cat].append(chunk)
    return dict(groups)


def encode_chunks(model: SentenceTransformer, chunks: list[dict]) -> np.ndarray:
    """Encode chunk content fields to embedding vectors."""
    texts = [c.get("content", "") for c in chunks]
    eprint(f"  Encoding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(embeddings, dtype=np.float64)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (assumed pre-normalized or not)."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def compute_spectrum(projs: list[float], bins: int) -> list[float]:
    """Normalized histogram of projection values."""
    if not projs:
        return [0.0] * bins
    arr = np.array(projs)
    counts, _ = np.histogram(arr, bins=bins, range=(0.0, 1.0))
    total = counts.sum()
    if total == 0:
        return [0.0] * bins
    return (counts / total).tolist()


def compute_mhep(projs: list[float]) -> float:
    """Mean Harmonic Embedding Perplexity — inverse of the shifted-softmax denominator.

    For a single constellation, MHEP = 1 / sum(exp(projs - max(projs))). This is
    equivalent to the softmax temperature-1 normalizer evaluated in max-shifted
    log-space (numerical stability), NOT 1/sum(softmax(projs)) — the latter is
    always 1.0 by definition of softmax.

    Interpretation: MHEP is bounded in (0, 1]. MHEP → 1.0 as one projection
    dominates (peaked); MHEP → 1/N as projections are equal (flat). For example:
      - compute_mhep([0.0]) == 1.0           (single projection)
      - compute_mhep([1.0, 1.0]) == 0.5      (flat, N=2 → 1/2)
      - compute_mhep([10.0, 0.0, 0.0]) ≈ 1.0 (peaked)

    Returns 0.0 if no projections (edge case for empty constellations).
    """
    if not projs:
        return 0.0
    arr = np.array(projs, dtype=np.float64)
    # softmax with temperature=1
    shifted = arr - arr.max()
    exp_vals = np.exp(shifted)
    softmax_sum = exp_vals.sum()
    if softmax_sum == 0.0:
        return 0.0
    return float(1.0 / softmax_sum)


def build_cgp(
    category_groups: dict[str, list[dict]],
    embeddings_per_cat: dict[str, np.ndarray],
    k: int,
    bins: int,
) -> dict:
    """Build the full CGP packet from grouped chunks and their embeddings."""
    categories = sorted(category_groups.keys())
    num_cats = len(categories)
    if num_cats == 0:
        return {"spec": "chit.cgp.v1.0", "super_nodes": []}

    radius = 1.0
    now = datetime.now(timezone.utc).isoformat()

    all_constellations: list[dict] = []
    all_points: list[dict] = []
    super_nodes: list[dict] = []

    for i, cat in enumerate(categories):
        chunks = category_groups[cat]
        embs = embeddings_per_cat[cat]
        n = len(chunks)

        # Super-node position on circle
        angle = 2.0 * math.pi * i / num_cats
        sx = round(radius * math.cos(angle), 6)
        sy = round(radius * math.sin(angle), 6)

        # Determine actual K (reduce if fewer chunks than K)
        actual_k = min(k, n)
        if actual_k < 1:
            actual_k = 1

        eprint(f"  Category '{cat}': {n} chunks, K={actual_k}")

        # Cluster embeddings
        if n <= 1:
            # Single chunk — one cluster, centroid is the embedding itself
            labels = np.array([0])
            centroids = embs.reshape(1, -1) if n == 1 else np.zeros((1, embs.shape[1]))
        else:
            km = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
            labels = km.fit_predict(embs)
            centroids = km.cluster_centers_

        cat_constellations: list[dict] = []
        cat_points: list[dict] = []

        for c_idx in range(actual_k):
            # Find chunks in this cluster
            mask = labels == c_idx
            cluster_indices = np.where(mask)[0]
            cluster_embs = embs[mask]
            cluster_chunks = [chunks[j] for j in cluster_indices]

            if len(cluster_chunks) == 0:
                continue

            # Centroid normalized
            centroid = centroids[c_idx]
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid_normed = centroid / norm
            else:
                centroid_normed = centroid

            # Anchor: [x, y] from first 2 dims of normalized centroid
            anchor_x = float(centroid_normed[0])
            anchor_y = float(centroid_normed[1]) if centroid_normed.shape[0] > 1 else 0.0

            constellation_id = f"{cat}-c{c_idx}"

            points: list[dict] = []
            projs: list[float] = []

            for p_idx, (chunk, emb) in enumerate(zip(cluster_chunks, cluster_embs)):
                chunk_id = chunk.get("id", f"{constellation_id}-p{p_idx}")
                content = chunk.get("content", "")
                proj_val = cosine_similarity(emb, centroid_normed)
                projs.append(proj_val)

                # Relative 2D position: first 2 dims of (embedding - centroid)
                diff = emb - centroid_normed
                px = float(diff[0]) if diff.shape[0] > 0 else 0.0
                py = float(diff[1]) if diff.shape[0] > 1 else 0.0

                point = {
                    "id": chunk_id,
                    "ref_id": chunk_id,
                    "modality": "text",
                    "text": content[:512],
                    "proj": round(proj_val, 6),
                    "conf": round(proj_val, 6),
                    "x": round(px, 6),
                    "y": round(py, 6),
                    "char_len": len(content),
                    "word_count": len(content.split()),
                    "summary": chunk.get("title", ""),
                    "meta": {
                        "category": cat,
                        "namespace": chunk.get("namespace", "pmoves.consciousness"),
                    },
                }
                # Only include source_ref if url is present (schema requires string, not null)
                if chunk.get("url"):
                    point["source_ref"] = chunk["url"]
                # Optional ts from chunk
                if chunk.get("created_at"):
                    point["ts"] = chunk["created_at"]

                points.append(point)

            # Spectrum
            spectrum = compute_spectrum(projs, bins)

            # Radial minmax from projection values
            if projs:
                radial_minmax = [round(min(projs), 6), round(max(projs), 6)]
            else:
                radial_minmax = [0.0, 0.0]

            constellation = {
                "id": constellation_id,
                "points": points,
                "anchor": [anchor_x, anchor_y],
                "spectrum": spectrum,
                "radial_minmax": radial_minmax,
            }

            cat_constellations.append(constellation)
            cat_points.extend(points)

        super_node = {
            "id": f"super-{cat}",
            "label": cat,
            "x": sx,
            "y": sy,
            "r": radius,
            "constellations": cat_constellations,
        }
        super_nodes.append(super_node)
        all_constellations.extend(cat_constellations)
        all_points.extend(cat_points)

    # Compute top-level MHEP across all constellations
    mhep_values = []
    for con in all_constellations:
        con_projs = [p.get("proj", 0.0) for p in con.get("points", [])]
        mhep_values.append(compute_mhep(con_projs))
    avg_mhep = float(np.mean(mhep_values)) if mhep_values else 0.0

    cgp = {
        "spec": "chit.cgp.v1.0",
        "created_at": now,
        "updated_at": now,
        "summary": f"CGP auto-mapped from {sum(len(v) for v in category_groups.values())} chunks "
                   f"across {num_cats} categories, {len(all_constellations)} constellations",
        "meta": {
            "mhep": round(avg_mhep, 6),
            "total_chunks": sum(len(v) for v in category_groups.values()),
            "categories": categories,
            "K": k,
            "bins": bins,
        },
        "super_nodes": super_nodes,
        "constellations": all_constellations,
        "points": all_points,
    }

    return cgp


def load_schema() -> dict:
    """Load CGP v1 schema from contracts directory."""
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "contracts"
        / "schemas"
        / "geometry"
        / "cgp.v1.schema.json"
    )
    if not schema_path.exists():
        eprint(f"WARN: schema not found at {schema_path} — skipping validation")
        return {}
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_cgp(cgp: dict, schema: dict) -> bool:
    """Validate CGP packet against schema. Returns True if valid."""
    if not schema:
        eprint("WARN: no schema loaded, skipping validation")
        return True
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(cgp), key=lambda e: list(e.path))
    if not errors:
        eprint("  Schema validation: PASSED")
        return True
    eprint(f"  Schema validation: FAILED ({len(errors)} error(s))")
    for err in errors:
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        eprint(f"    {path}: {err.message}")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="CHIT CGP Auto-Mapper: consciousness-chunks JSONL → CGP geometry packet",
    )
    parser.add_argument("--input", required=True, help="Path to consciousness-chunks.jsonl")
    parser.add_argument("--output", required=True, help="Path to output CGP JSON file")
    parser.add_argument("--K", type=int, default=3, help="Constellations per super-node (default: 3)")
    parser.add_argument("--bins", type=int, default=8, help="Spectrum resolution bins (default: 8)")
    parser.add_argument(
        "--backend",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model name (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        default=False,
        help="Disable schema validation (default: validate)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        eprint(f"ERROR: input file not found: {input_path}")
        sys.exit(1)

    # 1. Load chunks
    eprint(f"Loading chunks from {input_path}...")
    chunks = load_chunks(input_path)
    if not chunks:
        eprint("ERROR: no valid chunks found in input file")
        sys.exit(1)
    eprint(f"  Loaded {len(chunks)} chunks")

    # 2. Group by category
    category_groups = group_by_category(chunks)
    eprint(f"  Found {len(category_groups)} categories: {', '.join(sorted(category_groups.keys()))}")

    # 3. Load model
    eprint(f"Loading model '{args.backend}'...")
    model = SentenceTransformer(args.backend)
    eprint(f"  Model loaded, embedding dim: {model.get_sentence_embedding_dimension()}")

    # 4. Encode all chunks per category
    eprint("Encoding chunks per category...")
    embeddings_per_cat: dict[str, np.ndarray] = {}
    for cat in sorted(category_groups.keys()):
        cat_chunks = category_groups[cat]
        embeddings_per_cat[cat] = encode_chunks(model, cat_chunks)

    # 5. Build CGP
    eprint("Building CGP packet...")
    cgp = build_cgp(category_groups, embeddings_per_cat, args.K, args.bins)

    sn_count = len(cgp["super_nodes"])
    con_count = len(cgp.get("constellations", []))
    pt_count = len(cgp.get("points", []))
    eprint(f"  Built: {sn_count} super-nodes, {con_count} constellations, {pt_count} points")

    # 6. Validate
    if not args.no_validate:
        eprint("Validating against schema...")
        schema = load_schema()
        if not validate_cgp(cgp, schema):
            eprint("ERROR: schema validation failed")
            sys.exit(1)
    else:
        eprint("Schema validation disabled (--no-validate)")

    # 7. Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cgp, f, indent=2, ensure_ascii=False)
    eprint(f"Written to {output_path}")


if __name__ == "__main__":
    main()
