"""Fetch all 121 parameter defaults from Gradio API and test Higgs with proper defaults."""
import json
import urllib.request
import sys
import time

BASE = "http://127.0.0.1:7860"

# Fetch API info
resp = urllib.request.urlopen(f"{BASE}/gradio_api/info")
info = json.loads(resp.read())
endpoint = info.get("named_endpoints", {}).get("/generate_unified_tts", {})
params = endpoint.get("parameters", [])

print(f"Total params: {len(params)}")

# Build array with ALL defaults filled in
data = []
none_positions = []
for i, p in enumerate(params):
    default = p.get("parameter_default")
    data.append(default)
    if default is None:
        none_positions.append(i)

print(f"Params with None default: {none_positions}")
print()

# Override core + Higgs params
data[0] = "Hello, this is a Higgs Audio test."  # text_input
data[1] = "Higgs Audio"  # tts_engine
data[2] = "wav"  # audio_format

# Show what positions 73-82 look like with defaults
print("Higgs positions (73-82) with API defaults:")
for i in range(73, 83):
    p = params[i]
    print(f"  [{i}] {p.get('parameter_name','?')} = {repr(data[i])}")

print()
print(f"Position 76 (system_prompt) = {repr(data[76])}")
print()

# Submit with all defaults
print("Submitting with ALL defaults filled...")
req = urllib.request.Request(
    f"{BASE}/gradio_api/call/generate_unified_tts",
    data=json.dumps({"data": data}).encode(),
    headers={"Content-Type": "application/json"},
)
t0 = time.time()
resp = urllib.request.urlopen(req, timeout=30)
submit_data = json.loads(resp.read())
event_id = submit_data.get("event_id")
print(f"Event ID: {event_id} ({time.time()-t0:.1f}s)")

# Stream SSE
print("Streaming SSE response...")
sse_url = f"{BASE}/gradio_api/call/generate_unified_tts/{event_id}"
sse_resp = urllib.request.urlopen(sse_url, timeout=240)

current_event = ""
for raw_line in sse_resp:
    line = raw_line.decode("utf-8", errors="replace").rstrip("\\n\\r")
    if line.startswith("event:"):
        current_event = line[6:].strip()
    elif line.startswith("data:"):
        raw_data = line[5:].strip()
        print(f"  [{current_event}] {raw_data[:300]}")
        if current_event == "complete":
            print(f"\\nSUCCESS in {time.time()-t0:.1f}s")
            sys.exit(0)
        elif current_event == "error":
            print(f"\\nERROR in {time.time()-t0:.1f}s")
            sys.exit(1)
