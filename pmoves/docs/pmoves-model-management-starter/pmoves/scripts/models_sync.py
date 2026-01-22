#!/usr/bin/env python3
import os, sys, subprocess, argparse, json
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr); sys.exit(1)

ROOT = Path(__file__).resolve().parents[2]  # repo root
MODELS = ROOT / "pmoves" / "models"
ENV_DIR = ROOT  # write .env.*.override at repo root

def write_override(filename, envmap: dict):
    out = []
    for k,v in envmap.items():
        out.append(f"{k}={v}")
    Path(filename).write_text("\n".join(out) + "\n")
    print(f"wrote {filename}")
    return filename

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
    return write_override(ENV_DIR/".env.agent-zero.override", envmap)

def sync_archon(m):
    emb = m["embedding"]["default"]
    rer = m["reranker"]["default"]
    hirag = m.get("hirag",{})
    envmap = {
        "HIRAG_EMBED_MODEL": emb,
        "HIRAG_RERANK_MODEL": rer,
        "HIRAG_RERANK_ENABLED": "true" if hirag.get("enable_rerank",True) else "false",
        "GRAPH_BOOST": str(hirag.get("graph_boost", 0.15)),
        "OLLAMA_URL": hirag.get("ollama_url", "http://ollama:11434"),
        "SENTENCE_MODEL": hirag.get("sentence_model_fallback","all-MiniLM-L6-v2"),
    }
    return write_override(ENV_DIR/".env.hirag.override", envmap)

def sync_media(m, host):
    envmap={}
    if "vision" in m and host.startswith("jetson"):
        det = m["vision"]["jetson_orin_8gb"]["detector"]
        envmap["MEDIA_DETECTOR_MODEL"] = det
        envmap["MEDIA_DETECTOR_TRT_ENGINE"] = os.getenv("MEDIA_DETECTOR_TRT_ENGINE", "/models/yolo/jetson.trt")
    if "asr" in m:
        if host.startswith("jetson"):
            asr = m["asr"]["jetson_orin_8gb"]
        elif "workstation" in host:
            asr = m["asr"]["workstation_5090"]
        else:
            asr = m["asr"]["laptop_4090"]
        envmap["WHISPER_MODEL"] = asr.split()[0]
        envmap["WHISPER_PROVIDER"] = "faster-whisper" if "faster-whisper" in asr else "openai-whisper"
    return write_override(ENV_DIR/".env.media.override", envmap)

def sync_creator(m, host):
    vlm = m["vlm"]["workstation_5090"] if "workstation" in host else m["vlm"]["laptop_4090"]
    flows = ",".join(m.get("sd_workflows",{}).get("comfyui",[]))
    envmap = {
        "VLM_MODEL": vlm,
        "COMFY_WORKFLOWS": flows
    }
    return write_override(ENV_DIR/".env.creator.override", envmap)

def do_sync(args):
    m = load_manifest(args.profile)
    if args.profile == "agent-zero":
        sync_agent_zero(m, args.host, args.tensorzero_base)
    elif args.profile == "archon":
        sync_archon(m)
    elif args.profile == "media":
        sync_media(m, args.host)
    elif args.profile == "vlm-and-creator":
        sync_creator(m, args.host)
    else:
        sys.exit(f"unknown profile: {args.profile}")
    print("OK: env overrides written. Restart relevant service(s).")

def do_swap(args):
    if args.service in ("agents","agent-zero"):
        envf = ENV_DIR/".env.agent-zero.override"
        base = {}
        if args.name: base["AGENT_ZERO_MODEL_ID"] = args.name
        write_override(envf, base)
    elif args.service in ("hi-rag-gateway-v2","hirag"):
        envf = ENV_DIR/".env.hirag.override"
        base = {}
        if args.name: base["HIRAG_RERANK_MODEL"] = args.name
        write_override(envf, base)
    elif args.service.startswith("media"):
        envf = ENV_DIR/".env.media.override"
        base = {}
        if args.name:
            if "whisper" in args.name:
                base["WHISPER_MODEL"] = args.name
            else:
                base["MEDIA_DETECTOR_MODEL"] = args.name
        write_override(envf, base)
    elif args.service in ("creator","comfyui"):
        envf = ENV_DIR/".env.creator.override"
        base = {}
        if args.name: base["VLM_MODEL"] = args.name
        write_override(envf, base)
    else:
        sys.exit(f"unknown service: {args.service}")
    print("OK: override updated.")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sync")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--host", required=True)
    sp.add_argument("--tensorzero-base", default="http://tensorzero:3000")
    sp.add_argument("--dry-run", action="store_true")
    ss = sub.add_parser("swap")
    ss.add_argument("--profile", required=True)
    ss.add_argument("--host", required=True)
    ss.add_argument("--service", required=True)
    ss.add_argument("--name", default="")
    args = ap.parse_args()
    if args.cmd=="sync": do_sync(args)
    else: do_swap(args)

if __name__=="__main__":
    main()
