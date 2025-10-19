import argparse, requests, json
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8000")
ap.add_argument("--cid", default="8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111")
ap.add_argument("--modalities", default="text,video,audio,doc,image")
ap.add_argument("--minProj", type=float, default=0.5)
ap.add_argument("--minConf", type=float, default=0.5)
ap.add_argument("--limit", type=int, default=50)
args = ap.parse_args()
url = f"{args.base}/mindmap/{args.cid}"
params = dict(modalities=args.modalities, minProj=args.minProj, minConf=args.minConf, limit=args.limit)
r = requests.get(url, params=params, timeout=20)
r.raise_for_status()
print(json.dumps(r.json(), indent=2))
