# Repository Directory Map

_Last updated: 2025-10-21_

This document captures the current layout of the `PMOVES.AI` repository to help new contributors find key resources quickly. The tree below is trimmed to a maximum depth of two levels (root → child → grandchild) to balance detail and readability.

## Regenerating this map

Run the following command from the repository root to rebuild the listing. Adjust `MAX_DEPTH` if you need a deeper or shallower view, and add/remove entries in `EXCLUDES` to skip generated assets or other noise.

```bash
python - <<'PY'
from pathlib import Path

ROOT = Path('.')
MAX_DEPTH = 2
EXCLUDES = {'.git', '__pycache__', '.DS_Store'}

def walk(path: Path, prefix: str = "", depth: int = 0):
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
├── .gitattributes
├── .github/
│   ├── CODEOWNERS
│   ├── README-badge-snippet.md
│   ├── copilot-instructions.md
│   ├── pull_request_template.md
│   └── workflows/
│       ├── chit-contract.yml
│       ├── env-preflight.yml
│       ├── python-tests.yml
│       ├── sql-policy-lint.yml
│       └── webhook-smoke.yml
├── .gitignore
├── .vscode/
│   └── mcp.json
├── AGENTS.md
├── CATACLYSM_STUDIOS_INC/
│   ├── PMOVES-PROVISIONS/
│   │   ├── README.md
│   │   ├── backup/
│   │   ├── desktop.ini
│   │   ├── docker-stacks/
│   │   ├── docs/
│   │   ├── jetson/
│   │   ├── linux/
│   │   ├── proxmox/
│   │   ├── tailscale/
│   │   ├── ventoy/
│   │   └── windows/
│   └── desktop.ini
├── README.md
├── SECURITY.md
├── docs/
│   ├── COPILOT_REVIEW_WORKFLOW.md
│   ├── LOCAL_CI_CHECKS.md
│   ├── PMOVES.md
│   ├── PMOVES_ARC.md
│   ├── PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md
│   ├── REPO_RULES.md
│   ├── hi-rag-gateway-trusted-proxy-tests.md
│   ├── notes/
│   │   └── mermaid-fixes-2025-10-02.md
│   ├── notesfordev.md
│   └── repoingest/
│       ├── agent0ai-agent-zero.txt
│       ├── charmbracelet-crush.txt
│       └── coleam00-archon.txt
├── folders.md
├── pmoves/
│   ├── .env.example
│   ├── .env.local.example
│   ├── .env.supa.local.example
│   ├── .env.supa.remote.example
│   ├── .envrc.example
│   ├── .github/
│   │   ├── PR_M2_AUTOMATION.md
│   │   └── workflows/
│   ├── .gitignore
│   ├── .tmp_demo.jsonl
│   ├── AGENTS.md
│   ├── Makefile
│   ├── PR_BODY_HIRAG_PLUS_EVAL.md
│   ├── README.md
│   ├── comfyui/
│   │   ├── custom_nodes/
│   │   └── minio_loader.py
│   ├── compose/
│   │   ├── agent-zero/
│   │   ├── docker-compose.core.yml
│   │   ├── docker-compose.firefly.yml
│   │   ├── docker-compose.flows-watcher.yml
│   │   └── docker-compose.wger.yml
│   ├── configs/
│   │   └── agents/
│   ├── chit/
│   │   ├── __init__.py
│   │   └── codec.py
│   ├── contracts/
│   │   ├── samples/
│   │   ├── schemas/
│   │   └── topics.json
│   ├── datasets/
│   │   ├── example_capsule.json
│   │   ├── log_sample.xml
│   │   ├── personas/
│   │   ├── pmoves_entities_tiny.json
│   │   ├── pmoves_smoke.json
│   │   ├── queries.jsonl
│   │   ├── queries_demo.jsonl
│   │   ├── sample.pdf
│   │   └── structured_dataset.example.jsonl
│   ├── docker-compose.gpu.yml
│   ├── docker-compose.n8n.yml
│   ├── docker-compose.realtime.yml
│   ├── docker-compose.supabase.yml
│   ├── docker-compose.yml
│   ├── docs/
│   │   ├── COMFYUI_END_TO_END.md
│   │   ├── COMFYUI_MINIO_PRESIGN.md
│   │   ├── CREATOR_PIPELINE.md
│   │   ├── DATA_IMPORT.md
│   │   ├── Enhanced Media Stack with Advanced AudioVideo Analysis/
│   │   ├── HI-RAG_UPGRADE.md
│   │   ├── HIRAG_QWEN_CUDA_NOTES.md
│   │   ├── HI_RAG_RERANKER.md
│   │   ├── HI_RAG_RERANK_PROVIDERS.md
│   │   ├── LANGEXTRACT.md
│   │   ├── LOCAL_DEV.md
│   │   ├── M2_VALIDATION_GUIDE.md
│   │   ├── MAKE_TARGETS.md
│   │   ├── N8N_CHECKLIST.md
│   │   ├── N8N_SETUP.md
│   │   ├── NEXT_STEPS.md
│   │   ├── creator/
│   │   ├── PMOVES-CONCHexecution_guide.pdf
│   │   ├── PMOVES-CONCHexecution_guideb.pdf
│   │   ├── PMOVES.ffmpeg/
│   │   ├── PMOVES.md
│   │   ├── PMOVES.yt/
│   │   ├── PMOVES_ARC.md
│   │   ├── PMOVES_Enhanced_Visual_Architecture_Diagrams.md
│   │   ├── PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md
│   │   ├── README_DOCS_INDEX.md
│   │   ├── REALTIME_LISTENER.md
│   │   ├── RENDER_COMPLETION_WEBHOOK.md
│   │   ├── RETRIEVAL_EVAL_GUIDE.md
│   │   ├── ROADMAP.md
│   │   ├── SECRETS.md
│   │   ├── SESSION_IMPLEMENTATION_PLAN.md
│   │   ├── SMOKETESTS.md
│   │   ├── SUPABASE_DISCORD_AUTOMATION.md
│   │   ├── SUPABASE_FULL.md
│   │   ├── SUPABASE_RLS_CHECKLIST.md
│   │   ├── SUPABASE_SWITCH.md
│   │   ├── TAILSCALE_DISCORD_RUNBOOK.md
│   │   ├── TELEMETRY_ROI.md
│   │   ├── archonupdateforpmoves.md
│   │   ├── agent_zero_cuda docs/
│   │   ├── archive/
│   │   ├── cipher_pmoves_bundle/
│   │   ├── codex_full_config_bundle/
│   │   ├── codexconfig.md
│   │   ├── context/
│   │   ├── evals/
│   │   ├── events/
│   │   ├── notesfordev.md
│   │   ├── p.md
│   │   ├── pmoves_chit_all_in_one/
│   │   ├── pmoves_enhanced_diagrams.md
│   │   ├── pmoves_v_5.12.md
│   │   ├── repoingest/
│   │   ├── stocksharp-stocksharp.txt
│   │   └── understand/
│   ├── env.hirag.reranker.additions
│   ├── env.hirag.reranker.providers.additions
│   ├── env.presign.additions
│   ├── env.publisher.enrich.additions
│   ├── env.render_webhook.additions
│   ├── environment.yml
│   ├── libs/
│   │   ├── langextract/
│   │   └── providers/
│   ├── integrations/
│   │   ├── firefly-iii/
│   │   │   └── n8n/
│   │   ├── health-wger/
│   │   │   └── n8n/
│   │   └── pr-kits
│   ├── n8n/
│   │   └── flows/
│   ├── neo4j/
│   │   ├── cypher/
│   │   └── datasets/
│   ├── pmoves_provisioning_pr_pack/
│   │   ├── README_APPLY.txt
│   │   ├── docker-compose.gpu.yml
│   │   ├── patches/
│   │   └── scripts/
│   ├── pr_body.md
│   ├── schemas/
│   │   ├── analysis.entities.v1.json
│   │   ├── gen.asset.v1.json
│   │   ├── ingest.document.v1.json
│   │   └── kb.write.v1.json
│   ├── scripts/
│   │   ├── apply_migrations_docker.ps1
│   │   ├── apply_migrations_docker.sh
│   │   ├── buildx-agent-zero.ps1
│   │   ├── buildx-agent-zero.sh
│   │   ├── codex_bootstrap.ps1
│   │   ├── codex_bootstrap.sh
│   │   ├── create_venv.ps1
│   │   ├── create_venv.sh
│   │   ├── create_venv_min.ps1
│   │   ├── create_venv_min.sh
│   │   ├── discord_ping.ps1
│   │   ├── discord_ping.sh
│   │   ├── n8n-flows-watcher.sh
│   │   ├── n8n-import-flows.sh
│   │   ├── env_check.ps1
│   │   ├── env_check.sh
│   │   ├── env_setup.ps1
│   │   ├── env_setup.sh
│   │   ├── extract_supa_md.ps1
│   │   ├── init_avatars.py
│   │   ├── install/
│   │   ├── install_all_requirements.ps1
│   │   ├── install_all_requirements.sh
│   │   ├── pmoves.ps1
│   │   ├── proxmox/
│   │   ├── setup.ps1
│   │   ├── smoke.ps1
│   │   └── windows_bootstrap.ps1
│   ├── services/
│   │   ├── agent-zero/
│   │   ├── agent_zero/
│   │   ├── agents/
│   │   ├── analysis-echo/
│   │   ├── archon/
│   │   │   ├── README.md
│   │   ├── comfy-watcher/
│   │   ├── comfyui/
│   │   ├── common/
│   │   ├── extract-worker/
│   │   ├── ffmpeg-whisper/
│   │   ├── gateway/
│   │   ├── graph-linker/
│   │   ├── hi-rag-gateway/
│   │   ├── hi-rag-gateway-v2/
│   │   ├── jellyfin-bridge/
│   │   ├── langextract/
│   │   ├── media-audio/
│   │   ├── media-video/
│   │   ├── mesh-agent/
│   │   ├── notebook-sync/
│   │   ├── n8n/
│   │   ├── pdf-ingest/
│   │   ├── pmoves-yt/
│   │   ├── presign/
│   │   ├── publisher/
│   │   ├── publisher-discord/
│   │   ├── render-webhook/
│   │   ├── retrieval-eval/
│   │   └── supabase/
│   ├── supabase/
│   │   ├── initdb/
│   │   ├── migrations/
│   │   └── sql/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_ffmpeg_whisper.py
│   │   ├── test_hirag_gateway.py
│   │   ├── test_langextract.py
│   │   └── test_pmoves_yt.py
│   └── tools/
│       ├── chit_codebook_gen.py
│       ├── chit_decode_secrets.py
│       ├── chit_encode_secrets.py
│       ├── chit_security.py
│       ├── env_dedupe.py
│       ├── evidence_log.ps1
│       ├── evidence_log.sh
│       ├── evidence_stamp.ps1
│       ├── evidence_stamp.sh
│       ├── flightcheck/
│       ├── publish_content_published.ps1
│       ├── publish_content_published.sh
│       ├── publish_handshake.py
│       ├── realtime_listener.py
│       ├── requirements-minimal.txt
│       ├── seed_studio_board.ps1
│       ├── seed_studio_board.sh
│       └── smoke_webhook.py
└── repomix-output.xml
```
