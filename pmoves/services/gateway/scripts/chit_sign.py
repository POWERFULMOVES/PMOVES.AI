"""
scripts/chit_sign.py — Sign and optionally encrypt CGPs for PMOVES.AI demos.

Usage:
  python scripts/chit_sign.py --in tests/data/cgp_fixture.json --out data/cgp_signed.json \
         --passphrase "secret" --encrypt-anchors

Flags:
  --passphrase: when provided, HMAC-SHA256 is computed over the CGP (sans 'sig').
  --encrypt-anchors: replaces 'anchor' with 'anchor_enc' (AES-GCM with key derived via scrypt).
"""
import os, json, base64, hashlib, secrets, argparse
from typing import Any, Dict

def canon(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

def hmac_sign(doc: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    d = dict(doc)
    d.pop("sig", None)
    mac = hashlib.new("sha256", passphrase.encode("utf-8"))
    mac.update(canon(d))
    sig = {
        "alg": "HMAC-SHA256",
        "kid": "demo",
        "ts": int(__import__("time").time()),
        "hmac": base64.b64encode(mac.digest()).decode("ascii"),
    }
    doc["sig"] = sig
    return doc

def aesgcm_encrypt_anchor(const: Dict[str, Any], passphrase: str) -> None:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as e:
        raise SystemExit("cryptography is required for --encrypt-anchors") from e
    if "anchor" not in const: 
        return
    anchor = const["anchor"]
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    aead = AESGCM(key)
    aad = canon({"id": const.get("id","")})
    pt = json.dumps(anchor).encode("utf-8")
    ct = aead.encrypt(iv, pt, aad)
    const["anchor_enc"] = {
        "iv": base64.b64encode(iv).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
    }
    const.pop("anchor", None)

def process(cgp: Dict[str, Any], passphrase: str=None, encrypt_anchors: bool=False) -> Dict[str, Any]:
    out = dict(cgp)
    for s in out.get("super_nodes", []):
        for const in s.get("constellations", []):
            if encrypt_anchors and passphrase:
                aesgcm_encrypt_anchor(const, passphrase)
    if passphrase:
        out = hmac_sign(out, passphrase)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--passphrase", dest="passphrase", default=None)
    ap.add_argument("--encrypt-anchors", dest="encrypt", action="store_true")
    args = ap.parse_args()
    cgp = json.load(open(args.inp, "r", encoding="utf-8"))
    out = process(cgp, args.passphrase, args.encrypt)
    os.makedirs(os.path.dirname(args.outp), exist_ok=True)
    json.dump(out, open(args.outp, "w", encoding="utf-8"), indent=2)
    print("Wrote", args.outp)

if __name__ == "__main__":
    main()
