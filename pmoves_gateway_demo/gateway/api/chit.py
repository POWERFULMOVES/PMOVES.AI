import os, json, base64, hashlib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

router = APIRouter(tags=["CHIT"])

CHIT_REQUIRE_SIGNATURE = os.getenv("CHIT_REQUIRE_SIGNATURE","false").lower()=="true"
CHIT_DECRYPT_ANCHORS = os.getenv("CHIT_DECRYPT_ANCHORS","false").lower()=="true"
CHIT_PASSPHRASE = os.getenv("CHIT_PASSPHRASE","change-me")
CHIT_CODEBOOK_PATH = os.getenv("CHIT_CODEBOOK_PATH","tests/data/codebook.jsonl")
CHIT_LEARNED_TEXT = os.getenv("CHIT_LEARNED_TEXT","false").lower()=="true"
CHIT_T5_MODEL = os.getenv("CHIT_T5_MODEL")  # optional HF model path/name

# Optional integrations
try:
    from gateway.integrations import supabase as supa
except Exception:  # pragma: no cover
    supa = None

SHAPES: Dict[str, Dict[str, Any]] = {}
POINTS: Dict[str, Dict[str, Any]] = {}

def canon(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",",":")).encode()

def verify_hmac(cgp: Dict[str, Any]) -> bool:
    sig = cgp.get("sig")
    if not sig: return not CHIT_REQUIRE_SIGNATURE
    mac_b64 = sig.get("hmac","")
    doc = dict(cgp); doc.pop("sig", None)
    mac2 = hashlib.new("sha256", CHIT_PASSPHRASE.encode())
    mac2.update(canon(doc))
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return False
    return mac1 == mac2.digest()

