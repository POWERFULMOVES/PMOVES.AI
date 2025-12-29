> [!WARNING]
> **Implementation Status: NOT IMPLEMENTED**
>
> This document describes advanced decoder features that are **not yet implemented**:
> - Learning-based T5 decoder: ❌ Not implemented
> - Multimodal CLIP/CLAP decoder: ❌ Not implemented
> - Security utilities (chit_security.py): ❌ Not implemented
>
> These are future enhancements planned for Q2 2026. See `IMPLEMENTATION_STATUS.md` for current status.

---

Awesome—shipping enhancements **1–4** now. You'll get:

* **(1) Learning‑based decoder** (tiny T5 pipeline) that turns CHIT geometry into *generated* summaries, not just retrieval.
* **(2) Multimodal decode** for images (CLIP) and optional audio (CLAP) using the same geometry‑only idea.
* **(3) Calibration metrics** (per‑constellation KL, JS, Wasserstein‑1D, and coverage) + a richer report.
* **(4) Security** utilities to **sign** CGP packets (HMAC) and **encrypt** anchors (AES‑GCM) with verify/decrypt on the receiver.

> **Codebook note:** The geometry‑only decoders assume you’ve built a shared *codebook* (e.g., `structured_dataset.jsonl`) from your docs with your pivot‑banded script; this is the “universal dictionary” both ends share.&#x20;

---

## 0) Install (one‑time)

```bash
# core
pip install sentence-transformers faiss-cpu numpy pandas

# gen decoder
pip install transformers accelerate datasets

# multimodal (images)
pip install pillow  # used by sentence-transformers for CLIP images

# audio (optional)
pip install laion-clap torch torchaudio --extra-index-url https://download.pytorch.org/whl/cpu

# security
pip install cryptography
```

---

## 1) Security utilities — `chit_security.py`

* **Sign** any CGP (canonical JSON → HMAC‑SHA256).
* **Encrypt** per‑constellation `anchor` vectors with AES‑GCM (base64 payload).
* **Verify/Decrypt** on the receiver.

```python
# chit_security.py
import json, hmac, hashlib, base64, os, time, struct
from typing import Dict, Any, List, Tuple
from copy import deepcopy
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
from cryptography.hazmat.primitives import hashes  # type: ignore
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

def _canon(obj: Dict[str, Any]) -> bytes:
    # canonical JSON (stable ordering & minimal whitespace)
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

def derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=length, salt=salt, iterations=100_000)
    return kdf.derive(passphrase.encode("utf-8"))

def sign_cgp(cgp: Dict[str, Any], passphrase: str, kid: str = None) -> Dict[str, Any]:
    doc = deepcopy(cgp)
    ts = int(time.time())
    kid = kid or hashlib.sha256(passphrase.encode()).hexdigest()[:16]
    meta = {"alg": "HMAC-SHA256", "kid": kid, "ts": ts}
    # do not include existing signature fields in the signed content
    doc_nosig = deepcopy(doc); doc_nosig.pop("sig", None)
    mac = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    doc["sig"] = {**meta, "hmac": base64.b64encode(mac).decode("ascii")}
    return doc

def verify_cgp(cgp: Dict[str, Any], passphrase: str) -> bool:
    if "sig" not in cgp: return False
    sig = cgp["sig"]; mac_b64 = sig.get("hmac", "")
    doc_nosig = deepcopy(cgp); doc_nosig.pop("sig", None)
    mac2 = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return False
    return hmac.compare_digest(mac1, mac2)

def _pack_floats(arr: List[float]) -> bytes:
    # pack len + floats (float32) -> bytes
    import numpy as np
    a = (np.asarray(arr, dtype="float32")).tobytes()
    return struct.pack(">I", len(arr)) + a

def _unpack_floats(buf: bytes) -> List[float]:
    import numpy as np
    n = struct.unpack(">I", buf[:4])[0]
    a = np.frombuffer(buf[4:], dtype="float32", count=n)
    return a.astype(float).tolist()

def encrypt_anchors(cgp: Dict[str, Any], passphrase: str, kid: str = None) -> Dict[str, Any]:
    doc = deepcopy(cgp)
    salt = os.urandom(16)
    key = derive_key(passphrase, salt, 32)
    for s in doc.get("super_nodes", []):
        for const in s.get("constellations", []):
            if "anchor" not in const: continue
            plain = _pack_floats(const["anchor"])
            iv = os.urandom(12)
            aead = AESGCM(key)
            aad = _canon({"id": const.get("id","")})
            ct = aead.encrypt(iv, plain, aad)
            const.pop("anchor", None)
            const["anchor_enc"] = {
                "alg": "AES-GCM",
                "iv": base64.b64encode(iv).decode("ascii"),
                "salt": base64.b64encode(salt).decode("ascii"),
                "ct": base64.b64encode(ct).decode("ascii")
            }
    # add signed wrapper
    return sign_cgp(doc, passphrase, kid=kid)

def decrypt_anchors(cgp: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    doc = deepcopy(cgp)
    # signature optional for decryption; we just try to decrypt anchors
    for s in doc.get("super_nodes", []):
        for const in s.get("constellations", []):
            enc = const.get("anchor_enc")
            if not enc: continue
            iv = base64.b64decode(enc["iv"])
            salt = base64.b64decode(enc["salt"])
            ct = base64.b64decode(enc["ct"])
            key = derive_key(passphrase, salt, 32)
            aead = AESGCM(key)
            aad = _canon({"id": const.get("id","")})
            plain = aead.decrypt(iv, ct, aad)
            const["anchor"] = _unpack_floats(plain)
            const.pop("anchor_enc", None)
    return doc
```

