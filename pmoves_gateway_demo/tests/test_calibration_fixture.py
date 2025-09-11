import json, os, subprocess, sys

def test_mini_calibration():
    root = os.path.dirname(os.path.dirname(__file__))
    cgp = os.path.join(root, "tests", "data", "cgp_fixture.json")
    codebook = os.path.join(root, "tests", "data", "codebook.jsonl")
    out_json = os.path.join(root, "tests", "artifacts", "metrics.json")
    out_md = os.path.join(root, "tests", "artifacts", "metrics.md")
    os.makedirs(os.path.join(root, "tests", "artifacts"), exist_ok=True)
    subprocess.check_call([sys.executable, os.path.join(root, "scripts", "mini_geometry_decode.py"),
                           "--cgp", cgp, "--codebook", codebook, "--out-json", out_json, "--out-md", out_md])
    m = json.load(open(out_json))
    assert m["JS"] <= 0.20
    assert m["coverage"] >= 0.80
