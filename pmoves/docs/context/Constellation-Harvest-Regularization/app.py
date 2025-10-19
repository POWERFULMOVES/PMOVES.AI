import os
import io
import json
import math
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gradio as gr

# ---- Parsers ----
from docx import Document
import traceback

# ---- Embeddings ----
# We try sentence-transformers. If unavailable (or offline), we fall back to HashingVectorizer.
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.decomposition import PCA

# Optional import guarded for environments without torch/models
_ST_MODEL = None
def _load_st_model():
    global _ST_MODEL
    if _ST_MODEL is not None:
        return _ST_MODEL
    try:
        from sentence_transformers import SentenceTransformer
        # A small, reliable model
        _ST_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return _ST_MODEL
    except Exception as e:
        return None

def _resolve_file_input(file_obj):
    """Return (bytes_io, display_name) for a variety of Gradio/HF file input shapes.
    Supports: tempfile objects, dicts with 'name'/'path'/'data', raw path strings, or bytes.
    """
    import io, os
    # 1) Dict shape (some Gradio environments)
    if isinstance(file_obj, dict):
        # Prefer an on-disk path if present
        for key in ("path", "name"):
            p = file_obj.get(key)
            if isinstance(p, str) and os.path.exists(p):
                with open(p, "rb") as f:
                    return io.BytesIO(f.read()), os.path.basename(p)
        # Raw bytes in 'data'
        data = file_obj.get("data")
        if isinstance(data, (bytes, bytearray)):
            return io.BytesIO(bytes(data)), file_obj.get("orig_name", "upload.docx")
    # 2) Tempfile-like object
    if hasattr(file_obj, "read") and hasattr(file_obj, "name"):
        try:
            file_obj.seek(0)
            content = file_obj.read()
            if isinstance(content, (bytes, bytearray)):
                return io.BytesIO(content), os.path.basename(getattr(file_obj, "name", "upload.docx"))
        except Exception:
            pass
        # Fallback: open by path
        p = getattr(file_obj, "name", None)
        if isinstance(p, str) and os.path.exists(p):
            with open(p, "rb") as f:
                return io.BytesIO(f.read()), os.path.basename(p)
    # 3) Path string
    if isinstance(file_obj, str) and os.path.exists(file_obj):
        with open(file_obj, "rb") as f:
            import os
            return io.BytesIO(f.read()), os.path.basename(file_obj)
    # 4) Raw bytes
    if isinstance(file_obj, (bytes, bytearray)):
        return io.BytesIO(bytes(file_obj)), "upload.docx"
    # Unknown shape
    return None, "upload.docx"

def read_docx_any(file_obj) -> List[str]:
    bio, _ = _resolve_file_input(file_obj)
    if bio is None:
        raise ValueError("Could not read uploaded .docx file; unsupported input shape.")
    doc = Document(bio)
    paras = [p.text.strip() for p in doc.paragraphs]
    paras = [p for p in paras if p and not p.isspace()]
    return paras

def _basic_sentence_split(text: str) -> List[str]:
    # Lightweight sentence split without external downloads
    # Splits on '.', '?', '!' and line breaks, keeping reasonable length.
    import re
    rough = re.split(r'[\n\r]+|(?<=[\.\!\?])\s+', text.strip())
    out = []
    for s in rough:
        s = s.strip()
        if len(s) > 0:
            out.append(s)
    return out

def paragraphs_to_units(paras: List[str], mode: str = "paragraphs") -> List[str]:
    if mode == "paragraphs":
        return paras
    elif mode == "sentences":
        units = []
        for p in paras:
            units.extend(_basic_sentence_split(p))
        return units
    else:
        return paras

def embed_texts(texts: List[str], prefer_sentence_transformer: bool = True) -> Tuple[np.ndarray, str]:
    """
    Returns L2-normalized embeddings [N, d] and a string describing the backend.
    Tries SentenceTransformer; if not available, falls back to HashingVectorizer.
    """
    texts = [t if isinstance(t, str) else str(t) for t in texts]
    if prefer_sentence_transformer:
        model = _load_st_model()
        if model is not None:
            try:
                vecs = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
                return vecs.astype(np.float32), "sentence-transformers/all-MiniLM-L6-v2"
            except Exception as e:
                pass

    # Fallback: HashingVectorizer + l2 normalize
    hv = HashingVectorizer(n_features=768, alternate_sign=False, norm=None)
    X = hv.transform(texts)
    # Convert sparse to dense carefully (for small docs; fine for demo)
    vecs = X.toarray().astype(np.float32)
    # L2 normalize
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    vecs = vecs / norms
    return vecs, "HashingVectorizer(768d) fallback"

# ---- CHR Core ----

