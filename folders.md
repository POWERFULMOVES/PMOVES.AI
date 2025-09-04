Directory structure:
└── powerfulmoves-pmoves.ai/
    ├── CATACLYSM_STUDIOS_INC/
    │   └── PMOVES-PROVISIONS/
    │       ├── README.md
    │       ├── backup/
    │       │   ├── linux_backup.sh
    │       │   └── windows_backup.ps1
    │       ├── docker-stacks/
    │       │   ├── cloudflared.yml
    │       │   ├── netdata.yml
    │       │   ├── npm.yml
    │       │   ├── ollama.yml
    │       │   ├── portainer.yml
    │       │   └── jellyfin-ai/
    │       │       ├── docker-compose.yml
    │       │       ├── gemini.md
    │       │       ├── install_plugins.sh
    │       │       ├── jellyfin-ai-media-stack-guide.md
    │       │       ├── jellyfin_plugin_client_guide.md
    │       │       ├── neo4j-setup.cypher
    │       │       ├── plugins.py
    │       │       ├── setup.sh
    │       │       ├── supabase-setup.sql
    │       │       ├── .env.template
    │       │       ├── api-gateway/
    │       │       │   ├── Dockerfile
    │       │       │   ├── package.json
    │       │       │   └── server.js
    │       │       ├── audio-processor/
    │       │       │   ├── Dockerfile
    │       │       │   ├── entrypoint.sh
    │       │       │   ├── main.py
    │       │       │   └── requirements.txt
    │       │       └── dashboard/
    │       │           ├── Dockerfile
    │       │           ├── package.json
    │       │           ├── public/
    │       │           │   └── index.html
    │       │           └── src/
    │       │               ├── App.css
    │       │               └── App.js
    │       ├── jetson/
    │       │   ├── jetson-postinstall.sh
    │       │   ├── ngc_login.sh
    │       │   └── pull_and_save.sh
    │       ├── linux/
    │       │   ├── scripts/
    │       │   │   └── pop-postinstall.sh
    │       │   └── ubuntu-autoinstall/
    │       │       ├── meta-data
    │       │       └── user-data
    │       ├── proxmox/
    │       │   ├── pve9_postinstall.sh
    │       │   └── pve_on_debian13.sh
    │       ├── tailscale/
    │       │   └── tailscale_up.sh
    │       ├── ventoy/
    │       │   └── ventoy.json
    │       └── windows/
    │           ├── Autounattend.xml
    │           └── win-postinstall.ps1
    ├── docs/
    │   ├── notesfordev.md
    │   ├── PMOVES.md
    │   ├── PMOVES_ARC.md
    │   └── PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md
    ├── pmoves/
    │   ├── README.md
    │   ├── docker-compose.yml
    │   ├── Makefile
    │   ├── PMOVES_hirag_hybrid_service.zip
    │   ├── pmoves_hirag_hybrid_upgrade.patch
    │   ├── pmoves_starter.patch
    │   ├── STARTER_PR_BODY.md
    │   ├── .env.example
    │   ├── comfyui/
    │   │   └── minio_loader.py
    │   ├── contracts/
    │   │   ├── topics.json
    │   │   └── schemas/
    │   │       ├── analysis/
    │   │       │   ├── extract-topics.request.v1.schema.json
    │   │       │   └── extract-topics.result.v1.schema.json
    │   │       ├── common/
    │   │       │   └── envelope.schema.json
    │   │       ├── content/
    │   │       │   ├── publish.approved.v1.schema.json
    │   │       │   └── published.v1.schema.json
    │   │       ├── gen/
    │   │       │   ├── image.request.v1.schema.json
    │   │       │   ├── image.result.v1.schema.json
    │   │       │   ├── text.request.v1.schema.json
    │   │       │   └── text.result.v1.schema.json
    │   │       ├── ingest/
    │   │       │   ├── file-added.v1.schema.json
    │   │       │   └── transcript-ready.v1.schema.json
    │   │       └── kb/
    │   │           ├── search.request.v1.schema.json
    │   │           ├── search.result.v1.schema.json
    │   │           ├── upsert.request.v1.schema.json
    │   │           └── upsert.result.v1.schema.json
    │   ├── datasets/
    │   │   └── pmoves_smoke.json
    │   ├── docs/
    │   │   └── HI-RAG_UPGRADE.md
    │   ├── n8n/
    │   │   └── flows/
    │   │       ├── approval_poller.json
    │   │       └── echo_publisher.json
    │   ├── neo4j/
    │   │   └── cypher/
    │   │       └── 001_init.cypher
    │   ├── schemas/
    │   │   ├── analysis.entities.v1.json
    │   │   ├── gen.asset.v1.json
    │   │   ├── ingest.document.v1.json
    │   │   └── kb.write.v1.json
    │   ├── services/
    │   │   ├── agent-zero/
    │   │   │   ├── Dockerfile
    │   │   │   ├── main.py
    │   │   │   └── requirements.txt
    │   │   ├── agents/
    │   │   │   └── pubsub_stub.py
    │   │   ├── analysis-echo/
    │   │   │   ├── Dockerfile
    │   │   │   ├── requirements.txt
    │   │   │   └── worker.py
    │   │   ├── archon/
    │   │   │   ├── Dockerfile
    │   │   │   ├── main.py
    │   │   │   └── requirements.txt
    │   │   ├── comfy-watcher/
    │   │   │   ├── Dockerfile
    │   │   │   ├── requirements.txt
    │   │   │   └── watcher.py
    │   │   ├── comfyui/
    │   │   │   └── prompt_examples/
    │   │   │       └── pmoves_basic_prompt.json
    │   │   ├── common/
    │   │   │   └── events.py
    │   │   ├── graph-linker/
    │   │   │   ├── Dockerfile
    │   │   │   ├── linker.py
    │   │   │   ├── requirements.txt
    │   │   │   └── migrations/
    │   │   │       └── 01_init.cypher
    │   │   ├── hi-rag-gateway/
    │   │   │   ├── Dockerfile
    │   │   │   ├── gateway.py
    │   │   │   └── requirements.txt
    │   │   ├── n8n/
    │   │   │   └── workflows/
    │   │   │       ├── pmoves_comfy_gen.json
    │   │   │       ├── pmoves_content_approval.json
    │   │   │       └── pmoves_echo_ingest.json
    │   │   ├── publisher/
    │   │   │   ├── Dockerfile
    │   │   │   ├── publisher.py
    │   │   │   └── requirements.txt
    │   │   ├── retrieval-eval/
    │   │   │   ├── Dockerfile
    │   │   │   ├── requirements.txt
    │   │   │   ├── server.py
    │   │   │   └── static/
    │   │   │       └── index.html
    │   │   └── supabase/
    │   │       └── init/
    │   │           └── 00_pmoves_schema.sql
    │   ├── supabase/
    │   │   └── sql/
    │   │       └── 001_init.sql
    │   └── .github/
    │       └── workflows/
    │           └── ci.yml
    └── pmoves-v5/
        ├── README.md
        ├── docker-compose.yml
        ├── .env.example
        ├── contracts/
        │   ├── topics.json
        │   └── schemas/
        │       ├── analysis/
        │       │   ├── extract-topics.request.v1.schema.json
        │       │   └── extract-topics.result.v1.schema.json
        │       ├── common/
        │       │   └── envelope.schema.json
        │       ├── content/
        │       │   ├── publish.approved.v1.schema.json
        │       │   └── published.v1.schema.json
        │       ├── gen/
        │       │   ├── image.request.v1.schema.json
        │       │   ├── image.result.v1.schema.json
        │       │   ├── text.request.v1.schema.json
        │       │   └── text.result.v1.schema.json
        │       ├── ingest/
        │       │   ├── file-added.v1.schema.json
        │       │   └── transcript-ready.v1.schema.json
        │       └── kb/
        │           ├── search.request.v1.schema.json
        │           ├── search.result.v1.schema.json
        │           ├── upsert.request.v1.schema.json
        │           └── upsert.result.v1.schema.json
        └── services/
            ├── agent-zero/
            │   ├── Dockerfile
            │   ├── main.py
            │   └── requirements.txt
            ├── analysis-echo/
            │   ├── Dockerfile
            │   ├── requirements.txt
            │   └── worker.py
            ├── archon/
            │   ├── Dockerfile
            │   ├── main.py
            │   └── requirements.txt
            ├── comfy-watcher/
            │   ├── Dockerfile
            │   ├── requirements.txt
            │   └── watcher.py
            ├── comfyui/
            │   └── prompt_examples/
            │       └── pmoves_basic_prompt.json
            ├── common/
            │   └── events.py
            ├── graph-linker/
            │   ├── Dockerfile
            │   ├── linker.py
            │   ├── requirements.txt
            │   └── migrations/
            │       └── 01_init.cypher
            ├── n8n/
            │   └── workflows/
            │       ├── pmoves_comfy_gen.json
            │       ├── pmoves_content_approval.json
            │       └── pmoves_echo_ingest.json
            ├── publisher/
            │   ├── Dockerfile
            │   ├── publisher.py
            │   └── requirements.txt
            └── supabase/
                └── init/
                    └── 00_pmoves_schema.sql
