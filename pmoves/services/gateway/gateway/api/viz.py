from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, HTMLResponse
from typing import List, Dict, Any, Optional
import json, os, math

from gateway.api.chit import Constellation, CGP, decode_constellations

router = APIRouter(tags=["Viz"], prefix="/viz")


def _svg_header(w: int, h: int) -> str:
    return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}'>"


def _polar(cx: float, cy: float, r: float, theta: float) -> tuple[float, float]:
    return cx + r * math.cos(theta), cy + r * math.sin(theta)


def _draw_constellation_svg(
    const: Constellation,
    title: Optional[str] = None,
    w: int = 512,
    h: int = 512,
    dim_x: int = 0,
    dim_y: int = 1,
    rotate_deg: float = 0.0,
) -> str:
    cx, cy = w / 2, h / 2
    R = min(w, h) * 0.4
    parts: List[str] = [_svg_header(w, h)]

    parts.append("<defs><radialGradient id='bg' cx='50%' cy='45%'><stop offset='0%' stop-color='#0b162b'/><stop offset='100%' stop-color='#0b1020'/></radialGradient></defs>")
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='url(#bg)'/>")
    for i in range(1, 5):
        r = R * i / 5
        parts.append(f"<circle cx='{cx}' cy='{cy}' r='{r:.2f}' fill='none' stroke='#1f2a44' stroke-width='1' />")
    for k in range(8):
        ang = (2 * math.pi) * k / 8
        x, y = _polar(cx, cy, R, ang)
        parts.append(f"<line x1='{cx}' y1='{cy}' x2='{x:.1f}' y2='{y:.1f}' stroke='#1f2a44' stroke-width='1'/>")

    spec = const.spectrum or []
    bins = max(1, len(spec))
    bar_w = (2 * math.pi) / bins
    for i, val in enumerate(spec):
        v = max(0.0, float(val))
        rlen = R * (0.15 + 0.8 * v)
        ang = -math.pi / 2 + i * bar_w
        x2, y2 = _polar(cx, cy, rlen, ang)
        hue = int(200 + 120 * (i / max(1, bins - 1))) % 360
        parts.append(
            f"<line x1='{cx}' y1='{cy}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='hsl({hue},80%,60%)' stroke-width='4' stroke-linecap='round'/>"
        )
    # Tick marks for spectrum centers
    for i in range(bins):
        ang = -math.pi / 2 + i * bar_w
        x1, y1 = _polar(cx, cy, R * 1.02, ang)
        x2, y2 = _polar(cx, cy, R * 1.08, ang)
        parts.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='#334166' stroke-width='1' />")
        lx, ly = _polar(cx, cy, R * 1.14, ang)
        parts.append(f"<text x='{lx:.1f}' y='{ly:.1f}' fill='#7aa2e3' font-size='10' text-anchor='middle' dominant-baseline='middle'>{i+1}</text>")

    anchor = const.anchor or []
    ax = float(anchor[dim_x]) if len(anchor) > dim_x else 0.0
    ay = float(anchor[dim_y]) if len(anchor) > dim_y else 0.0
    nrm = math.hypot(ax, ay)
    if nrm > 1e-6:
        ux, uy = ax / nrm, ay / nrm
        if rotate_deg:
            th = math.radians(rotate_deg)
            rx = ux * math.cos(th) - uy * math.sin(th)
            ry = ux * math.sin(th) + uy * math.cos(th)
            ux, uy = rx, ry
        tipx, tipy = cx + ux * (R * 0.95), cy + uy * (R * 0.95)
        parts.append(
            f"<line x1='{cx}' y1='{cy}' x2='{tipx:.1f}' y2='{tipy:.1f}' stroke='#22d3ee' stroke-width='5' stroke-linecap='round'/>"
        )
        ah_ang = math.atan2(uy, ux)
        left = _polar(tipx, tipy, 12, ah_ang + 2.6)
        right = _polar(tipx, tipy, 12, ah_ang - 2.6)
        parts.append(
            f"<polygon points='{tipx:.1f},{tipy:.1f} {left[0]:.1f},{left[1]:.1f} {right[0]:.1f},{right[1]:.1f}' fill='#22d3ee'/>"
        )

    title_text = title or const.id
    if title_text:
        parts.append(
            f"<text x='{cx}' y='{h - 18}' text-anchor='middle' fill='#b6c8e2' font-family='ui-sans-serif,system-ui' font-size='14'>{title_text}</text>"
        )
    # Axis labels for selected dims
    parts.append(f"<text x='{cx - R - 20}' y='{cy - R - 8}' fill='#64748b' font-size='11'>dim_x={dim_x}, dim_y={dim_y}, rot={rotate_deg:.0f}°</text>")

    parts.append("</svg>")
    return "".join(parts)


@router.post("/constellation.svg")
def constellation_svg(const: Constellation, dim_x: int = Query(0, ge=0), dim_y: int = Query(1, ge=0), rotate: float = 0.0):
    svg = _draw_constellation_svg(const, dim_x=dim_x, dim_y=dim_y, rotate_deg=rotate)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/shape/{shape_id}.svg")
