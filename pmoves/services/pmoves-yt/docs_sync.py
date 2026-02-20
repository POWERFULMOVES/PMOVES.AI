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
SUPA_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)

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
    if not SUPA_SERVICE_KEY:
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
    url = f"{SUPA}/pmoves_core.tool_docs?on_conflict=tool,version,doc_type"
    headers = {
        "apikey": SUPA_SERVICE_KEY,
        "Authorization": f"Bearer {SUPA_SERVICE_KEY}",
        "content-type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    r = requests.post(url, headers=headers, data=json.dumps(rows), timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {"text": r.text}
    if not r.ok:
        raise RuntimeError(f"Supabase upsert failed: {r.status_code} {body}")
    return {"status": "ok", "count": len(rows), "version": ver}

if __name__ == "__main__":
    data = collect_yt_dlp_docs()
    out = sync_to_supabase(data)
    print(json.dumps(out))

