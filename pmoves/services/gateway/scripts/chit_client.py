"""
scripts/chit_client.py — end-to-end smoke test client.

Usage:
  python scripts/chit_client.py --base http://localhost:8000 \
    --cgp tests/data/cgp_fixture.json \
    --sign "secret" --encrypt-anchors

Steps:
  - (optional) sign/encrypt CGP
  - POST /geometry/event
  - POST /geometry/decode/text
  - POST /geometry/calibration/report
"""
import os, json, argparse, requests, tempfile, subprocess, sys

from gateway.api.chit import compute_shape_id

def maybe_sign(cgp: dict, sign: str=None, encrypt: bool=False) -> dict:
    if not sign and not encrypt: 
        return cgp
    import importlib.util, pathlib
    # Load signer dynamically
    signer_path = pathlib.Path("scripts") / "chit_sign.py"
    if not signer_path.exists():
        print("signer not found at", signer_path, file=sys.stderr); return cgp
    # Use subprocess to keep deps simple
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json"); tmp.close()
    json.dump(cgp, open(tmp.name, "w", encoding="utf-8"))
    outp = tempfile.NamedTemporaryFile(delete=False, suffix=".json"); outp.close()
    cmd = [sys.executable, str(signer_path), "--in", tmp.name, "--out", outp.name]
    if sign: cmd += ["--passphrase", sign]
    if encrypt: cmd += ["--encrypt-anchors"]
    subprocess.check_call(cmd)
    out = json.load(open(outp.name, "r", encoding="utf-8"))
    os.unlink(tmp.name); os.unlink(outp.name)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--cgp", default="tests/data/cgp_fixture.json")
    ap.add_argument("--sign", default=None)
    ap.add_argument("--encrypt-anchors", action="store_true")
    ap.add_argument("--per-constellation", type=int, default=5)
    args = ap.parse_args()

    cgp = json.load(open(args.cgp, "r", encoding="utf-8"))
    cgp = maybe_sign(cgp, args.sign, args.encrypt_anchors)

    s = requests.Session()

    shape_id = compute_shape_id(cgp)

    # 1) publish
    envelope = {"type": "geometry.cgp.v1", "data": cgp}
    r = s.post(f"{args.base}/geometry/event", json=envelope, timeout=20)
    r.raise_for_status()
    print("Publish:", r.json(), "shape_id=", shape_id)

    # 2) decode
    const_ids = []
    for sn in cgp.get("super_nodes", []) or []:
        for const in sn.get("constellations", []) or []:
            cid = const.get("id")
            if cid:
                const_ids.append(cid)
    decode_body = {
        "shape_id": shape_id,
        "constellation_ids": const_ids,
        "per_constellation": args.per_constellation,
    }
    r = s.post(f"{args.base}/geometry/decode/text", json=decode_body, timeout=20)
    r.raise_for_status()
    items = r.json().get("items", [])
    print(f"Decode: got {len(items)} items")
    for it in items[:5]:
        print("-", it.get("text"))

    # 3) calibration
    r = s.post(f"{args.base}/geometry/calibration/report", json=cgp, timeout=20)
    r.raise_for_status()
    print("Calibration:", r.json())

if __name__ == "__main__":
    main()
