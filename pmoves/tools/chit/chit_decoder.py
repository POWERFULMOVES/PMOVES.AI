"""
CHIT Decoder v0.1 - CGP → Content

Decodes CHIT Geometry Packets (CGP) back to original content.
Supports two modes:
1. Exact decode (lossless): Recovers text from CGP points if embedded
2. Geometry-only decode (lossy/retrieval): Retrieves matching content from shared corpus

Usage:
    python -m pmoves.tools.chit.chit_decoder --cgp cgp.json --corpus corpus.jsonl --mode auto

Author: PMOVES.AI
Date: 2026-02-08
Reference: pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
from typing import Any, Dict, List

import numpy as np
import pandas as pd

try:
    import faiss  # type: ignore
except Exception:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None

# Optional: T5 for learning-based decoder
try:
    from datasets import Dataset  # type: ignore
    from transformers import (  # type: ignore
        T5ForConditionalGeneration,
        T5Tokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )
    TRANSFORMERS_AVAILABLE = True
except Exception:
    TRANSFORMERS_AVAILABLE = False


# =============================================================================
# Utils
# =============================================================================


def load_cgp(fp: str) -> Dict[str, Any]:
    """Load CGP from JSON file."""
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def load_corpus(
    path: str, text_field: str = "text"
) -> List[str]:
    """
    Load corpus from JSONL, CSV, TXT, or directory of .txt files.

    Args:
        path: Path to corpus file or directory
        text_field: Field name for text in JSONL/CSV

    Returns:
        List of text strings
    """
    p = pathlib.Path(path)
    texts: List[str] = []

    if p.is_file():
        # JSONL (preferred)
        if p.suffix.lower() == ".jsonl":
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if text_field in rec and isinstance(rec[text_field], str):
                        texts.append(rec[text_field])
        # CSV
        elif p.suffix.lower() in [".csv", ".tsv"]:
            df = pd.read_csv(
                p,
                sep="\t" if p.suffix.lower() == ".tsv" else ",",
                dtype=str,
                keep_default_na=False,
            )
            if text_field not in df.columns:
                raise ValueError(
                    f"CSV missing column '{text_field}'. Columns: {df.columns.tolist()}"
                )
            texts = df[text_field].astype(str).tolist()
        # TXT
        elif p.suffix.lower() in [".txt"]:
            with open(p, "r", encoding="utf-8") as f:
                texts = [ln.strip() for ln in f if ln.strip()]
        else:
            raise ValueError(f"Unsupported file type: {p.suffix}")
    else:
        # Directory of .txt files
        for fp in sorted(p.glob("**/*.txt")):
            t = fp.read_text(encoding="utf-8").strip()
            if t:
                texts.append(t)

    if not texts:
        raise RuntimeError("No texts found in corpus source.")
    return texts


def embed_texts(
    texts: List[str], model_name: str, batch_size: int = 64
) -> np.ndarray:
    """Embed texts using sentence-transformers model."""
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers not installed")
    model = SentenceTransformer(model_name)
    vecs = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 128,
        normalize_embeddings=True,
    )
    return vecs.astype(np.float32)


def build_faiss_index(vecs: np.ndarray):
    """Build FAISS index for similarity search."""
    if faiss is None:
        raise RuntimeError("faiss-cpu not installed")
    d = vecs.shape[1]
    idx = faiss.IndexFlatIP(d)  # Inner product (cosine on normalized vectors)
    idx.add(vecs)
    return idx


def centers_from_minmax(rmin: float, rmax: float, bins: int) -> np.ndarray:
    """Generate bin centers from min/max range."""
    if bins <= 1:
        return np.array([(rmin + rmax) / 2.0], dtype=np.float32)
    return np.linspace(rmin, rmax, bins).astype(np.float32)


# =============================================================================
# Decoding Modes
# =============================================================================


def exact_decode(cgp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract texts from CGP if embedded in points.

    This is lossless - recovers original text directly from CGP.
    """
    out = []
    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            pts = const.get("points", [])
            for p in pts:
                # Check for direct text field
                if "text" in p and isinstance(p["text"], str) and p["text"].strip():
                    out.append({
                        "constellation_id": const.get("id", ""),
                        "super_id": s.get("id", ""),
                        "text": p["text"].strip(),
                        "proj": p.get("proj", None),
                        "conf": p.get("conf", None),
                    })
                # Check for base64-encoded text
                elif "text_b64" in p and isinstance(p["text_b64"], str):
                    import base64
                    try:
                        text = base64.b64decode(p["text_b64"]).decode("utf-8")
                        out.append({
                            "constellation_id": const.get("id", ""),
                            "super_id": s.get("id", ""),
                            "text": text.strip(),
                            "proj": p.get("proj", None),
                            "conf": p.get("conf", None),
                        })
                    except Exception:
                        pass
    return out


