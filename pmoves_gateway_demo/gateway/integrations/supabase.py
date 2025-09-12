import os
import json
from typing import Any, Dict, List

import requests


def enabled() -> bool:
    return os.getenv("SUPABASE_ENABLED", "false").lower() == "true" and bool(os.getenv("SUPABASE_URL")) and bool(os.getenv("SUPABASE_KEY"))


def _headers() -> Dict[str, str]:
    key = os.environ["SUPABASE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _post(table: str, rows: List[Dict[str, Any]]):
    url = f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/{table}"
    resp = requests.post(url, headers=_headers(), data=json.dumps(rows))
    resp.raise_for_status()
    return resp.json()


def publish_cgp(shape_id: str, cgp: Dict[str, Any]):
    """Publish CGP parts into minimal Supabase tables if enabled.

    Expected tables:
      - anchors(id text primary key, shape_id text, summary text, radial_min real, radial_max real, spectrum jsonb)
      - constellations(id text primary key, shape_id text, anchor_id text, summary text)
      - shape_points(id text primary key, constellation_id text, modality text, ref_id text, proj real, conf real, meta jsonb)
    """
    if not enabled():
        return

    anchors_rows = []
    const_rows = []
    points_rows = []

    for s in cgp.get("super_nodes", []):
        for const in s.get("constellations", []):
            cid = const.get("id") or f"{shape_id}:{len(const_rows)}"
            anchors_rows.append({
                "id": f"anc:{cid}",
                "shape_id": shape_id,
                "summary": const.get("summary"),
                "radial_min": (const.get("radial_minmax") or [0,0])[0],
                "radial_max": (const.get("radial_minmax") or [0,0])[1],
                "spectrum": const.get("spectrum"),
            })
            const_rows.append({
                "id": cid,
                "shape_id": shape_id,
                "anchor_id": f"anc:{cid}",
                "summary": const.get("summary"),
            })
            for p in const.get("points", []):
                points_rows.append({
                    "id": p.get("id"),
                    "constellation_id": cid,
                    "modality": p.get("modality"),
                    "ref_id": p.get("source_ref") or p.get("id"),
                    "proj": p.get("proj"),
                    "conf": p.get("conf"),
                    "meta": {k:v for k,v in p.items() if k not in ("id","modality","source_ref","proj","conf")},
                })

    if anchors_rows:
        _post("anchors", anchors_rows)
    if const_rows:
        _post("constellations", const_rows)
    if points_rows:
        _post("shape_points", points_rows)