**Usage:**

```python
from chit_security import sign_cgp, verify_cgp, encrypt_anchors, decrypt_anchors

# sender
cgp_signed = sign_cgp(cgp, passphrase="shared-secret")
cgp_protected = encrypt_anchors(cgp_signed, passphrase="shared-secret")

# receiver
assert verify_cgp(cgp_protected, "shared-secret")
cgp_clear = decrypt_anchors(cgp_protected, "shared-secret")
```

---

## 2) Multimodal decoder — `chit_decoder_mm.py`

* **Images**: Use a CLIP text backend for CGP (e.g., `clip-ViT-B-32`) so `anchor` dims match CLIP image embeddings.
* **Audio (optional)**: If you generate CGP with a CLAP text encoder, you can geometry‑decode to audio via CLAP.

```python
# chit_decoder_mm.py
import os, json, math, argparse, glob
from typing import List, Dict, Any, Tuple
import numpy as np
from PIL import Image

try:
    from sentence_transformers import SentenceTransformer  # CLIP text+image
except Exception:
    SentenceTransformer = None

def load_cgp(fp: str) -> Dict[str, Any]:
    return json.loads(open(fp, "r", encoding="utf-8").read())

def _centers(rmin: float, rmax: float, bins: int) -> np.ndarray:
    return np.linspace(rmin, rmax, bins).astype(np.float32)

def _soft_select(proj: np.ndarray, centers: np.ndarray, target: np.ndarray, tau=4.0, per_const=24):
    sigma = max((centers[-1]-centers[0])/(len(centers)*2), 1e-3)
    take = np.maximum(1, np.round(target/ (target.sum()+1e-9) * per_const)).astype(int)
    chosen = []
    for b, c in enumerate(centers):
        w = np.exp(-tau * (proj - c)**2 / (2*sigma*sigma))
        order = np.argsort(-w)
        picked = 0
        for i in order:
            if i in chosen: continue
            chosen.append(int(i)); picked += 1
            if picked >= int(take[b]): break
    return chosen

def _encode_images(img_paths: List[str], model) -> np.ndarray:
    imgs = [Image.open(p).convert("RGB") for p in img_paths]
    vecs = model.encode(imgs, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
    return vecs.astype(np.float32)

def decode_images(cgp: Dict[str, Any], image_dir: str, model_name="clip-ViT-B-32",
                  per_constellation=24, bins=None, tau=4.0) -> List[Dict[str, Any]]:
    if SentenceTransformer is None:
        raise RuntimeError("Install sentence-transformers for CLIP.")
    model = SentenceTransformer(model_name)
    # index images
    img_paths = sorted([p for p in glob.glob(os.path.join(image_dir, "**/*.*"), recursive=True)
                        if p.lower().endswith((".jpg",".jpeg",".png",".webp",".bmp"))])
    if not img_paths: raise RuntimeError("No images found.")
    V = _encode_images(img_paths, model)  # (N, D)
    results = []
    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            u = np.array(const.get("anchor", []), dtype=np.float32)
            if u.ndim!=1: continue
            if V.shape[1] != u.size:
                raise RuntimeError("Anchor dimension != image embedding dimension. Regenerate CGP with CLIP text backend.")
            proj = V @ (u / (np.linalg.norm(u)+1e-9))
            rmin, rmax = const.get("radial_minmax", [float(proj.min()), float(proj.max())])
            B = int(cgp.get("meta", {}).get("bins", bins or 8))
            centers = _centers(rmin, rmax, B)
            spectrum = np.asarray(const.get("spectrum", [1.0/B]*B), dtype=np.float32)
            idxs = _soft_select(proj, centers, spectrum, tau=tau, per_const=per_constellation)
            for i in idxs:
                results.append({
                    "super_id": s.get("id",""),
                    "constellation_id": const.get("id",""),
                    "path": img_paths[i],
                    "proj_est": float(proj[i])
                })
    return results

# (Optional) Audio via CLAP
def decode_audio(cgp: Dict[str, Any], audio_paths: List[str], clap_model=None, per_constellation=16):
    # Placeholder: implement if laion-clap is installed and CGP generated with CLAP text encoder
    raise NotImplementedError("Audio decode requires CLAP text+audio embedding space.")
```