def geometry_only_decode(
    cgp: Dict[str, Any],
    corpus_texts: List[str],
    corpus_vecs: np.ndarray,
    per_constellation: int = 50,
    bin_sigma: float = 0.35,
    tau: float = 4.0,
) -> List[Dict[str, Any]]:
    """
    Reconstruct content by retrieving texts matching geometric constellations.

    Uses anchor direction and spectrum to select best-matching texts from corpus.
    """
    decoded: List[Dict[str, Any]] = []
    used = set()  # Avoid duplicates across constellations

    bins_count = int(cgp.get("meta", {}).get("bins", 8))

    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            anchor = np.array(const.get("anchor", []), dtype=np.float32)
            if anchor.ndim != 1 or anchor.size != corpus_vecs.shape[1]:
                # Skip if anchor dimension mismatches corpus
                continue

            # Compute projections of all corpus items onto anchor
            proj = corpus_vecs @ (anchor / (np.linalg.norm(anchor) + 1e-9))
            rmin, rmax = const.get("radial_minmax", [float(proj.min()), float(proj.max())])

            spectrum = np.array(
                const.get("spectrum", [1.0 / bins_count] * bins_count), dtype=np.float32
            )
            if spectrum.size != bins_count:
                # Pad/trim spectrum to match bins_count
                if spectrum.size < bins_count:
                    spectrum = np.pad(spectrum, (0, bins_count - spectrum.size), mode="edge")
                else:
                    spectrum = spectrum[:bins_count]
            spectrum = spectrum / (spectrum.sum() + 1e-9)

            centers = centers_from_minmax(rmin, rmax, bins_count)
            width = max((rmax - rmin) / max(bins_count, 2), 1e-3)
            sigma = max(width * bin_sigma, 1e-3)

            # Bin-wise selection to match spectrum proportions
            take_per_bin = np.maximum(1, np.round(spectrum * per_constellation)).astype(int)
            chosen_idxs: List[int] = []

            for b, c in enumerate(centers):
                # Weight candidates by closeness to bin center
                w = np.exp(-tau * ((proj - c) ** 2) / (2 * sigma * sigma))
                order = np.argsort(-w)
                picked = 0
                for i in order:
                    if i in used:
                        continue
                    chosen_idxs.append(int(i))
                    used.add(int(i))
                    picked += 1
                    if picked >= int(take_per_bin[b]):
                        break

            # Dedupe within constellation
            chosen_idxs = list(dict.fromkeys(chosen_idxs))[: int(per_constellation)]
            for i in chosen_idxs:
                decoded.append({
                    "super_id": s.get("id", ""),
                    "constellation_id": const.get("id", ""),
                    "corpus_idx": int(i),  # Include for metric computation
                    "text": corpus_texts[i],
                    "proj_est": float(proj[i]),
                })

    return decoded


# =============================================================================
# Metrics (Calibration)
# =============================================================================


