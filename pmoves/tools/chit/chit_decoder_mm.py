"""
CHIT Multi-Modal Decoder v0.1

Decodes CHIT Geometry Packets (CGP) to multi-modal content:
- Images: Using CLIP embeddings for visual-semantic matching
- Audio: Using CLAP embeddings for audio-semantic matching (optional)

Usage:
    python -m pmoves.tools.chit.chit_decoder_mm --cgp cgp.json --image-dir ./images

Author: PMOVES.AI
Date: 2026-02-08
Reference: pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODER_MULTIv0.1.md
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Tuple, List
from typing import Any, Dict

import numpy as np
from PIL import Image

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None

try:
    import torch  # type: ignore
except Exception:
    torch = None


# =============================================================================
# Utils
# =============================================================================


def load_cgp(fp: str) -> Dict[str, Any]:
    """Load CGP from JSON file."""
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def centers_from_minmax(rmin: float, rmax: float, bins: int) -> np.ndarray:
    """Generate bin centers from min/max range."""
    if bins <= 1:
        return np.array([(rmin + rmax) / 2.0], dtype=np.float32)
    return np.linspace(rmin, rmax, bins).astype(np.float32)


def soft_select(
    proj: np.ndarray,
    centers: np.ndarray,
    target: np.ndarray,
    tau: float = 4.0,
    per_const: int = 24,
) -> List[int]:
    """
    Select indices using soft kernel matching to target spectrum.

    Args:
        proj: Projection values of all items onto anchor
        centers: Bin centers
        target: Target spectrum distribution
        tau: Kernel sharpness
        per_const: Items per constellation

    Returns:
        List of selected indices
    """
    sigma = max((centers[-1] - centers[0]) / (len(centers) * 2), 1e-3)
    take = np.maximum(1, np.round(target / (target.sum() + 1e-9) * per_const)).astype(int)
    chosen: List[int] = []

    for b, c in enumerate(centers):
        # Gaussian kernel weight
        w = np.exp(-tau * (proj - c) ** 2 / (2 * sigma * sigma))
        order = np.argsort(-w)
        picked = 0
        for i in order:
            if i in chosen:
                continue
            chosen.append(int(i))
            picked += 1
            if picked >= int(take[b]):
                break

    return chosen


def encode_images(
    img_paths: List[str], model: SentenceTransformer
) -> Tuple[np.ndarray, List[str]]:
    """
    Encode images using CLIP model.

    Args:
        img_paths: List of image file paths
        model: SentenceTransformer with CLIP model

    Returns:
        Tuple of (normalized image embeddings, valid paths)
    """
    imgs = []
    valid_paths = []

    for p in img_paths:
        try:
            img = Image.open(p).convert("RGB")
            imgs.append(img)
            valid_paths.append(p)
        except Exception as e:
            print(f"Warning: Could not load {p}: {e}")

    if not imgs:
        raise RuntimeError("No valid images loaded")

    vecs = model.encode(
        imgs, batch_size=32, convert_to_numpy=True, normalize_embeddings=True
    )
    return vecs.astype(np.float32), valid_paths


# =============================================================================
# Image Decoding
# =============================================================================


def decode_images(
    cgp: Dict[str, Any],
    image_dir: str,
    model_name: str = "clip-ViT-B-32",
    per_constellation: int = 24,
    bins: int | None = None,
    tau: float = 4.0,
) -> List[Dict[str, Any]]:
    """
    Decode CGP to images using CLIP embeddings.

    Finds images whose visual content matches the geometric constellations.

    Args:
        cgp: CHIT Geometry Packet
        image_dir: Directory containing images
        model_name: CLIP model name (must match what was used to generate CGP)
        per_constellation: Target images per constellation
        bins: Number of bins (uses CGP meta if None)
        tau: Kernel sharpness for selection

    Returns:
        List of decoded image records with path and projection score
    """
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers not installed")

    # Load CLIP model
    print(f"Loading CLIP model: {model_name}")
    model = SentenceTransformer(model_name)

    # Find all images
    img_extensions = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
    img_paths = sorted([
        p
        for p in [
            os.path.join(root, f)
            for root, _, files in os.walk(image_dir)
            for f in files
        ]
        if p.lower().endswith(img_extensions)
    ])

    if not img_paths:
        raise RuntimeError(f"No images found in {image_dir}")

    print(f"Found {len(img_paths)} images")

    # Encode images
    vecs, valid_paths = encode_images(img_paths, model)
    print(f"Encoded {len(valid_paths)} images")

    results: List[Dict[str, Any]] = []
    bins_count = bins or int(cgp.get("meta", {}).get("bins", 8))

    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            anchor = np.array(const.get("anchor", []), dtype=np.float32)
            if anchor.ndim != 1:
                continue

            # Check dimension match
            if vecs.shape[1] != anchor.size:
                raise RuntimeError(
                    f"Anchor dimension ({anchor.size}) != image embedding dimension "
                    f"({vecs.shape[1]}). Regenerate CGP with CLIP text encoder."
                )

            # Project images onto anchor
            proj = vecs @ (anchor / (np.linalg.norm(anchor) + 1e-9))

            # Get or compute bounds
            rmin, rmax = const.get("radial_minmax", [float(proj.min()), float(proj.max())])

            # Get spectrum
            B = bins_count
            centers = centers_from_minmax(rmin, rmax, B)
            spectrum = np.asarray(
                const.get("spectrum", [1.0 / B] * B), dtype=np.float32
            )

            # Select images matching spectrum
            idxs = soft_select(proj, centers, spectrum, tau=tau, per_const=per_constellation)

            for i in idxs:
                results.append({
                    "super_id": s.get("id", ""),
                    "constellation_id": const.get("id", ""),
                    "path": valid_paths[i],
                    "proj_est": float(proj[i]),
                })

    return results


# =============================================================================
# Audio Decoding (Optional - CLAP)
# =============================================================================


def decode_audio(
    cgp: Dict[str, Any],
    audio_paths: List[str],
    clap_model: str = "laion/clap-httap-fusion",
    per_constellation: int = 16,
    tau: float = 4.0,
) -> List[Dict[str, Any]]:
    """
    Decode CGP to audio using CLAP embeddings.

    Note: This requires laion-clap installation:
        pip install laion-clap torch torchaudio

    Args:
        cgp: CHIT Geometry Packet (generated with CLAP text encoder)
        audio_paths: List of audio file paths
        clap_model: CLAP model name
        per_constellation: Target audio clips per constellation
        tau: Kernel sharpness

    Returns:
        List of decoded audio records
    """
    try:
        import laion_clap  # type: ignore
    except Exception:
        raise NotImplementedError(
            "Audio decode requires CLAP. Install with: pip install laion-clap torch torchaudio"
        )

    model = laion_clap.CLAP_Model(enable_fusion=True)
    model.load_ckpt()  # Uses default checkpoint

    # Encode audio files
    for path in audio_paths:
        # This is a placeholder - actual CLAP audio encoding would go here
        # The CLAP API is complex and varies by version
        pass

    raise NotImplementedError(
        "Audio decode requires CLAP text+audio embedding space. "
        "See CLAP documentation for implementation details."
    )


# =============================================================================
# CLI
# =============================================================================


def main():
    ap = argparse.ArgumentParser(
        description="CHIT Multi-Modal Decoder v0.1"
    )
    ap.add_argument("--cgp", required=True, help="Path to CGP JSON")
    ap.add_argument("--image-dir", help="Directory containing images")
    ap.add_argument("--audio-dir", help="Directory containing audio files")
    ap.add_argument(
        "--model",
        default="clip-ViT-B-32",
        help="CLIP model (must match CGP backend)",
    )
    ap.add_argument(
        "--per-constellation",
        type=int,
        default=24,
        help="Target items per constellation",
    )
    ap.add_argument("--bins", type=int, help="Override bins from CGP")
    ap.add_argument(
        "--tau", type=float, default=4.0, help="Kernel sharpness"
    )
    ap.add_argument(
        "--out", default="decoded_multimodal.jsonl", help="Output JSONL"
    )
    ap.add_argument(
        "--report", default="decoded_multimodal_report.md", help="Summary report"
    )

    args = ap.parse_args()

    cgp = load_cgp(args.cgp)

    results: List[Dict[str, Any]] = []

    # Image decoding
    if args.image_dir:
        print(f"Decoding images from {args.image_dir}")
        results = decode_images(
            cgp,
            args.image_dir,
            model_name=args.model,
            per_constellation=args.per_constellation,
            bins=args.bins,
            tau=args.tau,
        )

    # Audio decoding (not yet implemented)
    if args.audio_dir:
        print("Audio decoding not yet implemented")
        # results.extend(decode_audio(...))

    if not results:
        raise RuntimeError("No decoded items produced.")

    # Write output
    import pandas as pd

    with open(args.out, "w", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Generate report
    df = pd.DataFrame(results)

    with open(args.report, "w", encoding="utf-8") as f:
        f.write("# CHIT Multi-Modal Decoding Report\n\n")
        f.write(f"- Output: `{args.out}`\n")
        f.write(f"- Items: {len(df)}\n\n")

        if "constellation_id" in df.columns:
            by_const = df.groupby("constellation_id").size().sort_values(ascending=False)
            f.write("## Items per Constellation\n\n")
            f.write(by_const.to_string() + "\n")

        if "path" in df.columns:
            f.write("\n## Sample Results\n\n")
            f.write("| Constellation | Path | Score |\n")
            f.write("|---|---|---:|\n")
            for _, row in df.head(20).iterrows():
                f.write(
                    f"| {row.get('constellation_id', 'N/A')} | `{row.get('path', 'N/A')}` "
                    f"| {row.get('proj_est', 0):.4f} |\n"
                )

    print(f"Saved: {args.out}, {args.report}")


if __name__ == "__main__":
    main()
