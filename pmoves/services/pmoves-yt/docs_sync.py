import os
import subprocess
import json
from datetime import datetime, timezone
from typing import Dict, Any

SUPA = (
    os.environ.get("SUPABASE_REST_URL")
    or os.environ.get("SUPA_REST_URL")
    or "http://postgrest:3000"
).rstrip("/")


def _candidate_keys() -> list[str]:
    # Only service-role keys are valid for write operations.
    # SUPABASE_ANON_KEY is intentionally excluded — anon tokens lack INSERT
    # privileges on pmoves_core tables and would silently produce 403s.
    keys = [
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        os.environ.get("SUPABASE_SERVICE_KEY"),
        os.environ.get("SUPABASE_KEY"),
    ]
    out: list[str] = []
    for key in keys:
        if not key:
            continue
        if key not in out:
            out.append(key)
    return out

def _capture_cmd(args: list[str]) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return proc.stderr.strip() or proc.stdout.strip()
        return proc.stdout
    except Exception as exc:  # best-effort
        return f"<error: {exc}>"

def collect_yt_dlp_docs() -> Dict[str, Any]:
    import yt_dlp  # type: ignore
    version = getattr(yt_dlp, "version", None)
    if isinstance(version, str):
        ver = version
    else:
        ver = getattr(yt_dlp, "__version__", "unknown")
    docs: Dict[str, Any] = {
        "version": ver,
        "help_cli": _capture_cmd(["yt-dlp", "--help"]),
        "extractors": _capture_cmd(["yt-dlp", "--list-extractors"]),
        "user_agent": _capture_cmd(["yt-dlp", "--dump-user-agent"]),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return docs

def sync_to_supabase(docs: Dict[str, Any]) -> Dict[str, Any]:
    keys = _candidate_keys()
    if not keys:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY (or equivalent) is required")
    tool = "yt-dlp"
    ver = docs.get("version") or "unknown"
    rows = []
    for k in ("help_cli", "extractors", "user_agent"):
        content = docs.get(k)
        # Store as JSON with `text` field for consistency
        rows.append({
            "tool": tool,
            "version": str(ver),
            "doc_type": k,
            "content": {"text": content},
        })
    import requests
    targets = [
        # Preferred: proper PostgREST profile headers for pmoves_core schema.
        {"url": f"{SUPA}/tool_docs?on_conflict=tool,version,doc_type", "schema": "pmoves_core"},
        # Legacy fallback: existing callers that encode schema in table path.
        {"url": f"{SUPA}/pmoves_core.tool_docs?on_conflict=tool,version,doc_type", "schema": None},
        # Last fallback if schema support is not configured.
        {"url": f"{SUPA}/tool_docs?on_conflict=tool,version,doc_type", "schema": None},
    ]

    last_error: str | None = None
    for target in targets:
        missing_relation = False
        transport_error = False
        for key in keys:
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "content-type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            }
            if target["schema"]:
                headers["Accept-Profile"] = target["schema"]
                headers["Content-Profile"] = target["schema"]
            try:
                r = requests.post(target["url"], headers=headers, data=json.dumps(rows), timeout=20)
            except requests.RequestException as exc:
                last_error = f"transport error: {exc}"
                transport_error = True
                break
            try:
                body = r.json()
            except ValueError:
                body = {"text": r.text}
            if r.ok:
                return {"status": "ok", "count": len(rows), "version": ver}
            last_error = f"{r.status_code} {body}"
            # JWT/key mismatch can happen when layered env files contain stale aliases.
            # Continue trying available keys before failing hard.
            if r.status_code in (401, 403):
                continue
            # Missing schema/table: move to next target strategy.
            if r.status_code in (404, 406):
                missing_relation = True
            break
        if missing_relation or transport_error:
            continue

    raise RuntimeError(f"Supabase upsert failed: {last_error}")

if __name__ == "__main__":
    data = collect_yt_dlp_docs()
    out = sync_to_supabase(data)
    print(json.dumps(out))
