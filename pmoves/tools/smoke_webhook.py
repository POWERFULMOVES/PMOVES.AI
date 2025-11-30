#!/usr/bin/env python3
"""
Minimal render-webhook smoke test.

Defaults:
  BASE_URL=http://localhost:8085
  PATH=/comfy/webhook
  TOKEN env: PMOVES_WEBHOOK_TOKEN (optional)

Usage:
  python pmoves/tools/smoke_webhook.py                 # dry-run (no network)
  python pmoves/tools/smoke_webhook.py --live          # real POST to BASE_URL+PATH
  BASE_URL=http://localhost:8085 TOKEN=change_me python pmoves/tools/smoke_webhook.py --live

Exit codes:
  0 success, 1 failure.
"""
import os, sys, json, time, base64
import argparse
from urllib import request, error

def build_payload():
    now = int(time.time())
    # Small synthetic body that matches pmoves_completion_webhook.py expectations
    payload = {
        "bucket": os.environ.get("WEBHOOK_BUCKET", "outputs"),
        "key": os.environ.get("WEBHOOK_KEY", f"smoke/hello-{now}.txt"),
        "title": os.environ.get("WEBHOOK_TITLE", "Smoke Test Artifact"),
        "namespace": os.environ.get("WEBHOOK_NAMESPACE", "pmoves"),
        "author": os.environ.get("WEBHOOK_AUTHOR", "CI"),
        "tags": ["smoke", "render"],
        "s3_uri": os.environ.get("WEBHOOK_S3_URI", "s3://outputs/smoke/hello.txt"),
        "presigned_get": os.environ.get("WEBHOOK_PRESIGNED", "https://example.com/hello.txt"),
        "auto_approve": False,
        "graph_hash": None,
    }
    return payload

def do_post(url: str, token: str, data: dict) -> tuple[int, str]:
    body = json.dumps(data).encode("utf-8")
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=15) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="ignore")
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return 0, str(e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://localhost:8085"))
    ap.add_argument("--path", default=os.environ.get("WEBHOOK_PATH", "/comfy/webhook"))
    ap.add_argument("--token", default=os.environ.get("TOKEN", os.environ.get("PMOVES_WEBHOOK_TOKEN", "")))
    ap.add_argument("--live", action="store_true", help="perform real POST; otherwise dry-run")
    args = ap.parse_args()

    url = args.base_url.rstrip("/") + args.path
    payload = build_payload()

    if not args.live:
        print("[dry-run] POST", url)
        print(json.dumps(payload, indent=2))
        return 0

    code, text = do_post(url, args.token, payload)
    ok = (code == 200)
    print(f"status: {code}; ok={ok}")
    if text:
        print(text[:500])
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())