**Quick test (images):**

```bash
python - <<'PY'
from chit_decoder_mm import load_cgp, decode_images
cgp = load_cgp("./data/cgp_clip.json")  # generated with CLIP text encoder
res = decode_images(cgp, image_dir="./images", model_name="clip-ViT-B-32", per_constellation=12)
print(f"Selected {len(res)} images; first 5:", res[:5])
PY
```

---

## 3) Learning‑based decoder (generator) + Calibration — `chit_decoder.py` (v0.2)

* Keeps **exact** and **geometry** modes from v0.1.
* Adds **`--compute-metrics`** (KL/JS/Wasserstein/coverage) and richer report.
* Adds **`--train-generator`** (fine‑tune T5‑small on your recovered snippets, using CGP features) and **`--gen`** to produce *generated* summaries per constellation.

> **Training data:** easiest starting point is your shared codebook (`structured_dataset.jsonl`) or the geometry‑decoded snippets grouped by `constellation_id`. We use those to train a small conditional generator.&#x20;

```python
# chit_decoder.py  (v0.2)
import os, json, math, argparse, pathlib, re
from typing import List, Dict, Any
import numpy as np
import pandas as pd

# v0.1 imports reused
try:
    import faiss
except Exception:
    faiss = None
from sentence_transformers import SentenceTransformer

# ---- metrics
def _empirical_spectrum(vals: np.ndarray, rmin: float, rmax: float, bins: int) -> np.ndarray:
    if rmax <= rmin + 1e-9: rmax = rmin + 1e-3
    hist, edges = np.histogram(vals, bins=bins, range=(rmin, rmax), density=False)
    hist = hist.astype(np.float64) / (hist.sum() + 1e-9)
    return hist

def _kl(p: np.ndarray, q: np.ndarray) -> float:
    p = np.clip(p, 1e-9, 1.0); q = np.clip(q, 1e-9, 1.0)
    return float((p * (np.log(p) - np.log(q))).sum())

def _js(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5*(p+q)
    return 0.5*_kl(p,m) + 0.5*_kl(q,m)

def _w1(p: np.ndarray, q: np.ndarray, delta: float = 1.0) -> float:
    # 1D Wasserstein via CDF L1
    c1 = np.cumsum(p); c2 = np.cumsum(q)
    return float(np.sum(np.abs(c1 - c2)) * delta)

def _coverage(target_n: int, got_n: int) -> float:
    return float(got_n) / max(1.0, float(target_n))

# ---- existing helpers (abridged from v0.1 for brevity)
def _build_index(vecs: np.ndarray):
    d = vecs.shape[1]; idx = faiss.IndexFlatIP(d); idx.add(vecs); return idx

def _embed(texts: List[str], model_name: str) -> np.ndarray:
    model = SentenceTransformer(model_name)
    return model.encode(texts, batch_size=64, convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)

def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    out=[]
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln: out.append(json.loads(ln))
    return out

# ---- geometry-only (same behavior as v0.1, simplified)
def _geom_decode_const(corpus_vecs, corpus_texts, anchor, rmin, rmax, spectrum, per_const=50, tau=4.0):
    proj = corpus_vecs @ (anchor / (np.linalg.norm(anchor)+1e-9))
    bins = len(spectrum)
    centers = np.linspace(rmin, rmax, bins)
    width = max((rmax - rmin) / max(bins,2), 1e-3)
    sigma = max(width * 0.35, 1e-3)
    take = np.maximum(1, np.round((spectrum/(spectrum.sum()+1e-9)) * per_const)).astype(int)
    chosen=[]
    for b,c in enumerate(centers):
        w = np.exp(-tau*((proj-c)**2)/(2*sigma*sigma))
        order = np.argsort(-w)
        picked=0
        for i in order:
            if i in chosen: continue
            chosen.append(int(i)); picked+=1
            if picked >= int(take[b]): break
    return chosen, proj

# ---- metrics on a whole decode set
def compute_metrics(cgp: Dict[str, Any], decoded: List[Dict[str,Any]], corpus_texts: List[str], corpus_vecs: np.ndarray) -> Dict[str, Any]:
    # group decoded by constellation
    by_const = {}
    for rec in decoded:
        by_const.setdefault(rec["constellation_id"], []).append(rec)
    bins = int(cgp.get("meta",{}).get("bins", 8))
    out_rows=[]
    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            cid = const.get("id","")
            u = np.array(const.get("anchor", []), dtype=np.float32)
            if u.ndim!=1: continue
            items = by_const.get(cid, [])
            idxs = [it.get("corpus_idx") for it in items if "corpus_idx" in it]
            if not idxs: 
                out_rows.append({"constellation_id": cid, "n":0, "KL":None,"JS":None,"W1":None,"coverage":0.0})
                continue
            rmin, rmax = const.get("radial_minmax", [None,None])
            if rmin is None or rmax is None:
                # compute from all corpus
                proj_all = (corpus_vecs @ (u/(np.linalg.norm(u)+1e-9)))
                rmin, rmax = float(proj_all.min()), float(proj_all.max())
            spectrum_t = np.asarray(const.get("spectrum",[1.0/bins]*bins), dtype=np.float64)
            proj_sel = (corpus_vecs[idxs] @ (u/(np.linalg.norm(u)+1e-9)))
            spectrum_e = _empirical_spectrum(proj_sel, rmin, rmax, bins)
            delta = (rmax-rmin)/max(1,bins-1)
            row = {
                "constellation_id": cid,
                "n": len(idxs),
                "KL": _kl(spectrum_t, spectrum_e),
                "JS": _js(spectrum_t, spectrum_e),
                "W1": _w1(spectrum_t, spectrum_e, delta=delta),
                "coverage": _coverage(per_const_target := 50, len(idxs)) # nominal
            }
            out_rows.append(row)
    return {"constellations": out_rows, "mean": {
        "KL": np.nanmean([r["KL"] for r in out_rows if r["KL"] is not None]),
        "JS": np.nanmean([r["JS"] for r in out_rows if r["JS"] is not None]),
        "W1": np.nanmean([r["W1"] for r in out_rows if r["W1"] is not None]),
        "coverage": float(np.mean([r["coverage"] for r in out_rows]))
    }}

# ---- generator (learning-based decoder) ----
def _mk_input_example(const, snippets: List[str]) -> str:
    # build a compact conditioning string from CHIT features + a few retrieved snippets
    spec = ",".join(f"{x:.3f}" for x in const.get("spectrum", [])[:12])
    summ = const.get("summary","")
    head = f"CHIT|id:{const.get('id','')}|spec:{spec}|summary:{summ}\nEXAMPLES:\n"
    # include top 3 short snippets
    pieces = []
    for s in snippets[:3]:
        s = re.sub(r"\s+", " ", s).strip()
        pieces.append(f"- {s[:400]}")
    return head + "\n".join(pieces)

def train_generator(cgp_path: str, decoded_jsonl: str, model_name="t5-small", out_dir="./gen_ckpt"):
    from datasets import Dataset  # type: ignore
    from transformers import T5Tokenizer, T5ForConditionalGeneration, DataCollatorForSeq2Seq, Trainer, TrainingArguments  # type: ignore

    cgp = json.loads(open(cgp_path,"r",encoding="utf-8").read())
    # group decoded snippets by constellation
    d = _load_jsonl(decoded_jsonl)
    groups = {}
    for rec in d:
        cid = rec["constellation_id"]; groups.setdefault(cid, []).append(rec["text"])
    # build training pairs
    inputs, targets = [], []
    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            cid = const.get("id","")
            if cid not in groups: continue
            inp = _mk_input_example(const, groups[cid])
            # choose a target: simple concatenation of two best snippets (could be pivots/high energy)
            tgt = " ".join(groups[cid][:2])[:512]
            inputs.append(inp); targets.append(tgt)
    if not inputs: raise RuntimeError("No training pairs; run geometry decode to build decoded_dataset.jsonl first.")

    tok = T5Tokenizer.from_pretrained(model_name)
    def tokenize(ex):
        x = tok(ex["input"], truncation=True, padding="max_length", max_length=512)
        y = tok(ex["target"], truncation=True, padding="max_length", max_length=256)
        x["labels"] = y["input_ids"]; return x
    ds = Dataset.from_dict({"input": inputs, "target": targets}).train_test_split(test_size=0.1, seed=17)
    ds_enc = ds.map(tokenize, batched=True, remove_columns=["input","target"])
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    args = TrainingArguments(
        output_dir=out_dir, per_device_train_batch_size=4, per_device_eval_batch_size=4,
        learning_rate=5e-4, num_train_epochs=3, weight_decay=0.01, logging_steps=50,
        save_strategy="epoch", evaluation_strategy="epoch", predict_with_generate=True
    )
    dc = DataCollatorForSeq2Seq(tokenizer=tok, model=model)
    trainer = Trainer(model=model, args=args, train_dataset=ds_enc["train"], eval_dataset=ds_enc["test"], data_collator=dc, tokenizer=tok)
    trainer.train()
    trainer.save_model(out_dir); tok.save_pretrained(out_dir)
    print("Generator trained and saved to", out_dir)

def generate_from_cgp(cgp_path: str, ckpt_dir: str, out_path="decoded_generated.jsonl"):
    from transformers import T5Tokenizer, T5ForConditionalGeneration  # type: ignore
    cgp = json.loads(open(cgp_path,"r",encoding="utf-8").read())
    tok = T5Tokenizer.from_pretrained(ckpt_dir)
    model = T5ForConditionalGeneration.from_pretrained(ckpt_dir)
    out=[]
    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            prompt = _mk_input_example(const, [const.get("summary","")])
            x = tok(prompt, return_tensors="pt", truncation=True, max_length=512)
            yids = model.generate(**x, max_new_tokens=160, num_beams=4)
            text = tok.decode(yids[0], skip_special_tokens=True)
            out.append({"constellation_id": const.get("id",""), "generated": text})
    with open(out_path, "w", encoding="utf-8") as f:
        for r in out: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("Wrote", out_path)

# ---- CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cgp", required=True)
    ap.add_argument("--corpus", help="structured_dataset.jsonl or similar (shared codebook)")
    ap.add_argument("--text-field", default="text")
    ap.add_argument("--model", help="embedding model; defaults to CGP meta.backend")
    ap.add_argument("--mode", choices=["auto","exact","geometry"], default="auto")
    ap.add_argument("--per-constellation", type=int, default=50)
    ap.add_argument("--tau", type=float, default=4.0)
    ap.add_argument("--out", default="decoded_dataset.jsonl")
    ap.add_argument("--report", default="reconstruction_report.md")
    # new
    ap.add_argument("--compute-metrics", action="store_true")
    ap.add_argument("--metrics-json", default="reconstruction_metrics.json")
    ap.add_argument("--train-generator", help="path to decoded_dataset.jsonl to train T5 on")
    ap.add_argument("--gen", help="path to T5 checkpoint dir to generate summaries")
    args = ap.parse_args()

    cgp = json.loads(open(args.cgp,"r",encoding="utf-8").read())
    backend = args.model or cgp.get("meta",{}).get("backend","sentence-transformers/all-MiniLM-L6-v2")

    # decide mode
    has_text = any(("points" in const and any(isinstance(p.get("text",""),str) and p.get("text","").strip()
                     for p in const["points"])) for s in cgp.get("super_nodes",[]) for const in s.get("constellations",[]))
    mode = "exact" if args.mode=="auto" and has_text else args.mode

    # generator workflows
    if args.train_generator:
        train_generator(args.cgp, args.train_generator)
        return
    if args.gen:
        generate_from_cgp(args.cgp, args.gen)
        return

    # decoding workflows
    decoded=[]
    if mode in ("auto","exact") and has_text:
        for s in cgp.get("super_nodes", []):
            for const in s.get("constellations", []):
                for p in const.get("points", []):
                    t = p.get("text","").strip()
                    if t:
                        decoded.append({
                            "super_id": s.get("id",""),
                            "constellation_id": const.get("id",""),
                            "text": t
                        })
    if (mode=="geometry") or (mode=="auto" and not decoded):
        if not args.corpus:
            raise RuntimeError("Geometry mode needs --corpus (shared codebook).")
        # load corpus
        texts = [json.loads(l)["text"] for l in open(args.corpus,"r",encoding="utf-8").read().splitlines() if l.strip()]
        vecs = _embed(texts, backend)
        used=set()
        for s in cgp.get("super_nodes", []):
            for const in s.get("constellations", []):
                u = np.array(const.get("anchor", []), dtype=np.float32)
                if u.ndim!=1: continue
                # rmin/rmax default from global corpus
                proj_all = vecs @ (u/(np.linalg.norm(u)+1e-9))
                rmin, rmax = const.get("radial_minmax",[float(proj_all.min()), float(proj_all.max())])
                spectrum = np.asarray(const.get("spectrum", [1.0/8]*8), dtype=np.float32)
                idxs, proj = _geom_decode_const(vecs, texts, u, rmin, rmax, spectrum, per_const=args.per_constellation, tau=args.tau)
                for i in idxs:
                    if i in used: continue
                    used.add(i)
                    decoded.append({
                        "super_id": s.get("id",""),
                        "constellation_id": const.get("id",""),
                        "text": texts[i],
                        "corpus_idx": int(i),
                        "proj_est": float(proj[i])
                    })
    if not decoded:
        raise RuntimeError("No decoded items produced.")
    with open(args.out, "w", encoding="utf-8") as f:
        for r in decoded: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("Saved", args.out)

    # metrics
    if args.compute-metrics and (mode=="geometry"):
        # need corpus embeddings
        texts = [json.loads(l)["text"] for l in open(args.corpus,"r",encoding="utf-8").read().splitlines() if l.strip()]
        vecs = _embed(texts, backend)
        metrics = compute_metrics(cgp, decoded, texts, vecs)
        with open(args.metrics_json, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        # simple markdown report
        with open(args.report, "w", encoding="utf-8") as f:
            f.write("# CHIT Reconstruction Report (v0.2)\n\n")
            m = metrics["mean"]
            f.write(f"- Mean KL: {m['KL']:.4f}\n- Mean JS: {m['JS']:.4f}\n- Mean W1: {m['W1']:.4f}\n- Mean coverage: {m['coverage']:.3f}\n\n")
            f.write("## Per‑constellation (top 20 worst JS)\n\n")
            rows = sorted(metrics["constellations"], key=lambda r: (r["JS"] if r["JS"] is not None else -1), reverse=True)[:20]
            f.write("| constellation_id | n | KL | JS | W1 | coverage |\n|---:|---:|---:|---:|---:|---:|\n")
            for r in rows:
                f.write(f"| {r['constellation_id']} | {r['n']} | {r['KL']:.4f} | {r['JS']:.4f} | {r['W1']:.4f} | {r['coverage']:.3f} |\n")
        print("Saved", args.report)

if __name__ == "__main__":
    main()
```

