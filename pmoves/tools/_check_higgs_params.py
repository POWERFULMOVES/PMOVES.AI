"""Diagnostic: check Gradio API param spec for Higgs Audio fields."""
import json
import urllib.request

resp = urllib.request.urlopen("http://127.0.0.1:7860/gradio_api/info")
info = json.loads(resp.read())
endpoint = info.get("named_endpoints", {}).get("/generate_unified_tts", {})
params = endpoint.get("parameters", [])

print(f"Total params: {len(params)}")
print()

# Show full spec for positions 75-80 (Higgs range)
for i in range(75, 81):
    p = params[i]
    print(f"[{i}] parameter_name={p.get('parameter_name', 'N/A')}")
    print(f"    label={p.get('label', 'N/A')}")
    print(f"    python_type={p.get('python_type', {}).get('type', '?')}")
    print(f"    parameter_default={p.get('parameter_default', 'NO_DEFAULT')}")
    print(f"    component={p.get('component', 'N/A')}")
    print()

# Also check what gradio_client.predict actually maps
print("--- All params with 'higgs' in parameter_name ---")
for i, p in enumerate(params):
    name = p.get("parameter_name", "")
    if "higgs" in name.lower():
        print(f"[{i}] parameter_name={name}, label={p.get('label', '')}")