def empirical_spectrum(vals: np.ndarray, rmin: float, rmax: float, bins: int) -> np.ndarray:
    """Compute empirical spectrum from values."""
    if rmax <= rmin + 1e-9:
        rmax = rmin + 1e-3
    hist, _ = np.histogram(vals, bins=bins, range=(rmin, rmax), density=False)
    hist = hist.astype(np.float64) / (hist.sum() + 1e-9)
    return hist


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Kullback-Leibler divergence."""
    p = np.clip(p, 1e-9, 1.0)
    q = np.clip(q, 1e-9, 1.0)
    return float((p * (np.log(p) - np.log(q))).sum())


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence."""
    m = 0.5 * (p + q)
    return 0.5 * kl_divergence(p, m) + 0.5 * kl_divergence(q, m)


def wasserstein_1d(p: np.ndarray, q: np.ndarray, delta: float = 1.0) -> float:
    """1D Wasserstein distance via CDF."""
    c1 = np.cumsum(p)
    c2 = np.cumsum(q)
    return float(np.sum(np.abs(c1 - c2)) * delta)


def compute_metrics(
    cgp: Dict[str, Any],
    decoded: List[Dict[str, Any]],
    corpus_texts: List[str],
    corpus_vecs: np.ndarray,
) -> Dict[str, Any]:
    """
    Compute reconstruction metrics per constellation.

    Returns KL, JS, Wasserstein, and coverage metrics.
    """
    # Group decoded by constellation
    by_const: Dict[str, List[Dict[str, Any]]] = {}
    for rec in decoded:
        by_const.setdefault(rec["constellation_id"], []).append(rec)

    bins = int(cgp.get("meta", {}).get("bins", 8))
    out_rows: List[Dict[str, Any]] = []

    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            cid = const.get("id", "")
            anchor = np.array(const.get("anchor", []), dtype=np.float32)
            if anchor.ndim != 1:
                continue

            items = by_const.get(cid, [])
            idxs = [it.get("corpus_idx") for it in items if "corpus_idx" in it]

            if not idxs:
                out_rows.append({
                    "constellation_id": cid,
                    "n": 0,
                    "KL": None,
                    "JS": None,
                    "W1": None,
                    "coverage": 0.0,
                })
                continue

            # Get or compute min/max
            rmin, rmax = const.get("radial_minmax", [None, None])
            if rmin is None or rmax is None:
                proj_all = corpus_vecs @ (anchor / (np.linalg.norm(anchor) + 1e-9))
                rmin, rmax = float(proj_all.min()), float(proj_all.max())

            spectrum_t = np.asarray(
                const.get("spectrum", [1.0 / bins] * bins), dtype=np.float64
            )

            # Empirical spectrum from decoded items
            proj_sel = corpus_vecs[idxs] @ (anchor / (np.linalg.norm(anchor) + 1e-9))
            spectrum_e = empirical_spectrum(proj_sel, rmin, rmax, bins)

            delta = (rmax - rmin) / max(1, bins - 1)

            # Get per_constellation target from CGP metadata (default 50)
            per_const_target = float(cgp.get("meta", {}).get("per_constellation", 50))

            out_rows.append({
                "constellation_id": cid,
                "n": len(idxs),
                "KL": kl_divergence(spectrum_t, spectrum_e),
                "JS": js_divergence(spectrum_t, spectrum_e),
                "W1": wasserstein_1d(spectrum_t, spectrum_e, delta=delta),
                "coverage": float(len(idxs)) / max(1.0, per_const_target),
            })

    # Compute means
    mean_vals = {
        "KL": np.nanmean([r["KL"] for r in out_rows if r["KL"] is not None]),
        "JS": np.nanmean([r["JS"] for r in out_rows if r["JS"] is not None]),
        "W1": np.nanmean([r["W1"] for r in out_rows if r["W1"] is not None]),
        "coverage": float(np.mean([r["coverage"] for r in out_rows])),
    }

    return {"constellations": out_rows, "mean": mean_vals}


# =============================================================================
# CLI
# =============================================================================