def shape_svg(shape_id: str, super_idx: int = Query(0, ge=0), const_idx: int = Query(0, ge=0), dim_x: int = Query(0, ge=0), dim_y: int = Query(1, ge=0), rotate: float = 0.0):
    path = os.path.join("data", f"{shape_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="shape not found")
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    try:
        cgp = CGP.model_validate(obj)
        const = cgp.super_nodes[super_idx].constellations[const_idx]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid indices: {e}")
    svg = _draw_constellation_svg(const, title=f"{shape_id} · {const.id}", dim_x=dim_x, dim_y=dim_y, rotate_deg=rotate)
    return Response(content=svg, media_type="image/svg+xml")


def _mix_arrays(a: List[float], b: List[float], alpha: float) -> List[float]:
    n = max(len(a), len(b))
    out = []
    for i in range(n):
        va = float(a[i]) if i < len(a) else 0.0
        vb = float(b[i]) if i < len(b) else 0.0
        out.append((1.0 - alpha) * va + alpha * vb)
    return out


def _norm_vec(v: List[float]) -> List[float]:
    n = math.sqrt(sum(x*x for x in v)) or 1.0
    return [x / n for x in v]


def _decode_with_server(cgp: CGP, per_constellation: int) -> Dict[str, Any]:
    # Reuse the geometry-only decoder logic on a list of constellations
    consts: List[Constellation] = []
    for sn in cgp.super_nodes:
        consts.extend(sn.constellations)
    return decode_constellations(consts, per_constellation=per_constellation)


@router.post("/preview/decode")
def preview_decode(const: Constellation, per_constellation: int = 20, codebook_path: Optional[str] = Query(None)):
    return decode_constellations([const], per_constellation=per_constellation, codebook_path=codebook_path)


@router.post("/mix/decode")
def mix_and_decode(payload: Dict[str, Any], per_constellation: int = 20, codebook_path: Optional[str] = Query(None)):
    # payload: { const_a, const_b, alpha_anchor, alpha_spectrum }
    try:
        ca = Constellation.model_validate(payload.get("const_a"))
        cb = Constellation.model_validate(payload.get("const_b"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid input: {e}")
    aa = float(payload.get("alpha_anchor", 0.5))
    as_ = float(payload.get("alpha_spectrum", 0.5))

    # Mix fields
    anchor = _norm_vec(_mix_arrays(ca.anchor or [], cb.anchor or [], aa))
    rmin_a, rmax_a = (ca.radial_minmax[0], ca.radial_minmax[1])
    rmin_b, rmax_b = (cb.radial_minmax[0], cb.radial_minmax[1])
    rmin = (1-aa)*float(rmin_a) + aa*float(rmin_b)
    rmax = (1-aa)*float(rmax_a) + aa*float(rmax_b)
    spec = _mix_arrays(ca.spectrum or [], cb.spectrum or [], as_)
    ssum = sum(spec) or 1.0
    spec = [x/ssum for x in spec]

    mixed = Constellation(
        id=f"mix:{ca.id}|{cb.id}",
        anchor=anchor,
        radial_minmax=[rmin, rmax],
        spectrum=spec,
        points=[],
    )
    return decode_constellations([mixed], per_constellation=per_constellation, codebook_path=codebook_path)


@router.get("/recent", response_model=List[str])
def recent_shapes(limit: int = 10):
    if not os.path.isdir("data"):
        return []
    files = [f for f in os.listdir("data") if f.endswith(".json")]
    files.sort(key=lambda fn: os.path.getmtime(os.path.join("data", fn)), reverse=True)
    return [os.path.splitext(f)[0] for f in files[:limit]]


@router.get("/shape/{shape_id}/constellations")
def shape_constellations(shape_id: str):
    path = os.path.join("data", f"{shape_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="shape not found")
    obj = json.loads(open(path, "r", encoding="utf-8").read())
    cgp = CGP.model_validate(obj)
    out = []
    for si, s in enumerate(cgp.super_nodes):
        for ci, const in enumerate(s.constellations):
            out.append({
                "super_idx": si,
                "const_idx": ci,
                "id": const.id,
                "has_points": bool(const.points),
            })
    return {"shape_id": shape_id, "constellations": out}


@router.post("/preview/calibration")
def preview_calibration(const: Constellation, codebook_path: Optional[str] = Query(None)):
    cgp = CGP(spec="chit.cgp.v0.1", meta={}, super_nodes=[{"id": "s0", "constellations": [json.loads(const.model_dump_json())]}])
    from gateway.api.chit import geometry_calibration_report
    return geometry_calibration_report(cgp=cgp, codebook_path=codebook_path)


@router.post("/mix/calibration")
def mix_calibration(payload: Dict[str, Any], codebook_path: Optional[str] = Query(None)):
    try:
        ca = Constellation.model_validate(payload.get("const_a"))
        cb = Constellation.model_validate(payload.get("const_b"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid input: {e}")
    aa = float(payload.get("alpha_anchor", 0.5))
    as_ = float(payload.get("alpha_spectrum", 0.5))
    anchor = _norm_vec(_mix_arrays(ca.anchor or [], cb.anchor or [], aa))
    rmin_a, rmax_a = (ca.radial_minmax[0], ca.radial_minmax[1])
    rmin_b, rmax_b = (cb.radial_minmax[0], cb.radial_minmax[1])
    rmin = (1-aa)*float(rmin_a) + aa*float(rmin_b)
    rmax = (1-aa)*float(rmax_a) + aa*float(rmax_b)
    spec = _mix_arrays(ca.spectrum or [], cb.spectrum or [], as_)
    ssum = sum(spec) or 1.0
    spec = [x/ssum for x in spec]
    mixed = CGP(spec="chit.cgp.v0.1", meta={}, super_nodes=[{"id": "s0", "constellations": [{
        "id": f"mix:{ca.id}|{cb.id}",
        "anchor": anchor,
        "radial_minmax": [rmin, rmax],
        "spectrum": spec,
        "points": []
    }]}])
    from gateway.api.chit import geometry_calibration_report
    return geometry_calibration_report(cgp=mixed, codebook_path=codebook_path)