def softmax(x, axis=-1):
    x = x - np.max(x, axis=axis, keepdims=True)
    ex = np.exp(x)
    return ex / (np.sum(ex, axis=axis, keepdims=True) + 1e-9)

def global_range_entropy(p: np.ndarray) -> float:
    """
    p: [N, K] soft assignments.
    m_j = mean_i p_ij
    H_g = - sum_j m_j log m_j
    """
    m = p.mean(axis=0)  # [K]
    m_safe = np.clip(m, 1e-12, None)
    return float(-(m_safe * np.log(m_safe)).sum())

def soft_slab_entropy(z: np.ndarray, U: np.ndarray, bins: int = 8, tau: float = 5.0) -> float:
    """
    z: [N, d] normalized embeddings
    U: [K, d] anchor directions (assumed normalized)
    Returns average entropy across anchors of a soft histogram over projected coordinates.
    """
    # Projections
    t = z @ U.T  # [N, K]
    K = U.shape[0]
    Hs = []
    for j in range(K):
        tj = t[:, j]
        tmin, tmax = float(tj.min()), float(tj.max())
        if not np.isfinite(tmin) or not np.isfinite(tmax) or tmax - tmin < 1e-6:
            Hs.append(0.0)
            continue
        centers = np.linspace(tmin, tmax, bins)
        # Soft assignment to bins via RBF(-tau * (t - c)^2)
        # [N, bins]
        dist2 = (tj[:, None] - centers[None, :]) ** 2
        weights = softmax(-tau * dist2, axis=1)
        hist = weights.mean(axis=0)  # [bins]
        hist = np.clip(hist, 1e-12, None)
        H = float(-(hist * np.log(hist)).sum())
        Hs.append(H)
    return float(np.mean(Hs)) if len(Hs) > 0 else 0.0

def kmeans_plus_plus_init(z: np.ndarray, K: int, rng: np.random.RandomState) -> np.ndarray:
    # Returns K unit vectors chosen by k-means++ over cosine distance.
    # Hardened against negative/NaN probabilities via clipping and uniform fallbacks.
    N, d = z.shape
    inds = []
    # Pick first randomly
    inds.append(rng.randint(0, N))
    centers = [z[inds[0]]]
    # Distances to nearest center: cosine distance = 1 - cos(theta)
    cos0 = np.clip(z @ centers[0], -1.0, 1.0)
    d2 = 1.0 - cos0
    d2 = np.clip(d2, 1e-12, None)
    for _ in range(1, K):
        s = d2.sum()
        if not np.isfinite(s) or s <= 0:
            probs = np.full(N, 1.0 / N)
        else:
            probs = d2 / s
            probs = np.clip(probs, 0.0, None)
            s2 = probs.sum()
            if s2 <= 0 or not np.isfinite(s2):
                probs = np.full(N, 1.0 / N)
            else:
                probs = probs / s2
        next_idx = rng.choice(N, p=probs)
        inds.append(next_idx)
        centers.append(z[next_idx])
        cos_new = np.clip(z @ z[next_idx], -1.0, 1.0)
        d2 = np.minimum(d2, 1.0 - cos_new)
        d2 = np.clip(d2, 1e-12, None)
    U = np.stack(centers, axis=0)
    U = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)
    return U

def chr_optimize(z: np.ndarray, K: int = 8, iters: int = 30, beta: float = 12.0, bins: int = 8, tau: float = 5.0, seed: int = 42):
    """
    Unsupervised CHR optimizer:
    - Initialize K anchor directions U via k-means++ on cosine distance.
    - Iterate:
        p_ij = softmax(beta * z_i · U_j)
        U_j = normalize( sum_i p_ij * z_i )
    Returns final U, p, trajectories of global entropy and slab entropy.
    """
    rng = np.random.RandomState(seed)
    N, d = z.shape
    U = kmeans_plus_plus_init(z, K, rng) if N >= K else np.pad(z, ((0, max(0, K - N)), (0, 0)), mode='wrap')[:K]
    # Normalize
    U = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)

    # Initial measures
    logits0 = beta * (z @ U.T)  # [N, K]
    p0 = softmax(logits0, axis=1)
    Hg0 = global_range_entropy(p0)
    Hs0 = soft_slab_entropy(z, U, bins=bins, tau=tau)

    Hg_traj = [Hg0]
    Hs_traj = [Hs0]

    for _ in range(iters):
        logits = beta * (z @ U.T)  # [N, K]
        p = softmax(logits, axis=1)  # [N, K]
        # Update anchors as weighted means
        numer = p.T @ z  # [K, d]
        # Avoid empty
        denom = p.sum(axis=0)[:, None] + 1e-9
        U = numer / denom
        # Normalize
        U = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)

        Hg = global_range_entropy(p)
        Hs = soft_slab_entropy(z, U, bins=bins, tau=tau)
        Hg_traj.append(Hg)
        Hs_traj.append(Hs)

    # Final assignments
    logits = beta * (z @ U.T)
    p = softmax(logits, axis=1)
    return U, p, np.array(Hg_traj), np.array(Hs_traj)

