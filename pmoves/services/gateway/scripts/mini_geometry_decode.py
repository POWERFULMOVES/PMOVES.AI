
import json, math, os, argparse, subprocess, sys
from typing import List, Dict, Any

def _load_jsonl(path: str):
    out=[]; 
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out

def empirical_spectrum(vals, rmin, rmax, bins):
    if rmax <= rmin: rmax = rmin + 1e-6
    width = (rmax - rmin) / bins
    hist = [0]*bins
    for v in vals:
        b = int((v - rmin) / width)
        if b < 0: b = 0
        if b >= bins: b = bins-1
        hist[b] += 1
    total = float(sum(hist)) or 1.0
    return [h/total for h in hist]

def kl(p,q):
    eps=1e-9
    return sum(pi*(math.log((pi+eps)/(qi+eps))) for pi,qi in zip(p,q))

def js(p,q):
    m=[(pi+qi)/2 for pi,qi in zip(p,q)]
    return 0.5*kl(p,m) + 0.5*kl(q,m)

def main(cgp_path, codebook_path, out_json, out_md):
    cgp = json.load(open(cgp_path,"r",encoding="utf-8"))
    code = _load_jsonl(codebook_path)
    const = cgp["super_nodes"][0]["constellations"][0]
    u = const["anchor"]; nrm = sum(x*x for x in u)**0.5 or 1.0
    u = [x/nrm for x in u]
    vals = [sum(a*b for a,b in zip(u, row["vec"])) for row in code]
    rmin, rmax = const["radial_minmax"]
    bins = cgp["meta"]["bins"]
    emp = empirical_spectrum(vals, rmin, rmax, bins)
    tgt = const["spectrum"]
    score = {"KL": kl(tgt, emp), "JS": js(tgt, emp), "coverage": sum(1 for e in emp if e>0)/bins}
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(score, open(out_json,"w",encoding="utf-8"), indent=2)
    open(out_md,"w",encoding="utf-8").write(f"# Calibration Report (mini)\n\n- KL: {score['KL']:.4f}\n- JS: {score['JS']:.4f}\n- Coverage: {score['coverage']:.2f}\n")

if __name__=="__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cgp", default="tests/data/cgp_fixture.json")
    ap.add_argument("--codebook", default="tests/data/codebook.jsonl")
    ap.add_argument("--out-json", default="tests/artifacts/metrics.json")
    ap.add_argument("--out-md", default="tests/artifacts/metrics.md")
    a = ap.parse_args()
    os.makedirs("tests/artifacts", exist_ok=True)
    main(a.cgp, a.codebook, a.out_json, a.out_md)
    print("Wrote", a.out_json, "and", a.out_md)
