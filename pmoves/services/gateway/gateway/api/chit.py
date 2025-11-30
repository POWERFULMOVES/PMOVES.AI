import os, json, base64, hashlib, logging
from typing import Any, Dict, List, Optional, Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

router = APIRouter(tags=["CHIT"])
logger = logging.getLogger(__name__)

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

try:  # pragma: no cover - optional during docs builds
    from pmoves.services.common.shape_store import ShapeStore
except Exception:  # pragma: no cover
    ShapeStore = None  # type: ignore

shape_store: Optional["ShapeStore"] = None
_shape_to_constellations: Dict[str, List[str]] = {}

def canon(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",",":")).encode()


def set_shape_store(store: Optional["ShapeStore"]) -> None:
    """Configure the module-level ShapeStore instance."""
    global shape_store
    shape_store = store


def compute_shape_id(cgp: Dict[str, Any]) -> str:
    doc = dict(cgp)
    doc.pop("sig", None)
    return hashlib.sha256(canon(doc)).hexdigest()[:16]

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


class GeometryEventEnvelope(BaseModel):
    type: str = Field(alias="type")
    data: CGP

    model_config = ConfigDict(populate_by_name=True)


class GeometryDecodeTextRequest(BaseModel):
    shape_id: Optional[str] = None
    constellation_ids: List[str] = Field(default_factory=list)
    per_constellation: int = 10
    codebook_path: Optional[str] = None


def ingest_cgp(cgp: Dict[str, Any]) -> str:
    if shape_store is None:
        raise HTTPException(status_code=503, detail="ShapeStore unavailable")
    if CHIT_REQUIRE_SIGNATURE and not verify_hmac(cgp):
        raise HTTPException(status_code=400, detail="Invalid or missing HMAC signature")

    for s in cgp.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            decrypt_anchor(const)

    shape_id = compute_shape_id(cgp)

    point_idx = 0
    const_ids: List[str] = []
    for s in cgp.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            cid = const.get("id")
            if cid:
                const_ids.append(str(cid))
            for p in const.get("points", []) or []:
                if not p.get("id"):
                    p["id"] = f"p:{shape_id}:{point_idx}"
                    point_idx += 1
                if "ref_id" not in p and p.get("source_ref"):
                    p["ref_id"] = p.get("source_ref")

    if const_ids:
        _shape_to_constellations[shape_id] = list(dict.fromkeys(const_ids))

    shape_store.on_geometry_event({"type": "geometry.cgp.v1", "data": cgp})

    os.makedirs("data", exist_ok=True)
    json.dump(cgp, open(f"data/{shape_id}.json", "w"), indent=2)

    try:
        if supa and supa.enabled():
            supa.publish_cgp(shape_id, cgp)
    except Exception as exc:
        logger.exception("Failed to sync CGP to Supabase")
        raise HTTPException(status_code=502, detail="Failed to sync CGP to Supabase") from exc


    try:
        from pmoves.services.gateway.gateway.api.events import emit_event  # late import to avoid cycles
        emit_event({"type": "geometry.event", "shape_id": shape_id})
    except Exception:
        pass

    return shape_id

@router.post("/geometry/event")
def geometry_event(event: GeometryEventEnvelope):
    if event.type != "geometry.cgp.v1":
        raise HTTPException(status_code=400, detail="Unsupported geometry event type")
    ingest_cgp(event.data.model_dump())
    return {"ok": True}

    return {"ok": True, "shape_id": shape_hash, "event": "geometry.cgp.v1"}


@router.get("/shape/point/{pid}/jump")
def shape_point_jump(pid: str):
    if shape_store is None:
        raise HTTPException(status_code=503, detail="ShapeStore unavailable")
    loc = shape_store.jump_locator(pid)
    if not loc:
        if pid.startswith("v:") and "#t=" in pid:
            vid, t = pid[2:].split("#t=", 1)
            t0 = t.split("-")[0]
            return {
                "ok": True,
                "locator": {"modality": "video", "ref_id": vid, "t": float(t0)},
            }
        raise HTTPException(status_code=404, detail="point not found")
    return {"ok": True, "locator": loc}

def _load_codebook(path: str):
    items=[]; 
    if not os.path.exists(path): path="tests/data/codebook.jsonl"
    if not os.path.exists(path): return items
    with open(path,"r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip(); 
            if ln: items.append(json.loads(ln))
    return items

def decode_constellations(
    constellations: Sequence[Constellation],
    per_constellation: int = 10,
    codebook_path: Optional[str] = None,
) -> Dict[str, Any]:
    items = _load_codebook(codebook_path or CHIT_CODEBOOK_PATH)
    if not items:
        return {"items": []}
    out: List[Dict[str, Any]] = []
    for const in constellations:
        anchor = const.anchor
        if not anchor and const.anchor_enc:
            d = const.model_dump()
            decrypt_anchor(d)
            anchor = d.get("anchor")
        if not anchor:
            continue
        nrm = sum(x * x for x in anchor) ** 0.5 or 1.0
        u = [x / nrm for x in anchor]
        projs: List[tuple[int, float]] = []
        for idx, it in enumerate(items):
            vec = it.get("vec")
            if vec is None:
                continue
            proj = sum(a * b for a, b in zip(u, vec))
            projs.append((idx, proj))
        rmin, rmax = const.radial_minmax
        bins = len(const.spectrum)
        centers = [rmin + (rmax - rmin) * i / max(1, bins - 1) for i in range(bins)]
        sel: List[tuple[int, float, float]] = []
        for idx, proj in projs:
            nearest = min(range(bins), key=lambda i: abs(proj - centers[i])) if bins else 0
            w = const.spectrum[nearest] if bins else 0.0
            sel.append((idx, w, proj))
        sel.sort(key=lambda x: x[1], reverse=True)
        for idx, w, proj in sel[:per_constellation]:
            out.append(
                {
                    "constellation_id": const.id,
                    "text": items[idx].get("text"),
                    "proj_est": proj,
                    "score": w,
                }
            )

    if CHIT_LEARNED_TEXT:
        learned = _learned_enhance(out)
        return {"items": out, "learned": learned}

    return {"items": out}


@router.post("/geometry/decode/text")
def geometry_decode_text(body: GeometryDecodeTextRequest):
    if shape_store is None:
        raise HTTPException(status_code=503, detail="ShapeStore unavailable")

    requested_ids: List[str] = []
    if body.shape_id:
        requested_ids.extend(_shape_to_constellations.get(body.shape_id, []))
    requested_ids.extend(body.constellation_ids)
    ordered_ids = list(dict.fromkeys(requested_ids))
    if not ordered_ids:
        raise HTTPException(status_code=400, detail="constellation_ids or shape_id required")

    found: List[Constellation] = []
    missing: List[str] = []
    for cid in ordered_ids:
        raw = shape_store.get_constellation(cid)
        if not raw:
            missing.append(cid)
            continue
        try:
            found.append(Constellation.model_validate(raw))
        except Exception:
            missing.append(cid)

    if not found:
        raise HTTPException(status_code=404, detail="constellations not found")

    resp = decode_constellations(
        found,
        per_constellation=body.per_constellation,
        codebook_path=body.codebook_path,
    )

    if missing:
        resp["missing"] = missing

    return resp

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
