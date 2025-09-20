# Repository Directory Map

_Last updated: 2025-09-20_

This document captures the current layout of the `PMOVES.AI` repository to help new contributors find key resources quickly. T
he tree below is trimmed to a maximum depth of two levels (root → child → grandchild) to balance detail and readability.

## Regenerating this map

Run the following command from the repository root to rebuild the listing. Adjust `MAX_DEPTH` if you need a deeper or shallowe
r view, and add/remove entries in `EXCLUDES` to skip generated assets or other noise.

```bash
python - <<'PY'
from pathlib import Path

ROOT = Path('.')
MAX_DEPTH = 2
EXCLUDES = {'.git', '__pycache__', '.DS_Store'}

def walk(path: Path, prefix: str = '', depth: int = 0):
    entries = sorted(p for p in path.iterdir() if p.name not in EXCLUDES)
    for idx, entry in enumerate(entries):
        connector = '└── ' if idx == len(entries) - 1 else '├── '
        suffix = '/' if entry.is_dir() else ''
        print(f"{prefix}{connector}{entry.name}{suffix}")
        if entry.is_dir() and depth < MAX_DEPTH:
            child_prefix = prefix + ('    ' if idx == len(entries) - 1 else '│   ')
            walk(entry, child_prefix, depth + 1)

print('.\n')
walk(ROOT)
PY
```

## Directory overview (depth 2)