def decrypt_anchor(const: Dict[str, Any]) -> None:
    if "anchor" in const: return
    enc = const.get("anchor_enc")
    if not enc:
        return
    if not CHIT_DECRYPT_ANCHORS:
        raise HTTPException(status_code=400, detail="Encrypted anchor but CHIT_DECRYPT_ANCHORS=false")
    iv = base64.b64decode(enc["iv"]); salt = base64.b64decode(enc["salt"]); ct = base64.b64decode(enc["ct"])
    key = hashlib.scrypt(CHIT_PASSPHRASE.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    aead = AESGCM(key); aad = canon({"id": const.get("id","")})
    pt = aead.decrypt(iv, ct, aad)
    try: const["anchor"] = json.loads(pt.decode())
    except: pass
    const.pop("anchor_enc", None)

class Point(BaseModel):
    id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    proj: Optional[float] = None
    conf: Optional[float] = None
    text: Optional[str] = None
    source_ref: Optional[str] = None

class Constellation(BaseModel):
    id: str
    anchor: Optional[List[float]] = None
    anchor_enc: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    radial_minmax: List[float]
    spectrum: List[float]
    points: List[Point] = Field(default_factory=list)

class SuperNode(BaseModel):
    id: str
    constellations: List[Constellation]

class CGP(BaseModel):
    spec: str
    meta: Dict[str, Any]
    super_nodes: List[SuperNode]
    sig: Optional[Dict[str, Any]] = None

@router.post("/geometry/event")
def geometry_event(cgp: CGP):
    obj = cgp.model_dump()
    if CHIT_REQUIRE_SIGNATURE and not verify_hmac(obj):
        raise HTTPException(status_code=400, detail="Invalid or missing HMAC signature")
    for s in obj.get("super_nodes", []):
        for const in s.get("constellations", []):
            decrypt_anchor(const)
    doc = dict(obj); doc.pop("sig", None)
    shape_hash = hashlib.sha256(canon(doc)).hexdigest()[:16]
    SHAPES[shape_hash] = obj
    for s in obj.get("super_nodes", []):
        for const in s.get("constellations", []):
            for p in const.get("points", []):
                pid = p.get("id") or f"p:{shape_hash}:{len(POINTS)}"
                p["id"] = pid; POINTS[pid] = p
    os.makedirs("data", exist_ok=True)
    json.dump(obj, open(f"data/{shape_hash}.json","w"), indent=2)

    # Publish to Supabase (optional)
    try:
        if supa and supa.enabled():
            supa.publish_cgp(shape_hash, obj)
    except Exception:
        pass

    # Emit realtime event (SSE mock)
    try:
        from gateway.api.events import emit_event  # late import to avoid cycles
        emit_event({"type": "geometry.event", "shape_id": shape_hash})
    except Exception:
        pass

    return {"ok": True, "shape_id": shape_hash, "event": "geometry.cgp.v1"}

@router.get("/shape/point/{pid}/jump")
def shape_point_jump(pid: str):
    p = POINTS.get(pid)
    if not p:
        if pid.startswith("v:") and "#t=" in pid:
            vid, t = pid[2:].split("#t=",1); t0 = t.split("-")[0]
            return {"id": pid, "url": f"https://youtu.be/{vid}?t={t0}"}
        raise HTTPException(status_code=404, detail="point not found")
    src = p.get("source_ref") or p.get("id","")
    if isinstance(src,str) and src.startswith("v:") and "#t=" in src:
        vid, t = src[2:].split("#t=",1); t0 = t.split("-")[0]
        return {"id": pid, "url": f"https://youtu.be/{vid}?t={t0}"}
    return {"id": pid, "url": "#"}

def _load_codebook(path: str):
    items=[]; 
    if not os.path.exists(path): path="tests/data/codebook.jsonl"
    if not os.path.exists(path): return items
    with open(path,"r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip(); 
            if ln: items.append(json.loads(ln))
    return items

@router.post("/geometry/decode/text")
def geometry_decode_text(cgp: CGP, per_constellation: int=10, codebook_path: Optional[str] = None):
    items = _load_codebook(codebook_path or CHIT_CODEBOOK_PATH)
    if not items: return {"items": []}
    out=[]
    for s in cgp.super_nodes:
        for const in s.constellations:
            anchor = const.anchor
            if not anchor and const.anchor_enc:
                d = const.model_dump(); decrypt_anchor(d); anchor = d.get("anchor")
            if not anchor: continue
            nrm = sum(x*x for x in anchor) ** 0.5 or 1.0
            u = [x/nrm for x in anchor]
            projs=[]
            for idx,it in enumerate(items):
                vec = it.get("vec"); 
                if vec is None: continue
                proj = sum(a*b for a,b in zip(u, vec))
                projs.append((idx, proj))
            rmin, rmax = const.radial_minmax; bins = len(const.spectrum)
            centers = [rmin+(rmax-rmin)*i/max(1,bins-1) for i in range(bins)]
            sel=[]
            for idx,proj in projs:
                # simple weight by nearest bin height
                nearest = min(range(bins), key=lambda i: abs(proj-centers[i]))
                w = const.spectrum[nearest]
                sel.append((idx,w,proj))
            sel.sort(key=lambda x: x[1], reverse=True)
            for idx,w,proj in sel[:per_constellation]:
                out.append({"constellation_id": const.id, "text": items[idx].get("text"), "proj_est": proj, "score": w})

    # Optional learned text decoder
    if CHIT_LEARNED_TEXT:
        learned = _learned_enhance(out)
        return {"items": out, "learned": learned}

    return {"items": out}

@router.post("/geometry/calibration/report")
def geometry_calibration_report(cgp: CGP, codebook_path: Optional[str] = None):
    items = _load_codebook(codebook_path or CHIT_CODEBOOK_PATH)
    if not items: return {"KL": None, "JS": None, "coverage": 0.0}
    const = cgp.super_nodes[0].constellations[0]
    anchor = const.anchor or []
    if not anchor and const.anchor_enc:
        d = const.model_dump(); decrypt_anchor(d); anchor = d.get("anchor") or []
    if not anchor: raise HTTPException(status_code=400, detail="No anchor")
    nrm = sum(x*x for x in anchor) ** 0.5 or 1.0
    u = [x/nrm for x in anchor]
    vals=[]; 
    for it in items:
        vec = it.get("vec"); 
        if vec: vals.append(sum(a*b for a,b in zip(u, vec)))
    rmin, rmax = const.radial_minmax; bins = len(const.spectrum)
    width = (rmax-rmin)/bins; hist=[0]*bins
    for v in vals:
        b = int((v-rmin)/width); b = max(0, min(b, bins-1)); hist[b]+=1
    total = float(sum(hist)) or 1.0
    emp = [h/total for h in hist]; tgt = list(const.spectrum)
    import math
    def kl(p,q): 
        eps=1e-9; return sum(pi*(math.log((pi+eps)/(qi+eps))) for pi,qi in zip(p,q))
    def js(p,q):
        m=[(pi+qi)/2 for pi,qi in zip(p,q)]; return 0.5*kl(p,m)+0.5*kl(q,m)
    cov = sum(1 for e in emp if e>0)/bins
    os.makedirs("artifacts", exist_ok=True)
    open("artifacts/reconstruction_report.md","w").write(f"# CHIT Calibration Report\n\n- KL: {kl(tgt,emp):.4f}\n- JS: {js(tgt,emp):.4f}\n- Coverage: {cov:.2f}\n")
    return {"KL": kl(tgt,emp), "JS": js(tgt,emp), "coverage": cov, "report": "artifacts/reconstruction_report.md"}


# --- Learned text decoding (optional) ------------------------------------------------------------

def _learned_enhance(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Optionally apply a small learned model to produce summaries.

    Tries HuggingFace Transformers pipeline if available and `CHIT_T5_MODEL` is set.
    Falls back to a simple frequency-driven summarizer when transformers are not installed.
    """
    try:
        if CHIT_T5_MODEL:
            from transformers import pipeline  # type: ignore
            texts = [it.get("text","") for it in items]
            head = "\n".join(texts[:10]) or ""
            summarizer = pipeline("summarization", model=CHIT_T5_MODEL)
            summ = summarizer(head, max_length=64, min_length=10, do_sample=False)[0]["summary_text"]
            return {"mode": "transformers", "summary": summ}
    except Exception:
        pass

    # Fallback: naive keyword summary
    from collections import Counter
    import re
    words = []
    for it in items:
        words += re.findall(r"[a-zA-Z][a-zA-Z0-9]+", (it.get("text") or "").lower())
    common = ", ".join(w for w,_ in Counter(words).most_common(8))
    return {"mode": "freq", "keywords": common}
