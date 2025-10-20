from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Any


def _now_iso() -> str:
    return _dt.datetime.utcnow().isoformat() + "Z"


def _norm(v: float | None, lo: float, hi: float) -> float | None:
    if v is None:
        return None
    if hi == lo:
        return 0.0
    x = (v - lo) / (hi - lo)
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return float(x)


def map_health_weekly_summary_to_cgp(evt: Dict[str, Any]) -> Dict[str, Any]:
    p = evt.get("payload", evt)
    ns = p.get("namespace", "pmoves")
    period = f"{p.get('period_start')}..{p.get('period_end')}"
    daily = p.get("daily", [])

    # Derive norm ranges
    loads = [d.get("load") for d in daily if isinstance(d.get("load"), (int, float))]
    load_lo, load_hi = (min(loads), max(loads)) if loads else (0.0, 100.0)

    consts: List[Dict[str, Any]] = []

    # Constellation: adherence (points per day; proj = workouts>0)
    adh_points = []
    for d in daily:
        day = d.get("date")
        workouts = int(d.get("workouts", 0))
        adh_points.append({
            "id": f"{day}:adh",
            "modality": "metric",
            "ref_id": day,
            "proj": 1.0 if workouts > 0 else 0.0,
            "summary": f"workouts={workouts}",
        })
    consts.append({
        "id": f"health.adh.{period}",
        "summary": f"adherence for {period}",
        "spectrum": [float(p.get("metrics",{}).get("adherence_pct", 0))/100.0],
        "points": adh_points,
        "meta": {"namespace": ns, "period": period}
    })

    # Constellation: load (normalized per day)
    load_points = []
    for d in daily:
        day = d.get("date")
        nload = _norm(d.get("load"), load_lo, load_hi)
        load_points.append({
            "id": f"{day}:load",
            "modality": "metric",
            "ref_id": day,
            "proj": 0.0 if nload is None else nload,
            "summary": f"load={d.get('load')}",
        })
    consts.append({
        "id": f"health.load.{period}",
        "summary": f"training load for {period}",
        "spectrum": [(_norm(p.get("metrics",{}).get("avg_load"), load_lo, load_hi) or 0.0)],
        "points": load_points,
        "meta": {"namespace": ns, "period": period}
    })

    # Optional: recovery as single knob
    rec = p.get("metrics", {}).get("recovery_score")
    consts.append({
        "id": f"health.recovery.{period}",
        "summary": "recovery score",
        "spectrum": [0.0 if rec is None else float(rec)/100.0],
        "points": [{"id": f"rec:{period}", "modality": "metric", "proj": 0.0 if rec is None else float(rec)/100.0}],
        "meta": {"namespace": ns, "period": period}
    })

    cgp: Dict[str, Any] = {
        "spec": "chit.cgp.v0.1",
        "summary": f"health weekly summary ({period})",
        "created_at": _now_iso(),
        "super_nodes": [
            {"id": f"health:{ns}", "label": ns, "summary": p.get("notes") or "", "constellations": consts}
        ],
        "meta": {"source": "health.weekly.summary.v1", "tags": p.get("tags", [])}
    }
    return cgp


def map_finance_monthly_summary_to_cgp(evt: Dict[str, Any]) -> Dict[str, Any]:
    p = evt.get("payload", evt)
    ns = p.get("namespace", "pmoves")
    month = p.get("month")
    cats = p.get("by_category", [])
    spend_values = [c.get("spend", 0.0) for c in cats]
    s_lo, s_hi = (min(spend_values), max(spend_values)) if spend_values else (0.0, 1.0)

    consts: List[Dict[str, Any]] = []
    for c in cats:
        cat = c.get("category")
        spend = c.get("spend", 0.0)
        budget = c.get("budget")
        var = c.get("variance")
        consts.append({
            "id": f"fin.{cat}.{month}",
            "summary": f"{cat} spend vs budget",
            "spectrum": [ _norm(spend, s_lo, s_hi) or 0.0, 0.0 if budget is None else _norm(budget, s_lo, s_hi) or 0.0 ],
            "points": [
                {"id": f"{month}:{cat}:spend", "modality": "metric", "proj": _norm(spend, s_lo, s_hi) or 0.0, "summary": f"${spend:.2f}"},
                {"id": f"{month}:{cat}:budget", "modality": "metric", "proj": 0.0 if budget is None else _norm(budget, s_lo, s_hi) or 0.0, "summary": f"${(budget or 0):.2f}"},
                {"id": f"{month}:{cat}:variance", "modality": "metric", "proj": 0.5 + (0 if var is None else max(min(var/ max(abs(s_hi),1.0), 0.5), -0.5)), "summary": f"var={(var or 0):+.2f}"}
            ],
            "meta": {"namespace": ns, "month": month, "category": cat}
        })

    cgp: Dict[str, Any] = {
        "spec": "chit.cgp.v0.1",
        "summary": f"finance monthly summary ({month})",
        "created_at": _now_iso(),
        "super_nodes": [
            {"id": f"finance:{ns}", "label": ns, "summary": p.get("notes") or "", "constellations": consts}
        ],
        "meta": {"source": "finance.monthly.summary.v1", "currency": p.get("currency"), "tags": p.get("tags", [])}
    }
    return cgp

