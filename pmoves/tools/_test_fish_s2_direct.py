"""Direct Gradio HTTP test for Fish S2 Pro — setup, load, synth, unload."""
import json
import urllib.request
import sys
import time

BASE = "http://127.0.0.1:7860"


def call_gradio(endpoint, data=None, timeout=300):
    """Call Gradio event API and wait for result."""
    if data is None:
        data = []
    req = urllib.request.Request(
        f"{BASE}/gradio_api/call{endpoint}",
        data=json.dumps({"data": data}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    event_id = json.loads(resp.read()).get("event_id")

    sse_resp = urllib.request.urlopen(
        f"{BASE}/gradio_api/call{endpoint}/{event_id}", timeout=timeout
    )
    current_event = ""
    result = None
    for raw_line in sse_resp:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            raw_data = line[5:].strip()
            if current_event == "complete":
                result = json.loads(raw_data)
                return True, result
            elif current_event == "error":
                return False, raw_data
    return False, "stream ended"


# Fetch defaults
print("Fetching API defaults...")
resp = urllib.request.urlopen(f"{BASE}/gradio_api/info")
info = json.loads(resp.read())
params = info["named_endpoints"]["/generate_unified_tts"]["parameters"]
data = []
for p in params:
    default = p.get("parameter_default")
    if default is not None:
        data.append(default)
    else:
        ptype = p.get("python_type", {}).get("type", "str")
        component = p.get("component", "")
        if component == "Audio" or "filepath" in ptype:
            data.append(None)
        elif "float" in ptype or "int" in ptype:
            data.append(0)
        elif "bool" in ptype:
            data.append(False)
        else:
            data.append("")

data[0] = "Hello, this is a Fish Speech S2 Pro test from the production path."
data[1] = "Fish Speech S2 Pro"
data[2] = "wav"

# Step 1: Setup (repo clone + weights)
print("\n1. Setup (repo + weights)...")
t0 = time.time()
ok, result = call_gradio("/handle_setup_fish_s2", timeout=600)
print(f"   {'OK' if ok else 'FAIL'} ({time.time()-t0:.1f}s): {str(result)[:200]}")
if not ok:
    print("Setup failed, exiting")
    sys.exit(1)

# Step 2: Load model
print("\n2. Loading model...")
t0 = time.time()
ok, result = call_gradio("/handle_load_fish_s2", timeout=120)
print(f"   {'OK' if ok else 'FAIL'} ({time.time()-t0:.1f}s): {str(result)[:200]}")
if not ok:
    print("Load failed, exiting")
    sys.exit(1)

# Step 3: Synthesize
print("\n3. Synthesizing...")
t0 = time.time()
ok, result = call_gradio("/generate_unified_tts", data, timeout=300)
print(f"   {'OK' if ok else 'FAIL'} ({time.time()-t0:.1f}s)")
if ok and isinstance(result, list) and len(result) >= 2:
    print(f"   Audio: {str(result[0])[:200]}")
    print(f"   Status: {result[1]}")
else:
    print(f"   Result: {str(result)[:300]}")

# Step 4: Unload
print("\n4. Unloading...")
t0 = time.time()
ok, result = call_gradio("/handle_unload_fish_s2", timeout=60)
print(f"   {'OK' if ok else 'FAIL'} ({time.time()-t0:.1f}s)")

print("\nDone!")
