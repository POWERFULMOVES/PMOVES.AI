"""Unload a TTS engine via Gradio event API."""
import json
import urllib.request
import sys
import time

BASE = "http://127.0.0.1:7860"
engine = sys.argv[1] if len(sys.argv) > 1 else "higgs"

endpoint_map = {
    "higgs": "/handle_unload_higgs",
    "fish_s2": "/handle_unload_fish_s2",
    "kitten": "/handle_unload_kitten",
    "kokoro": "/handle_unload_kokoro",
    "f5": "/handle_f5_unload",
    "chatterbox": "/handle_unload_chatterbox",
}

endpoint = endpoint_map.get(engine)
if not endpoint:
    print(f"Unknown engine: {engine}")
    sys.exit(1)

print(f"Unloading {engine} via {endpoint}...")
req = urllib.request.Request(
    f"{BASE}/gradio_api/call{endpoint}",
    data=json.dumps({"data": []}).encode(),
    headers={"Content-Type": "application/json"},
)
t0 = time.time()
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read())
event_id = result.get("event_id")

# Poll SSE
sse_resp = urllib.request.urlopen(
    f"{BASE}/gradio_api/call{endpoint}/{event_id}", timeout=60
)
for raw_line in sse_resp:
    line = raw_line.decode("utf-8", errors="replace").strip()
    if line.startswith("event:") and "complete" in line:
        print(f"Unloaded in {time.time()-t0:.1f}s")
        break
    if line.startswith("event:") and "error" in line:
        print("Error unloading")
        break