def compute_mhep(Hg_traj: np.ndarray, Hs_traj: np.ndarray, K: int, bins: int, w_g: float = 0.7, w_s: float = 0.3) -> float:
    """
    Maximum Harvestable Energy Potential (MHEP) as a percentage.
    Normalizes entropy drops by theoretical maxima (log K for global, log bins for slab).
    """
    if len(Hg_traj) < 2 or len(Hs_traj) < 2:
        return 0.0
    maxHg = math.log(max(K, 2))
    maxHs = math.log(max(bins, 2))

    drop_g = max(0.0, float(Hg_traj[0] - Hg_traj[-1])) / (maxHg + 1e-9)
    drop_s = max(0.0, float(Hs_traj[0] - Hs_traj[-1])) / (maxHs + 1e-9)
    score = 100.0 * (w_g * drop_g + w_s * drop_s)
    # Clamp to [0, 100]
    return float(np.clip(score, 0.0, 100.0))

def structure_outputs(texts: List[str], z: np.ndarray, U: np.ndarray, p: np.ndarray) -> Tuple[pd.DataFrame, Dict[int, str]]:
    """
    Create a structured table sorted by constellation and radial order,
    and summarize each constellation with top keywords.
    """
    N, d = z.shape
    K = U.shape[0]
    # Hard labels for convenience
    labels = p.argmax(axis=1)
    # Radial coordinate per anchor
    proj = z @ U.T  # [N, K]
    radial = proj[np.arange(N), labels]

    df = pd.DataFrame({
        "constellation": labels.astype(int),
        "radial_order": radial,
        "text": texts,
        "char_len": [len(t) for t in texts],
        "word_count": [len(t.split()) for t in texts],
        "confidence": p.max(axis=1)
    })
    # Sort by constellation then decreasing radial (farther along the ray first)
    df = df.sort_values(by=["constellation", "radial_order"], ascending=[True, False]).reset_index(drop=True)

    # Constellation summaries via TF-IDF per cluster
    summaries = {}
    for j in range(K):
        cluster_texts = [texts[i] for i in range(N) if labels[i] == j]
        if len(cluster_texts) == 0:
            summaries[j] = "(empty)"
            continue
        # Build a simple corpus: cluster as doc, others as background
        corpus = [" ".join(cluster_texts), " ".join([texts[i] for i in range(N) if labels[i] != j])]
        try:
            tfidf = TfidfVectorizer(max_features=1000, ngram_range=(1,2), stop_words="english")
            X = tfidf.fit_transform(corpus)
            vocab = np.array(tfidf.get_feature_names_out())
            # Take top terms for the cluster doc (row 0) relative to background (row 1)
            scores = (X[0].toarray()[0] - X[1].toarray()[0])
            idx = np.argsort(-scores)[:8]
            top_terms = [vocab[i] for i in idx if scores[i] > 0]
            summaries[j] = ", ".join(top_terms[:8]) if top_terms else "(generic)"
        except Exception as e:
            summaries[j] = "(summary unavailable)"

    return df, summaries