def main():
    ap = argparse.ArgumentParser(
        description="CHIT Decoder v0.1 (CGP → content)"
    )
    ap.add_argument("--cgp", required=True, help="Path to CGP JSON")
    ap.add_argument(
        "--corpus",
        help="Corpus source (JSONL/CSV/TXT or dir of .txt) for geometry-only decoding",
    )
    ap.add_argument("--text-field", default="text", help="Field name in JSONL/CSV for text")
    ap.add_argument(
        "--model", help="Sentence-Transformers model (defaults to CGP meta.backend)"
    )
    ap.add_argument(
        "--mode",
        choices=["auto", "exact", "geometry"],
        default="auto",
        help="Decoding mode",
    )
    ap.add_argument(
        "--per-constellation",
        type=int,
        default=50,
        help="Target texts per constellation in geometry mode",
    )
    ap.add_argument(
        "--bin-sigma", type=float, default=0.35, help="Bin width multiplier"
    )
    ap.add_argument(
        "--tau", type=float, default=4.0, help="Kernel sharpness"
    )
    ap.add_argument("--out", default="decoded_dataset.jsonl", help="Output JSONL")
    ap.add_argument("--report", default="reconstruction_report.md", help="Summary report")
    ap.add_argument(
        "--compute-metrics", action="store_true", help="Compute reconstruction metrics"
    )
    ap.add_argument(
        "--metrics-json", default="reconstruction_metrics.json", help="Metrics output"
    )

    args = ap.parse_args()

    # Load CGP
    cgp = load_cgp(args.cgp)
    backend_model = args.model or cgp.get("meta", {}).get(
        "backend", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Decide mode
    has_text_points = any(
        "points" in const
        and any(
            isinstance(p.get("text", ""), str) and p.get("text", "").strip()
            for p in const["points"]
        )
        for s in cgp.get("super_nodes", [])
        for const in s.get("constellations", [])
    )

    mode = args.mode
    if mode == "auto":
        mode = "exact" if has_text_points else "geometry"

    decoded: List[Dict[str, Any]] = []

    if mode == "exact":
        decoded = exact_decode(cgp)
        if not decoded and args.mode == "exact":
            raise RuntimeError("Exact mode requested but CGP carries no texts.")
        # Fall through to geometry if auto and empty
        if not decoded and args.corpus:
            mode = "geometry"

    if mode == "geometry":
        if not args.corpus:
            raise RuntimeError("Geometry mode requires --corpus to retrieve from.")
        texts = load_corpus(args.corpus, text_field=args.text_field)
        print(f"Loaded {len(texts)} corpus texts")
        vecs = embed_texts(texts, backend_model)
        decoded = geometry_only_decode(
            cgp,
            texts,
            vecs,
            per_constellation=args.per_constellation,
            bin_sigma=args.bin_sigma,
            tau=args.tau,
        )

        # Compute metrics if requested
        if args.compute_metrics:
            metrics = compute_metrics(cgp, decoded, texts, vecs)
            with open(args.metrics_json, "w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
            print(f"Saved metrics to {args.metrics_json}")

    if not decoded:
        raise RuntimeError("No decoded items produced.")

    # Write output
    with open(args.out, "w", encoding="utf-8") as f:
        for rec in decoded:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Generate report
    df = pd.DataFrame(decoded)
    by_const = df.groupby("constellation_id").size().sort_values(ascending=False)

    with open(args.report, "w", encoding="utf-8") as f:
        f.write("# CHIT Decoding Report\n\n")
        f.write(f"- Mode: **{mode}**\n")
        f.write(f"- Output: `{args.out}`\n")
        f.write(f"- Items: {len(df)}\n\n")
        f.write("## Items per Constellation\n\n")
        f.write(by_const.to_string() + "\n")

        if args.compute_metrics and mode == "geometry":
            # Load and append metrics
            with open(args.metrics_json, "r") as mf:
                metrics = json.load(mf)
            m = metrics["mean"]
            f.write("\n## Reconstruction Metrics\n\n")
            f.write(f"- Mean KL: {m['KL']:.4f}\n")
            f.write(f"- Mean JS: {m['JS']:.4f}\n")
            f.write(f"- Mean W1: {m['W1']:.4f}\n")
            f.write(f"- Mean coverage: {m['coverage']:.3f}\n")

    print(f"Saved: {args.out}, {args.report}")


if __name__ == "__main__":
    main()
