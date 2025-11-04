# Repository Directory Map

_Last updated: 2025-10-27_

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
.
├── .dockerignore
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
│   ├── ABOUT/
│   │   ├── Cataclsymstudios_MVP_&_Community_Engagement.md
│   │   ├── Cataclysm Studios Platform Vision & Brand Identity.md
│   │   ├── Cataclysmstudios_MVP_and_CONTENT.md
│   │   ├── Cataclysmstudios_Research_SIM_TCM.md
│   │   ├── Cataclysmstudios_TCM_FAQ.md
│   │   ├── Cataclysmstudios_YouTube_Channel_Content_Strategy.md
│   │   ├── Charters/
│   │   ├── Consitutions/
│   │   ├── Food Cooperative & Group Buying System - Tokenomics & Smart Contract Design.md
│   │   ├── Food Cooperative & Group Buying System design.md
│   │   ├── Food Cooperative & Group Buying System – Tokenomics & Smart Contract Design (v2.0).md
│   │   ├── Integrating Hybrid Manufacturing Technologies.md
│   │   ├── Integrating Tokenized Cooperative Models 3d.md
│   │   ├── PMOVES_FOOD_GEMREV.pdf
│   │   ├── Projections/
│   │   ├── Proposals/
│   │   ├── Simulation Theory, Holographic Models, and a New AI Communication Paradigm.docx
│   │   ├── Simulation Theory, Holographic Models, and a New AI Communication Paradigm.pdf
│   │   ├── Simulation, Holographic Reality, and High-Dimensional AI Communication.docx
│   │   ├── Simulation, Holographic Reality, and High-Dimensional AI Communication.pdf
│   │   ├── articles.md
│   │   ├── articles_long.md
│   │   ├── food_questionaire_research.md
│   │   ├── notes/
│   │   ├── pmoves_hybrid_tokens.md
│   │   └── pmoves_hybrid_tokens.pdf
│   ├── PMOVES-PROVISIONS/
│   │   ├── README.md
│   │   ├── backup/
│   │   ├── desktop.ini
│   │   ├── docker-stacks/
│   │   ├── docs/
│   │   ├── inventory/
│   │   ├── jetson/
│   │   ├── linux/
│   │   ├── proxmox/
│   │   ├── tailscale/
│   │   ├── ventoy/
│   │   └── windows/
│   └── desktop.ini
├── CRUSH.md
├── GEMINI.md
├── PMOVES.AI Provisioning Bundle Overview.pdf
├── README.md
├── SECURITY.md
├── docs/
│   ├── COPILOT_REVIEW_WORKFLOW.md
│   ├── LOCAL_CI_CHECKS.md
│   ├── PMOVES Multimodal Communication Layer (“Flute”) – Architecture & Roadmap.md
│   ├── PMOVES.md
│   ├── PMOVES_ADVANCED_CAPABILITIES.md
│   ├── PMOVES_AGENT_ENHANCEMENTS.md
│   ├── PMOVES_ARC.md
│   ├── PMOVES_MINI_CLI_SPEC.md
│   ├── PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md
│   ├── REPO_RULES.md
│   ├── SECRETS.md
│   ├── Unified and Modular PMOVES UI Design.md
│   ├── docs_papers_pmoves_multi_agent_paper.md
│   ├── hi-rag-gateway-trusted-proxy-tests.md
│   ├── notes/
│   │   └── mermaid-fixes-2025-10-02.md
│   ├── notesfordev.md
│   ├── papers/
│   │   └── pmoves_multi_agent_paper.md
│   ├── repoingest/
│   │   ├── agent0ai-agent-zero.txt
│   │   ├── charmbracelet-crush.txt
│   │   └── coleam00-archon.txt
│   └── research/
│       └── pmoves_paper_sources.md
├── folders.md
├── pmoves/
│   ├── .compose_config.yaml
│   ├── .dockerignore
│   ├── .env.example
│   ├── .env.hybrid.example
│   ├── .env.local.example
│   ├── .env.supa.local.example
│   ├── .env.supa.remote.example
│   ├── .envrc.example
│   ├── .github/
│   │   ├── PR_M2_AUTOMATION.md
│   │   └── workflows/
│   ├── .gitignore
│   ├── .supabase.env
│   ├── .tmp_demo.jsonl
│   ├── .venv_pmoves_yt/
│   │   ├── bin/
│   │   ├── lib/
│   │   ├── lib64/
│   │   ├── pyvenv.cfg
│   │   └── share/
│   ├── .venv_pubdisc/
│   │   ├── bin/
│   │   ├── lib/
│   │   ├── lib64/
│   │   └── pyvenv.cfg
│   ├── .venv_publisher/
│   │   ├── bin/
│   │   ├── lib/
│   │   ├── lib64/
│   │   └── pyvenv.cfg
│   ├── .venv_publisher_discord/
│   │   ├── bin/
│   │   ├── lib/
│   │   ├── lib64/
│   │   └── pyvenv.cfg
│   ├── .venv_yt/
│   │   ├── bin/
│   │   ├── lib/
│   │   ├── lib64/
│   │   ├── pyvenv.cfg
│   │   └── share/
│   ├── AGENTS.md
│   ├── Makefile
│   ├── NUL
│   ├── PR_BODY_HIRAG_PLUS_EVAL.md
│   ├── README.md
│   ├── __init__.py
│   ├── bootstrap/
│   │   └── registry.json
│   ├── chit/
│   │   ├── __init__.py
│   │   ├── codec.py
│   │   └── secrets_manifest.yaml
│   ├── comfyui/
│   │   ├── custom_nodes/
│   │   └── minio_loader.py
│   ├── compose/
│   │   ├── agent-zero/
│   │   ├── docker-compose.core.yml
│   │   ├── docker-compose.firefly.yml
│   │   ├── docker-compose.flows-watcher.yml
│   │   ├── docker-compose.wger.yml
│   │   └── n8n/
│   ├── config/
│   │   ├── channel_monitor.example.json
│   │   ├── channel_monitor.json
│   │   ├── cookies/
│   │   ├── mcp/
│   │   └── profiles/
│   ├── configs/
│   │   └── agents/
│   ├── contracts/
│   │   ├── samples/
│   │   ├── schemas/
│   │   └── topics.json
│   ├── creator/
│   │   ├── README.md
│   │   ├── installers/
│   │   ├── resources/
│   │   ├── tutorials/
│   │   └── workflows/
│   ├── data/
│   │   ├── agent-zero/
│   │   └── open-notebook/
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
│   ├── db/
│   │   ├── v5_12_grounded_personas.sql
│   │   ├── v5_12_seed.sql
│   │   └── v5_13_geometry_swarm.sql
│   ├── docker-compose.external.yml
│   ├── docker-compose.gpu.yml
│   ├── docker-compose.jellyfin-ai.yml
│   ├── docker-compose.n8n.yml
│   ├── docker-compose.open-notebook.yml
│   ├── docker-compose.realtime.yml
│   ├── docker-compose.supabase.yml
│   ├── docker-compose.yml
│   ├── docs/
│   │   ├── EXTERNAL_INTEGRATIONS_BRINGUP.md
│   │   ├── FIREFLY_WGER_INTEGRATIONS_STATUS.md
│   │   ├── LOCAL_DEV.md
│   │   ├── LOCAL_TOOLING_REFERENCE.md
│   │   ├── MAKE_TARGETS.md
│   │   ├── MERGE_PLAYBOOK_2025-10-19.md
│   │   ├── NEXT_STEPS.md
│   │   ├── PMOVES.AI PLANS/
│   │   ├── PMOVESCHIT/
│   │   ├── PR_DRAFT_REALTIME_FALLBACK_QWEN.md
│   │   ├── README_DOCS_INDEX.md
│   │   ├── ROADMAP.md
│   │   ├── SESSION_IMPLEMENTATION_PLAN.md
│   │   ├── SMOKETESTS.md
│   │   ├── archive/
│   │   ├── context/
│   │   ├── evals/
│   │   ├── events/
│   │   ├── integrations/
│   │   ├── logs/
│   │   ├── notes/
│   │   ├── pmoves_all_in_one/
│   │   └── services/
│   ├── env.hirag.reranker.additions
│   ├── env.hirag.reranker.providers.additions
│   ├── env.jellyfin-ai.example
│   ├── env.presign.additions
│   ├── env.publisher.enrich.additions
│   ├── env.render_webhook.additions
│   ├── env.shared.example
│   ├── environment.yml
│   ├── integrations/
│   │   ├── firefly-iii/
│   │   ├── health-wger/
│   │   └── pr-kits/
│   ├── libs/
│   │   ├── langextract/
│   │   └── providers/
│   ├── n8n/
│   │   └── flows/
│   ├── neo4j/
│   │   ├── cypher/
│   │   └── datasets/
│   ├── pmoves/
│   │   └── data/
│   ├── pmoves-integrations-pr-pack/
│   │   ├── .github/
│   │   ├── INSTRUCTIONS_EXTRAS.md
│   │   ├── Makefile
│   │   ├── PR_INSTRUCTIONS.md
│   │   ├── compose/
│   │   └── scripts/
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
│   │   ├── __init__.py
│   │   ├── _write_test.txt
│   │   ├── apply_migrations_docker.ps1
│   │   ├── apply_migrations_docker.sh
│   │   ├── backfill_jellyfin_metadata.py
│   │   ├── bootstrap_env.py
│   │   ├── buildx-agent-zero.ps1
│   │   ├── buildx-agent-zero.sh
│   │   ├── codex_bootstrap.ps1
│   │   ├── codex_bootstrap.sh
│   │   ├── create_venv.ps1
│   │   ├── create_venv.sh
│   │   ├── create_venv_min.ps1
│   │   ├── create_venv_min.sh
│   │   ├── credentials/
│   │   ├── discord_ping.ps1
│   │   ├── discord_ping.sh
│   │   ├── env_check.ps1
│   │   ├── env_check.sh
│   │   ├── env_setup.ps1
│   │   ├── env_setup.sh
│   │   ├── extract_supa_md.ps1
│   │   ├── hirag_search_to_notebook.py
│   │   ├── init_avatars.py
│   │   ├── install/
│   │   ├── install_all_requirements.ps1
│   │   ├── install_all_requirements.sh
│   │   ├── mindmap_query.py
│   │   ├── mindmap_to_notebook.py
│   │   ├── n8n-flows-watcher.sh
│   │   ├── n8n-import-flows.sh
│   │   ├── neo4j_bootstrap.sh
│   │   ├── notebook_ingest_utils.py
│   │   ├── open_notebook_seed.py
│   │   ├── pmoves.ps1
│   │   ├── proxmox/
│   │   ├── set_open_notebook_password.py
│   │   ├── setup.ps1
│   │   ├── smoke.ps1
│   │   ├── test_m2_loop.py
│   │   ├── update_workflow.py
│   │   ├── wger_brand_defaults.sh
│   │   ├── windows_bootstrap.ps1
│   │   └── yt_transcripts_to_notebook.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent-zero/
│   │   ├── agent_zero/
│   │   ├── agents/
│   │   ├── analysis-echo/
│   │   ├── archon/
│   │   ├── channel-monitor/
│   │   ├── comfy-watcher/
│   │   ├── comfyui/
│   │   ├── common/
│   │   ├── deepresearch/
│   │   ├── evo-controller/
│   │   ├── extract-worker/
│   │   ├── ffmpeg-whisper/
│   │   ├── gateway/
│   │   ├── graph-linker/
│   │   ├── grayjay-plugin-host/
│   │   ├── hi-rag-gateway/
│   │   ├── hi-rag-gateway-v2/
│   │   ├── invidious/
│   │   ├── jellyfin-bridge/
│   │   ├── langextract/
│   │   ├── mcp_youtube_adapter.py
│   │   ├── media-audio/
│   │   ├── media-video/
│   │   ├── mesh-agent/
│   │   ├── n8n/
│   │   ├── notebook-sync/
│   │   ├── pdf-ingest/
│   │   ├── pmoves-yt/
│   │   ├── pmoves_yt/
│   │   ├── presign/
│   │   ├── publisher/
│   │   ├── publisher-discord/
│   │   ├── publisher_discord/
│   │   ├── render-webhook/
│   │   ├── retrieval-eval/
│   │   └── supabase/
│   ├── supabase/
│   │   ├── .gitignore
│   │   ├── config.toml
│   │   ├── initdb/
│   │   ├── migrations/
│   │   └── sql/
│   ├── tensorzero/
│   │   ├── clickhouse/
│   │   └── config/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_ffmpeg_whisper.py
│   │   ├── test_hirag_gateway.py
│   │   ├── test_langextract.py
│   │   ├── test_mini_cli.py
│   │   ├── test_multiagent_workflow.py
│   │   └── test_pmoves_yt.py
│   ├── tools/
│   │   ├── automation_loader.py
│   │   ├── chit_codebook_gen.py
│   │   ├── chit_decode_secrets.py
│   │   ├── chit_encode_secrets.py
│   │   ├── chit_security.py
│   │   ├── consciousness_build.py
│   │   ├── consciousness_ingest.py
│   │   ├── crush_configurator.py
│   │   ├── env_dedupe.py
│   │   ├── events_to_cgp.py
│   │   ├── evidence_log.ps1
│   │   ├── evidence_log.sh
│   │   ├── evidence_stamp.ps1
│   │   ├── evidence_stamp.sh
│   │   ├── flightcheck/
│   │   ├── integrations/
│   │   ├── manifest_audit.py
│   │   ├── mcp_utils.py
│   │   ├── mini_cli.py
│   │   ├── onboarding_helper.py
│   │   ├── profile_loader.py
│   │   ├── publish_content_published.ps1
│   │   ├── publish_content_published.sh
│   │   ├── publish_handshake.py
│   │   ├── realtime_listener.py
│   │   ├── register_media_source.py
│   │   ├── requirements-minimal.txt
│   │   ├── secrets_sync.py
│   │   ├── seed_studio_board.ps1
│   │   ├── seed_studio_board.sh
│   │   ├── smoke_webhook.py
│   │   ├── tests/
│   │   └── youtube_po_token_capture.py
│   ├── ui/
│   │   ├── .gitignore
│   │   ├── README.md
│   │   ├── __tests__/
│   │   ├── app/
│   │   ├── components/
│   │   ├── config/
│   │   ├── e2e/
│   │   ├── eslint.config.mjs
│   │   ├── hooks/
│   │   ├── jest.config.js
│   │   ├── jest.setup.ts
│   │   ├── lib/
│   │   ├── next-env.d.ts
│   │   ├── next.config.mjs
│   │   ├── node_modules/
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   ├── playwright.config.ts
│   │   ├── postcss.config.js
│   │   ├── postcss.config.mjs
│   │   ├── proxy.ts
│   │   ├── public/
│   │   ├── tailwind.config.ts
│   │   └── tsconfig.json
│   └── vendor/
│       └── python/
├── pmoves_provisioning_addon_bundle/
│   ├── README.md
│   ├── addons/
│   │   └── patches/
│   ├── docker-compose.gpu.yml
│   ├── env.shared.example
│   └── pmoves/
│       └── scripts/
├── scripts/
│   ├── check_chit_contract.sh
│   ├── check_jellyfin_credentials.py
│   ├── seed_jellyfin_media.py
│   └── update_supabase_cli.sh
└── supabase/
    ├── .gitignore
    └── config.toml
```
