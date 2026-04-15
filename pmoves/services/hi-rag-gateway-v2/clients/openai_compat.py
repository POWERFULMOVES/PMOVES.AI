"""MeiliSearch lexical search and persona extraction helpers."""

from typing import Any, Dict, List, Optional

import requests

from config import USE_MEILI, MEILI_URL, MEILI_API_KEY, COLL, logger


def meili_lexical(query, namespace, limit):
    if not USE_MEILI: return {}
    try:
        headers = {'Authorization': f'Bearer {MEILI_API_KEY}'} if MEILI_API_KEY else {}
        filters = [f"namespace = '{namespace}'"] if namespace and namespace != "*" else []
        payload = {'q': query, 'limit': max(10, limit * 3), 'filter': filters}
        r = requests.post(f"{MEILI_URL}/indexes/{COLL}/search", json=payload, headers=headers, timeout=10)
        if not r.ok:
            return {}
        hits = r.json().get('hits', [])
        out = {}
        for i, h in enumerate(hits):
            cid = h.get('chunk_id') or h.get('id')
            if not cid: continue
            score = h.get('_rankingScore') or (1.0 - i / max(1.0, len(hits)))
            out[cid] = float(score)
        return out
    except Exception:
        logger.exception("meili lexical error")
        return {}


def _extract_persona(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    keys = (
        "persona_id",
        "persona_slug",
        "persona_label",
        "persona_name",
        "persona_summary",
        "persona_namespace",
    )
    persona = {k: payload.get(k) for k in keys if payload.get(k)}
    return persona or None