```
.
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   └── workflows/
│       └── chit-contract.yml
├── AGENTS.md
├── CATACLYSM_STUDIOS_INC/
│   ├── PMOVES-PROVISIONS/
│   │   ├── README.md
│   │   ├── backup/
│   │   ├── desktop.ini
│   │   ├── docker-stacks/
│   │   ├── jetson/
│   │   ├── linux/
│   │   ├── proxmox/
│   │   ├── tailscale/
│   │   ├── ventoy/
│   │   └── windows/
│   └── desktop.ini
├── SECURITY.md
├── docs/
│   ├── PMOVES.md
│   ├── PMOVES_ARC.md
│   ├── PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md
│   ├── REPO_RULES.md
│   ├── notesfordev.md
│   └── repoingest/
│       ├── agent0ai-agent-zero.txt
│       ├── charmbracelet-crush.txt
│       └── coleam00-archon.txt
├── folders.md
└── pmoves/
    ├── .env
    ├── .env.example
    ├── .env.local.example
    ├── .env.supa.local.example
    ├── .env.supa.remote.example
    ├── .github/
    │   └── workflows/
    ├── .gitignore
    ├── .tmp_demo.jsonl
    ├── AGENTS.md
    ├── Makefile
    ├── PR_BODY_HIRAG_PLUS_EVAL.md
    ├── README.md
    ├── comfyui/
    │   ├── custom_nodes/
    │   └── minio_loader.py
    ├── compose/
    │   └── agent-zero/
    ├── configs/
    │   └── agents/
    ├── contracts/
    │   ├── schemas/
    │   └── topics.json
    ├── datasets/
    │   ├── example_capsule.json
    │   ├── log_sample.xml
    │   ├── pmoves_entities_tiny.json
    │   ├── pmoves_smoke.json
    │   ├── queries.jsonl
    │   ├── queries_demo.jsonl
    │   ├── sample.pdf
    │   └── structured_dataset.example.jsonl
    ├── docker-compose.realtime.yml
    ├── docker-compose.supabase.yml
    ├── docker-compose.yml
    ├── docs/
    │   ├── COMFYUI_END_TO_END.md
    │   ├── COMFYUI_MINIO_PRESIGN.md
    │   ├── CREATOR_PIPELINE.md
    │   ├── DATA_IMPORT.md
    │   ├── Enhanced Media Stack with Advanced AudioVideo Analysis/
    │   ├── HI-RAG_UPGRADE.md
    │   ├── HIRAG_QWEN_CUDA_NOTES.md
    │   ├── HI_RAG_RERANKER.md
    │   ├── HI_RAG_RERANK_PROVIDERS.md
    │   ├── LANGEXTRACT.md
    │   ├── LOCAL_DEV.md
    │   ├── MAKE_TARGETS.md
    │   ├── NEXT_STEPS.md
    │   ├── PMOVES-CONCHexecution_guide.pdf
    │   ├── PMOVES-CONCHexecution_guideb.pdf
    │   ├── PMOVES.ffmpeg/
    │   ├── PMOVES.md
    │   ├── PMOVES.yt/
    │   ├── PMOVES_ARC.md
    │   ├── PMOVES_Enhanced_Visual_Architecture_Diagrams.md
    │   ├── PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md
    │   ├── README_DOCS_INDEX.md
    │   ├── REALTIME_LISTENER.md
    │   ├── RENDER_COMPLETION_WEBHOOK.md
    │   ├── RETRIEVAL_EVAL_GUIDE.md
    │   ├── ROADMAP.md
    │   ├── SMOKETESTS.md
    │   ├── SUPABASE_FULL.md
    │   ├── SUPABASE_SWITCH.md
    │   ├── agent_zero_cuda docs/
    │   ├── cipher_pmoves_bundle/
    │   ├── codex_full_config_bundle/
    │   ├── codexconfig.md
    │   ├── notesfordev.md
    │   ├── pmoves_chit_all_in_one/
    │   ├── pmoves_enhanced_diagrams.md
    │   ├── repoingest/
    │   ├── stocksharp-stocksharp.txt
    │   └── understand/
    ├── env.hirag.reranker.additions
    ├── env.hirag.reranker.providers.additions
    ├── env.presign.additions
    ├── env.publisher.enrich.additions
    ├── env.render_webhook.additions
    ├── environment.yml
    ├── libs/
    │   ├── langextract/
    │   └── providers/
    ├── n8n/
    │   └── flows/
    ├── neo4j/
    │   └── cypher/
    ├── pr_body.md
    ├── schemas/
    │   ├── analysis.entities.v1.json
    │   ├── gen.asset.v1.json
    │   ├── ingest.document.v1.json
    │   └── kb.write.v1.json
    ├── scripts/
    │   ├── apply_migrations_docker.ps1
    │   ├── apply_migrations_docker.sh
    │   ├── buildx-agent-zero.ps1
    │   ├── buildx-agent-zero.sh
    │   ├── codex_bootstrap.ps1
    │   ├── codex_bootstrap.sh
    │   ├── env_check.ps1
    │   ├── env_check.sh
    │   ├── extract_supa_md.ps1
    │   ├── init_avatars.py
    │   ├── install_all_requirements.ps1
    │   ├── install_all_requirements.sh
    │   ├── pmoves.ps1
    │   └── smoke.ps1
    ├── services/
    │   ├── agent-zero/
    │   ├── agent_zero/
    │   ├── agents/
    │   ├── analysis-echo/
    │   ├── archon/
    │   ├── comfy-watcher/
    │   ├── comfyui/
    │   ├── common/
    │   ├── extract-worker/
    │   ├── ffmpeg-whisper/
    │   ├── gateway/
    │   ├── graph-linker/
    │   ├── hi-rag-gateway/
    │   ├── hi-rag-gateway-v2/
    │   ├── jellyfin-bridge/
    │   ├── langextract/
    │   ├── media-audio/
    │   ├── media-video/
    │   ├── mesh-agent/
    │   ├── n8n/
    │   ├── pdf-ingest/
    │   ├── pmoves-yt/
    │   ├── presign/
    │   ├── publisher/
    │   ├── publisher-discord/
    │   ├── render-webhook/
    │   ├── retrieval-eval/
    │   └── supabase/
    ├── supabase/
    │   ├── initdb/
    │   ├── migrations/
    │   └── sql/
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py
    │   ├── test_ffmpeg_whisper.py
    │   ├── test_hirag_gateway.py
    │   ├── test_langextract.py
    │   └── test_pmoves_yt.py
    └── tools/
        ├── chit_codebook_gen.py
        ├── chit_security.py
        ├── env_dedupe.py
        ├── flightcheck/
        ├── publish_handshake.py
        └── realtime_listener.py
```

