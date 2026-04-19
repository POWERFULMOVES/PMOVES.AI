#!/usr/bin/env python3
"""CGP Decoder CLI — playback verification for CHIT Cognitive Geometry Packets.

Decodes a CGP JSON payload back to structured chunk references (exact mode)
or reconstructs text from geometric encoding using a corpus JSONL (geometry mode).

Usage:
    python pmoves/tools/chit_decoder.py --cgp geometry_payload.json --mode exact
    python pmoves/tools/chit_decoder.py --cgp geometry_payload.json --mode geometry --corpus chunks.jsonl --compute-metrics
    python pmoves/tools/chit_decoder.py --cgp geometry_payload.json --compute-metrics --output report.json

Standalone tool — no PMOVES-internal imports.
"""

import argparse
import json
import math
import statistics
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np


def load_cgp(path: str) -> dict:
    """Load and validate CGP JSON."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: CGP file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        print("ERROR: CGP root must be a JSON object", file=sys.stderr)
        sys.exit(1)
    if "super_nodes" not in data:
        print("WARNING: CGP has no 'super_nodes' field", file=sys.stderr)
    return data


def load_corpus(path: str) -> dict:
    """Load corpus JSONL into a dict keyed by 'id'."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: Corpus file not found: {path}", file=sys.stderr)
        sys.exit(1)
    corpus = {}
    with open(p, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARNING: Skipping malformed JSONL line {line_num}: {e}", file=sys.stderr)
                continue
            rid = record.get("id")
            if rid is not None:
                corpus[rid] = record
    print(f"Loaded {len(corpus)} corpus chunks from {path}", file=sys.stderr)
    return corpus


def kl_divergence_spectrum(spectrum: list, bins: int) -> float:
    """Compute KL(p || uniform) for a constellation spectrum.

    KL(p || u) = sum(p_i * log(p_i / u_i)) where u_i = 1/bins.
    Small epsilon added to avoid log(0).
    """
    eps = 1e-10
    p = np.array(spectrum, dtype=np.float64) + eps
    p = p / p.sum()
    u = np.full_like(p, 1.0 / bins)
    return float(np.sum(p * np.log(p / u)))


def decode_exact(cgp: dict) -> dict:
    """Decode CGP in exact mode — structure only, no corpus needed."""
    super_nodes_out = []
    for sn in cgp.get("super_nodes", []):
        constellations_out = []
        for constellation in sn.get("constellations", []):
            points = constellation.get("points", [])
            projections = [pt.get("proj", 0.0) for pt in points]
            point_ids = [pt.get("id") or pt.get("ref_id", "") for pt in points]
            mean_proj = round(float(statistics.mean(projections)), 4) if projections else None
            std_proj = round(float(statistics.stdev(projections)), 4) if len(projections) > 1 else 0.0
            constellations_out.append({
                "id": constellation.get("id", ""),
                "point_count": len(points),
                "points": point_ids,
                "mean_proj": mean_proj,
                "std_proj": std_proj,
            })
        super_nodes_out.append({
            "id": sn.get("id", ""),
            "label": sn.get("label", ""),
            "constellation_count": len(constellations_out),
            "constellations": constellations_out,
        })
    return {"super_nodes": super_nodes_out}


def decode_geometry(cgp: dict, corpus: dict) -> tuple:
    """Decode CGP in geometry mode — resolve point text against corpus.

    Returns:
        decode dict (same shape as exact) and a list of orphaned point refs.
    """
    orphaned = []
    super_nodes_out = []
    for sn in cgp.get("super_nodes", []):
        constellations_out = []
        for constellation in sn.get("constellations", []):
            points = constellation.get("points", [])
            projections = []
            point_ids = []
            for pt in points:
                ref_id = pt.get("ref_id") or pt.get("id", "")
                point_ids.append(ref_id)
                projections.append(pt.get("proj", 0.0))
                if ref_id not in corpus:
                    orphaned.append({
                        "point_id": ref_id,
                        "constellation_id": constellation.get("id", "")
                    })
            mean_proj = round(float(statistics.mean(projections)), 4) if projections else None
            std_proj = round(float(statistics.stdev(projections)), 4) if len(projections) > 1 else 0.0
            constellations_out.append({
                "id": constellation.get("id", ""),
                "point_count": len(points),
                "points": point_ids,
                "mean_proj": mean_proj,
                "std_proj": std_proj,
            })
        super_nodes_out.append({
            "id": sn.get("id", ""),
            "label": sn.get("label", ""),
            "constellation_count": len(constellations_out),
            "constellations": constellations_out,
        })
    return {"super_nodes": super_nodes_out}, orphaned


def compute_metrics(cgp: dict, mode: str, corpus: dict = None) -> dict:
    """Compute fidelity metrics: KL divergence, coverage, per-constellation fidelity."""
    meta = cgp.get("meta", {})
    bins = meta.get("bins", 8)

    # Gather all constellations from flat list, fall back to nested
    all_constellations = cgp.get("constellations", [])
    if not all_constellations:
        for sn in cgp.get("super_nodes", []):
            all_constellations.extend(sn.get("constellations", []))

    # KL divergence
    kl_values = []
    for constellation in all_constellations:
        spectrum = constellation.get("spectrum", [])
        if spectrum:
            kl_values.append(kl_divergence_spectrum(spectrum, bins))
    kl_mean = round(float(np.mean(kl_values)), 4) if kl_values else None
    kl_max = round(float(np.max(kl_values)), 4) if kl_values else None

    # Coverage
    coverage = None
    if corpus is not None:
        cgp_ref_ids = set()
        for sn in cgp.get("super_nodes", []):
            for constellation in sn.get("constellations", []):
                for pt in constellation.get("points", []):
                    rid = pt.get("ref_id") or pt.get("id", "")
                    if rid:
                        cgp_ref_ids.add(rid)
        for pt in cgp.get("points", []):
            rid = pt.get("ref_id") or pt.get("id", "")
            if rid:
                cgp_ref_ids.add(rid)
        total_corpus = len(corpus)
        matched = sum(1 for rid in cgp_ref_ids if rid in corpus)
        coverage = round(matched / total_corpus, 4) if total_corpus > 0 else 0.0
        print(f"Coverage: {matched}/{total_corpus} = {coverage}", file=sys.stderr)

    # Per-constellation fidelity
    fidelity_list = []
    for constellation in all_constellations:
        points = constellation.get("points", [])
        projections = [pt.get("proj", 0.0) for pt in points]
        orphaned_count = 0
        text_similarities = []
        for pt in points:
            ref_id = pt.get("ref_id") or pt.get("id", "")
            if corpus is not None and ref_id not in corpus:
                orphaned_count += 1
            if mode == "geometry" and corpus is not None and ref_id in corpus:
                point_text = pt.get("text", "") or ""
                corpus_content = corpus[ref_id].get("content", "") or ""
                if point_text and corpus_content:
                    ratio = SequenceMatcher(None, point_text, corpus_content[:512]).ratio()
                    text_similarities.append(ratio)
        mean_sim = round(float(statistics.mean(text_similarities)), 4) if text_similarities else None
        mean_proj = round(float(statistics.mean(projections)), 4) if projections else None
        std_proj = round(float(statistics.stdev(projections)), 4) if len(projections) > 1 else 0.0
        fidelity_list.append({
            "id": constellation.get("id", ""),
            "mean_proj": mean_proj,
            "std_proj": std_proj,
            "point_count": len(points),
            "orphaned_count": orphaned_count,
            "text_similarity": mean_sim,
        })

    return {
        "kl_divergence": {"mean": kl_mean, "max": kl_max},
        "coverage": coverage,
        "constellation_fidelity": fidelity_list,
    }


def count_points(cgp: dict) -> int:
    """Count total points across all super_nodes/constellations."""
    total = 0
    for sn in cgp.get("super_nodes", []):
        for constellation in sn.get("constellations", []):
            total += len(constellation.get("points", []))
    return total


def count_constellations(cgp: dict) -> int:
    """Count total constellations across all super_nodes."""
    total = 0
    for sn in cgp.get("super_nodes", []):
        total += len(sn.get("constellations", []))
    return total


def format_human(report: dict) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("CGP Decoder Report")
    lines.append("=" * 60)
    lines.append(f"Mode:           {report['mode']}")
    lines.append(f"CGP Spec:       {report.get('cgp_spec', 'N/A')}")
    lines.append(f"Summary:        {report.get('cgp_summary', 'N/A')}")
    lines.append(f"Super Nodes:    {report.get('super_node_count', 0)}")
    lines.append(f"Constellations: {report.get('constellation_count', 0)}")
    lines.append(f"Points:         {report.get('point_count', 0)}")
    lines.append("")
    decode = report.get("decode", {})
    for sn in decode.get("super_nodes", []):
        lines.append(f"\n[{sn['label']}] (id={sn['id']})")
        lines.append(f"  Constellations: {sn['constellation_count']}")
        for const in sn.get("constellations", []):
            lines.append(f"  \u2514 {const['id']}: {const['point_count']} pts, "
                         f"mean_proj={const['mean_proj']}, std_proj={const['std_proj']}")
            if const["points"]:
                for pid in const["points"]:
                    lines.append(f"      - {pid}")
    metrics = report.get("metrics")
    if metrics:
        lines.append(f"\n{'=' * 60}")
        lines.append("METRICS")
        lines.append("=" * 60)
        kl = metrics.get("kl_divergence", {})
        lines.append(f"KL Divergence:  mean={kl.get('mean', 'N/A')}, max={kl.get('max', 'N/A')}")
        lines.append(f"Coverage:       {metrics.get('coverage', 'N/A')}")
        lines.append("")
        lines.append("Per-constellation fidelity:")
        for fid in metrics.get("constellation_fidelity", []):
            sim_str = str(fid["text_similarity"]) if fid["text_similarity"] is not None else "N/A"
            lines.append(f"  {fid['id']}: proj={fid['mean_proj']}±{fid['std_proj']}, "
                         f"pts={fid['point_count']}, orphaned={fid['orphaned_count']}, "
                         f"sim={sim_str}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="CGP Decoder — playback verification for CHIT Cognitive Geometry Packets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
                "  %(prog)s --cgp geometry_payload.json --mode exact\n"
                "  %(prog)s --cgp geometry_payload.json --mode geometry --corpus chunks.jsonl --compute-metrics\n"
                "  %(prog)s --cgp geometry_payload.json --compute-metrics --output report.json\n",
    )
    parser.add_argument("--cgp", required=True, help="Path to CGP JSON file")
    parser.add_argument("--corpus", default=None, help="Path to corpus JSONL file (required for geometry mode)")
    parser.add_argument("--mode", choices=["exact", "geometry"], default="exact",
                        help="Decode mode (default: exact)")
    parser.add_argument("--compute-metrics", action="store_true",
                        help="Compute fidelity metrics")
    parser.add_argument("--output", default=None,
                        help="Path to output JSON report file (prints to stdout if not set)")
    args = parser.parse_args()

    # Load CGP
    print(f"Loading CGP from {args.cgp}...", file=sys.stderr)
    cgp = load_cgp(args.cgp)
    print(f"CGP spec: {cgp.get('spec', 'N/A')}", file=sys.stderr)
    sn_count = len(cgp.get("super_nodes", []))
    const_count = count_constellations(cgp)
    pt_count = count_points(cgp)
    print(f"Super nodes: {sn_count}, Constellations: {const_count}, Points: {pt_count}", file=sys.stderr)
    if pt_count == 0:
        print("WARNING: CGP contains zero points", file=sys.stderr)

    # Validate geometry mode requirements
    corpus = None
    if args.mode == "geometry":
        if not args.corpus:
            print("ERROR: --corpus is required for geometry mode", file=sys.stderr)
            sys.exit(1)
        corpus = load_corpus(args.corpus)

    # Decode
    print(f"Decoding in {args.mode} mode...", file=sys.stderr)
    if args.mode == "exact":
        decode = decode_exact(cgp)
    else:
        decode, orphaned = decode_geometry(cgp, corpus)
        if orphaned:
            print(f"WARNING: {len(orphaned)} orphaned points (ref_id not in corpus)", file=sys.stderr)
            for o in orphaned[:10]:
                print(f"  orphaned: {o['point_id']} (in {o['constellation_id']})", file=sys.stderr)
            if len(orphaned) > 10:
                print(f"  ... and {len(orphaned) - 10} more", file=sys.stderr)

    # Build report
    report = {
        "mode": args.mode,
        "cgp_spec": cgp.get("spec", ""),
        "cgp_summary": cgp.get("summary", ""),
        "super_node_count": sn_count,
        "constellation_count": const_count,
        "point_count": pt_count,
        "decode": decode,
    }

    # Metrics
    if args.compute_metrics:
        print("Computing metrics...", file=sys.stderr)
        report["metrics"] = compute_metrics(cgp, args.mode, corpus)

    # Output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(format_human(report))


if __name__ == "__main__":
    main()