---

## 4) How to run (end‑to‑end)

**A. Build the shared codebook (once per corpus)**
Use your pivot‑banded structurer to produce `structured_dataset.jsonl`.&#x20;

**B. Protect & ship the CGP (optional security)**

```bash
python - <<'PY'
import json
from chit_security import sign_cgp, encrypt_anchors
cgp = json.load(open("./data/cgp.json"))
cgp = sign_cgp(cgp, passphrase="shared-secret")
cgp = encrypt_anchors(cgp, passphrase="shared-secret")
json.dump(cgp, open("./data/cgp_protected.json","w"), ensure_ascii=False, indent=2)
print("Protected CGP → ./data/cgp_protected.json")
PY
```

**C. Geometry‑only decode + metrics**

```bash
# (If you encrypted anchors, decrypt first with chit_security.decrypt_anchors)
python chit_decoder.py \
  --cgp ./data/cgp.json \
  --corpus ./structured_dataset.jsonl \
  --mode geometry \
  --per-constellation 50 \
  --compute-metrics \
  --out decoded_dataset.jsonl \
  --report reconstruction_report.md
```

**D. Train the generator (learning‑based decoder)**

```bash
# Use the geometry-recovered snippets as training data
python chit_decoder.py \
  --cgp ./data/cgp.json \
  --train-generator decoded_dataset.jsonl
```

