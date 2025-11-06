#!/usr/bin/env python3
import os, sys, argparse, json
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr); sys.exit(1)

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT / "pmoves" / "models"
ENV_LOCAL = ROOT / "pmoves" / ".env.local"

def _load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                k,v = line.split('=',1)
                env[k.strip()] = v
    return env

def _write_env(path: Path, env: dict):
    lines = [f"{k}={v}" for k,v in env.items()]
    path.write_text("\n".join(lines)+"\n")
    print(f"wrote {path}")

def pull_hint(model_id:str, provider:str):
    if provider == "ollama":
        return f"ollama pull {model_id}"
    if provider == "vllm":
        return f"# vLLM: ensure HF weights cached for {model_id}"
    if provider == "llama.cpp" and ("gguf" in model_id or "-q" in model_id):
        return f"# GGUF: use huggingface_hub snapshot_download for {model_id}"
    if provider == "cloudflare":
        return "# Remote (Cloudflare Workers AI): ensure API key + model route in TensorZero"
    return f"# provider={provider} model={model_id}"

def load_manifest(profile):
    p = MODELS / f"{profile}.yaml"
    if not p.exists():
        sys.exit(f"manifest not found: {p}")
    return yaml.safe_load(p.read_text())

def sync_agent_zero(m, host, tz_base):
    tgt = m["targets"][host]
    model_id = tgt["llm"]; provider = tgt.get("provider","ollama")
    envmap = {
        "AGENT_ZERO_MODEL_ID": model_id,
        "AGENT_ZERO_DECODING": json.dumps(tgt.get("decoding", {"temperature":0.3,"top_p":0.8})),
        "AGENT_ZERO_CONTEXT_WINDOW": str(tgt.get("ctx", 32768)),
        "OPENAI_COMPAT_BASE_URL": tz_base,
    }
    print(pull_hint(model_id, provider))
    return envmap

def sync_archon(m):
    emb = m["embedding"]["default"]
    rer = m["reranker"]["default"]
    hirag = m.get("hirag",{})
    envmap = {
        "RERANK_ENABLE": "true" if hirag.get("enable_rerank",True) else "false",
        "RERANK_MODEL": rer,
        "GRAPH_BOOST": str(hirag.get("graph_boost", 0.15)),
        "SENTENCE_MODEL": hirag.get("sentence_model_fallback","all-MiniLM-L6-v2"),
        "OLLAMA_URL": hirag.get("ollama_url", "http://pmoves-ollama:11434"),
        "TENSORZERO_EMBED_MODEL": m["embedding"].get("tensorzero","tensorzero::embedding_model_name::gemma_embed_local"),
        "OLLAMA_EMBED_MODEL": m["embedding"].get("local_ollama","embeddinggemma:300m"),
    }
    return envmap

def sync_media(m, host):
    envmap={}
    if "vision" in m and host.startswith("jetson"):
        det = m["vision"]["jetson_orin_8gb"]["detector"]
        envmap["MEDIA_DETECTOR_MODEL"] = det
    if "asr" in m:
        if host.startswith("jetson"):
            asr = m["asr"]["jetson_orin_8gb"]
        elif "workstation" in host:
            asr = m["asr"]["workstation_5090"]
        else:
            asr = m["asr"]["laptop_4090"]
        envmap["WHISPER_MODEL"] = asr.split()[0]
        envmap["FFW_PROVIDER"] = "faster-whisper" if "faster-whisper" in asr else "openai-whisper"
    return envmap

def sync_creator(m, host):
    vlm = m["vlm"]["workstation_5090"] if "workstation" in host else m["vlm"]["laptop_4090"]
    envmap = {"VLM_MODEL": vlm}
    return envmap

def merge_into_env(local_env:dict, updates:dict) -> dict:
    out = dict(local_env)
    out.update({k:str(v) for k,v in updates.items()})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["sync","swap"], help="sync writes recommended env values into pmoves/.env.local")
    ap.add_argument("--profile", required=True, help="agent-zero|archon|media|vlm-and-creator")
    ap.add_argument("--host", default="workstation_5090")
    ap.add_argument("--tensorzero-base", default=os.getenv("TENSORZERO_BASE_URL","http://tensorzero-gateway:3000"))
    ap.add_argument("--service", default="")
    ap.add_argument("--name", default="")
    args = ap.parse_args()

    local = _load_env(ENV_LOCAL)
    m = load_manifest(args.profile)

    updates = {}
    if args.command == "sync":
        if args.profile == "agent-zero": updates = sync_agent_zero(m, args.host, args.tensorzero_base)
        elif args.profile == "archon": updates = sync_archon(m)
        elif args.profile == "media": updates = sync_media(m, args.host)
        elif args.profile == "vlm-and-creator": updates = sync_creator(m, args.host)
        else: sys.exit(f"unknown profile: {args.profile}")
    else:
        # light swap shortcuts
        if args.service in ("agents","agent-zero") and args.name:
            updates = {"AGENT_ZERO_MODEL_ID": args.name}
        elif args.service in ("hi-rag-gateway-v2","hirag") and args.name:
            updates = {"RERANK_MODEL": args.name}
        elif args.service.startswith("media") and args.name:
            updates = {"WHISPER_MODEL": args.name}
        elif args.service in ("creator","comfyui") and args.name:
            updates = {"VLM_MODEL": args.name}
        else:
            sys.exit("unknown service or name not provided")

    merged = merge_into_env(local, updates)
    _write_env(ENV_LOCAL, merged)
    print("OK: pmoves/.env.local updated. Restart affected services (e.g., make up, recreate-v2).")

if __name__ == "__main__":
    main()
