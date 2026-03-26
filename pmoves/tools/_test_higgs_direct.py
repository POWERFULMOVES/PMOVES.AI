"""Direct Gradio HTTP test for Higgs Audio — mirrors production provider path."""
import json
import urllib.request
import sys
import time

BASE = "http://127.0.0.1:7860"

# Build 121-element array matching _build_params() in ultimate_tts.py
data = [None] * 121
data[0] = "Hello, this is a Higgs Audio test."  # text_input
data[1] = "Higgs Audio"  # tts_engine
data[2] = "wav"  # audio_format
data[75] = "EMPTY"  # higgs_voice_preset
data[76] = ""  # higgs_system_prompt (empty string, NOT None)
data[77] = 1.0  # higgs_temperature
data[78] = 0.95  # higgs_top_p
data[79] = 50  # higgs_top_k
data[80] = 1024  # higgs_max_tokens
data[81] = 7  # higgs_ras_win_len
data[82] = 2  # higgs_ras_win_max_num_repeat

print(f"Position 76 value: {repr(data[76])}")
print(f"Position 76 type: {type(data[76])}")
print()

# Step 1: Submit
print("Submitting to Gradio API...")
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

# Step 2: Stream SSE
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
        print(f"  [{current_event}] {raw_data[:300]}")
        if current_event == "complete":
            print(f"\nSUCCESS in {time.time()-t0:.1f}s")
            result = json.loads(raw_data)
            print(f"Result type: {type(result)}")
            if isinstance(result, list) and len(result) >= 2:
                print(f"Audio info: {str(result[0])[:200]}")
                print(f"Status: {result[1]}")
            sys.exit(0)
        elif current_event == "error":
            print(f"\nERROR in {time.time()-t0:.1f}s: {raw_data}")
            sys.exit(1)

print(f"Stream ended without complete/error event ({time.time()-t0:.1f}s)")