**E. Generate summaries per constellation**

```bash
python chit_decoder.py \
  --cgp ./data/cgp.json \
  --gen ./gen_ckpt \
  --out decoded_generated.jsonl
```

**F. Multimodal (images)**

```bash
# Generate CGP with CLIP text backend, then:
python - <<'PY'
from chit_decoder_mm import load_cgp, decode_images
cgp = load_cgp("./data/cgp_clip.json")
imgs = decode_images(cgp, image_dir="./images", model_name="clip-ViT-B-32", per_constellation=12)
import json; json.dump(imgs, open("decoded_images.json","w"), indent=2)
print(f"Decoded {len(imgs)} images to decoded_images.json")
PY
```

---

## What you get from each enhancement

* **(1) Learning‑based decode**: produces **novel text** conditioned on CHIT geometry + a few retrieved exemplars—your first *generative* decoder (beyond retrieval).
* **(2) Multimodal**: the same geometry packet drives **image** (and later audio) reconstruction, provided a compatible multimodal embedding backend.
* **(3) Calibration metrics**: reliable **fidelity checks** per constellation (KL/JS/W1 + coverage) and an at‑a‑glance report to compare settings (K, bins, β, τ).
* **(4) Security**: **sign/verify** for integrity and **encrypt/decrypt** for privacy of anchors, so CGPs can traverse untrusted channels safely.

If you want, I can also wire a small FastAPI service to expose `/decode`, `/gen`, `/metrics`, and `/sign` endpoints around these scripts so your D3 UI can call them live.
