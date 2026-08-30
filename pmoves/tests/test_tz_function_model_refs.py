"""Every TZ function variant must reference a defined model.

Worker functions (pmoves_worker_*) may ONLY reference registry_ lane aliases —
this is the no-hardcoded-local-models gate (spec rev 3/4, 2026-07-02).
"""
import tomllib
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]
TZ_TOML = PMOVES / "tensorzero" / "config" / "tensorzero.toml"


def _tz():
    with open(TZ_TOML, "rb") as fh:
        return tomllib.load(fh)


def test_all_variant_model_refs_resolve():
    tz = _tz()
    defined = set(tz.get("models", {})) | set(tz.get("embedding_models", {}))
    dangling = [
        (fn, var, v["model"])
        for fn, f in tz.get("functions", {}).items()
        for var, v in (f.get("variants") or {}).items()
        if "model" in v and v["model"] not in defined
    ]
    assert not dangling, f"variants reference undefined models: {dangling}"


def test_worker_functions_use_registry_lanes_only():
    tz = _tz()
    offenders = [
        (fn, var, v["model"])
        for fn, f in tz.get("functions", {}).items()
        if fn.startswith("pmoves_worker_")
        for var, v in (f.get("variants") or {}).items()
        if not str(v.get("model", "")).startswith("registry_")
    ]
    assert not offenders, (
        "worker variants must reference registry_ lane aliases (Supabase-managed), "
        f"got: {offenders}"
    )
