"""Test Higgs with ALL None positions replaced with type-appropriate defaults."""
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

# Build array with ALL defaults, replacing None with type-appropriate values
data = []
for i, p in enumerate(params):
    default = p.get("parameter_default")
    if default is not None:
        data.append(default)
    else:
        # Fill None with type-appropriate default
        ptype = p.get("python_type", {}).get("type", "str")
        component = p.get("component", "")
        if component == "Audio" or "filepath" in ptype:
            data.append(None)  # Audio/File inputs stay None (optional)
        elif "float" in ptype or "int" in ptype:
            data.append(0)
        elif "bool" in ptype:
            data.append(False)
        else:
            data.append("")  # str default

print(f"Total params: {len(data)}")

# Override core + Higgs
data[0] = "Hello, this is a Higgs Audio test."
data[1] = "Higgs Audio"
data[2] = "wav"

# Show None positions and what we filled them with
print("Filled None positions:")
for i, p in enumerate(params):
    if p.get("parameter_default") is None:
        print(f"  [{i}] {p.get('parameter_name','?')} ({p.get('component','?')}) -> {repr(data[i])}")

print()
print("Submitting...")
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
    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
    if line.startswith("event:"):
        current_event = line[6:].strip()
    elif line.startswith("data:"):
        raw_data = line[5:].strip()
        print(f"  [{current_event}] {raw_data[:500]}")
        if current_event == "complete":
            print(f"\nSUCCESS in {time.time()-t0:.1f}s")
            result = json.loads(raw_data)
            if isinstance(result, list) and len(result) >= 2:
                print(f"Audio: {str(result[0])[:200]}")
                print(f"Status: {result[1]}")
            sys.exit(0)
        elif current_event == "error":
            print(f"\nERROR in {time.time()-t0:.1f}s")
            sys.exit(1)