def pca_plot(z: np.ndarray, U: np.ndarray, labels: np.ndarray, out_path: str):
    """
    2D PCA plot of points colored by constellation, with anchor stars.
    NOTE: We do not set any explicit colors or styles per instruction.
    """
    if z.shape[1] > 2:
        pca = PCA(n_components=2, random_state=0)
        Z2 = pca.fit_transform(z)
        U2 = pca.transform(U)
    else:
        Z2 = z
        U2 = U

    plt.figure(figsize=(6, 5))
    # Points
    plt.scatter(Z2[:, 0], Z2[:, 1], s=14, alpha=0.8, c=labels)
    # Anchors
    plt.scatter(U2[:, 0], U2[:, 1], marker="*", s=180)
    plt.title("Constellation Map (PCA)")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def process_pipeline(docx_file, units_mode, K, iters, beta, bins, tau, seed):
    if docx_file is None:
        return gr.update(value="# Please upload a .docx file."), None, None, None, None

    # Read file
    paras = read_docx_any(docx_file)
    units = paragraphs_to_units(paras, mode=units_mode)

    if len(units) == 0:
        return gr.update(value="# The document appears to be empty."), None, None, None, None

    # Embed
    Z, backend = embed_texts(units, prefer_sentence_transformer=True)

    # CHR optimize
    U, p, Hg_traj, Hs_traj = chr_optimize(Z, K=int(K), iters=int(iters), beta=float(beta), bins=int(bins), tau=float(tau), seed=int(seed))
    labels = p.argmax(axis=1)

    # Scores
    Hg0, HgT = float(Hg_traj[0]), float(Hg_traj[-1])
    Hs0, HsT = float(Hs_traj[0]), float(Hs_traj[-1])
    mhep = compute_mhep(Hg_traj, Hs_traj, K=int(K), bins=int(bins))

    # Structure
    df, summaries = structure_outputs(units, Z, U, p)

    # Exports
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "constellations.csv")
    json_path = os.path.join(tmpdir, "constellations.json")
    plot_path = os.path.join(tmpdir, "constellations_pca.png")

    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    # Plot
    pca_plot(Z, U, labels, plot_path)

    # Markdown report
    md = []
    md.append("# Constellation Harvest Regularization (CHR)")
    md.append("**Backend embeddings:** " + str(backend))
    md.append("")
    md.append(f"**K (constellations):** {K} &nbsp;&nbsp; **Iterations:** {iters} &nbsp;&nbsp; **Beta:** {beta}")
    md.append(f"**Bins:** {bins} &nbsp;&nbsp; **Tau:** {tau}")
    md.append("")
    md.append("## Harvest Metrics")
    md.append(f"- Global range entropy (start → end): **{Hg0:.4f} → {HgT:.4f}**")
    md.append(f"- Slab entropy (start → end): **{Hs0:.4f} → {HsT:.4f}**")
    md.append(f"- **Maximum Harvestable Energy Potential (MHEP): {mhep:.1f}%**")
    md.append("")
    md.append("## Constellation Summaries")
    for j in range(int(K)):
        md.append(f"- **Constellation {j}**: {summaries.get(j, '(n/a)')}")

    report_md = "\n".join(md)

    return report_md, plot_path, df, csv_path, json_path


# ----------------- Gradio UI -----------------

INTRO_MD = """
# Constellation Harvest Regularization (CHR)
**Arrange your document into data constellations for maximum harvestable energy.**  
Upload a **.docx** file. We embed each unit (paragraphs or sentences), then **optimize a set of constellation directions** to **reduce range entropy** and **align slabs** (the CHR principle).  
You’ll get:
- A **harvest score** (MHEP) showing how much structure we extracted.
- A **constellation map** (2D PCA) with anchors (★) and your units as points.
- A **structured table** grouped by constellation and ordered along each ray.
- **CSV/JSON** exports for your pipeline.
"""

HOW_MD = """
## How it Works (Short Version)
- We convert your document into units (**paragraphs** by default; you can switch to **sentences**).
- We compute embeddings (MiniLM or a local fallback).
- We initialize **K** anchor directions and iteratively adjust them to **lower the global range entropy** while forming **low-entropy slabs** along each anchor.
- The **Maximum Harvestable Energy Potential (MHEP)** combines the normalized drop in global and slab entropy.
- We then **group units by constellation** and **order them radially**, making the dataset easier to exploit downstream (routing, chunking, sparsity).

**Tip:** Increase **K** for more granular constellations; increase **iterations** or **beta** for sharper structures.
"""

with gr.Blocks(title="Constellation Harvest Regularization (CHR)") as demo:
    gr.Markdown(INTRO_MD)

    with gr.Row():
        with gr.Column(scale=1):
            docx_file = gr.File(label=".docx document", file_types=[".docx"], file_count="single")
            units_mode = gr.Radio(choices=["paragraphs", "sentences"], value="paragraphs", label="Unit granularity")
            K = gr.Slider(2, 24, value=8, step=1, label="K (number of constellations)")
            iters = gr.Slider(5, 100, value=30, step=1, label="Iterations")
            beta = gr.Slider(2, 30, value=12, step=1, label="Beta (softmax sharpness)")
            bins = gr.Slider(3, 16, value=8, step=1, label="Bins (slab histogram)")
            tau = gr.Slider(1, 20, value=5, step=1, label="Tau (slab softness)")
            seed = gr.Slider(0, 9999, value=42, step=1, label="Seed")

            run_btn = gr.Button("Process", variant="primary")

        with gr.Column(scale=1):
            report_md = gr.Markdown("# Upload a file to begin.")
            plot = gr.Image(label="Constellation Map (PCA)", type="filepath")
            gr.Markdown(HOW_MD)

    df_out = gr.Dataframe(label="Structured Output (head)", wrap=True, interactive=False)
    with gr.Row():
        csv_out = gr.File(label="Download CSV")
        json_out = gr.File(label="Download JSON")

    # Wiring
    run_btn.click(process_pipeline,
                  inputs=[docx_file, units_mode, K, iters, beta, bins, tau, seed],
                  outputs=[report_md, plot, df_out, csv_out, json_out])

if __name__ == "__main__":
    demo.launch()