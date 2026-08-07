// data.generated.js — LIVE tour data, generated from the agent registry (SSOT).
// DO NOT EDIT BY HAND. Regenerate: make -C pmoves chit-tour-data
// source: pmoves/config/agent_registry.yaml · agents: 97 · subjects: 109 · generated: 2026-08-01

const LIVE_META = {
  "generated_at": "2026-08-01",
  "source": "pmoves/config/agent_registry.yaml",
  "agent_count": 97,
  "subject_count": 109,
  "taxonomy_version": "1.5.0"
};

const AGENT_ROSTER = [
  {
    "name": "a0-plugins",
    "cls": "Utility",
    "primary": "Agent",
    "secondary": "Data",
    "tier": 6,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "A2UI",
    "cls": "Standard",
    "primary": "Ui",
    "secondary": "Agent",
    "tier": 7,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "Agent Zero",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Api",
    "tier": 6,
    "stage": "Mega",
    "layers": 7
  },
  {
    "name": "AgentGym",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "AgentGym RL",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "Archon",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Stage 2",
    "layers": 6
  },
  {
    "name": "autoresearch",
    "cls": "Specialized",
    "primary": "Llm",
    "secondary": "Worker",
    "tier": 3,
    "stage": "Pre Stage",
    "layers": 2
  },
  {
    "name": "BoTZ Architect",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "BoTZ Auditor",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "BoTZ Builder",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "BoTZ Gateway",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "Cast TTS Gateway",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Api",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Channel Monitor",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Media",
    "tier": 4,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Cipher Beats Analyst",
    "cls": "Specialized",
    "primary": "Media",
    "secondary": "Agent",
    "tier": 5,
    "stage": "Active",
    "layers": 2
  },
  {
    "name": "Cipher Memory",
    "cls": "Specialized",
    "primary": "Data",
    "secondary": "Agent",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "ClawZ (OpenClaw)",
    "cls": "Standard",
    "primary": "Ui",
    "secondary": "Agent",
    "tier": 7,
    "stage": "Pre Stage",
    "layers": 3
  },
  {
    "name": "Consciousness Service",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "Container Agent",
    "cls": "Utility",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Creator",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Ui",
    "tier": 5,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "Crush",
    "cls": "Standard",
    "primary": "Ui",
    "secondary": "Agent",
    "tier": 7,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Danger Infra",
    "cls": "Utility",
    "primary": "Worker",
    "secondary": "Agent",
    "tier": 4,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "DARKXSIDE Persona",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Stage 2",
    "layers": 4
  },
  {
    "name": "DeepResearch",
    "cls": "Standard",
    "primary": "Llm",
    "secondary": "Worker",
    "tier": 3,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "DoX",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Data",
    "tier": 4,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "E2B Danger Room",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "E2B Desktop",
    "cls": "Standard",
    "primary": "Ui",
    "secondary": "Agent",
    "tier": 7,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "E2B MCP Server",
    "cls": "Utility",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "E2B Spells",
    "cls": "Utility",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "EvoSwarm Controller",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Agent",
    "tier": 4,
    "stage": "Stage 2",
    "layers": 5
  },
  {
    "name": "Extract Worker",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Data",
    "tier": 4,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "FFmpeg-Whisper",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Flute-Gateway",
    "cls": "Standard",
    "primary": "Api",
    "secondary": "Media",
    "tier": 2,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "Fordham Creator",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Media",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Fordham Onboarding",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Fordham Steward",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Api",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Fordham Transaction",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Fordham Voice",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Media",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Gateway Agent",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Api",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Grafana",
    "cls": "Utility",
    "primary": "Ui",
    "secondary": "Data",
    "tier": 7,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Grafana Dashboard Specialist",
    "cls": "Specialized",
    "primary": "Ui",
    "secondary": "Data",
    "tier": 7,
    "stage": "Active",
    "layers": 4
  },
  {
    "name": "Headscale",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Health (wger)",
    "cls": "Specialized",
    "primary": "Ui",
    "secondary": "Data",
    "tier": 7,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "HERMES Agent",
    "cls": "Utility",
    "primary": "Agent",
    "secondary": "Api",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "HF Agent",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "HF Research Agent",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Hi-RAG v2",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Data",
    "tier": 4,
    "stage": "Stage 2",
    "layers": 5
  },
  {
    "name": "Hyperdimensions",
    "cls": "Specialized",
    "primary": "Ui",
    "secondary": "Data",
    "tier": 7,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Invidious",
    "cls": "Utility",
    "primary": "Ui",
    "secondary": "Media",
    "tier": 7,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Jaeger Tracing Specialist",
    "cls": "Specialized",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Active",
    "layers": 3
  },
  {
    "name": "Jellyfin AI Media Stack",
    "cls": "Specialized",
    "primary": "Media",
    "secondary": "Llm",
    "tier": 5,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Jellyfin Bridge",
    "cls": "Specialized",
    "primary": "Media",
    "secondary": "Data",
    "tier": 5,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "KiloCode GLM",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Stage 2",
    "layers": 3
  },
  {
    "name": "LangExtract",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Llm",
    "tier": 4,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Llama Throughput Lab",
    "cls": "Specialized",
    "primary": "Llm",
    "secondary": "Worker",
    "tier": 3,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Loki",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Loki Logs Specialist",
    "cls": "Specialized",
    "primary": "Data",
    "secondary": "Worker",
    "tier": 1,
    "stage": "Active",
    "layers": 3
  },
  {
    "name": "MAI-UI",
    "cls": "Standard",
    "primary": "Ui",
    "secondary": "Agent",
    "tier": 7,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "Media-Audio Analyzer",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Media-Video Analyzer",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "Meilisearch",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Mesh Agent",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Data",
    "tier": 6,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "MinIO",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "n8n",
    "cls": "Utility",
    "primary": "Worker",
    "secondary": "Agent",
    "tier": 4,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "NATS",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "NeMo Claw",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Nemotron Claw",
    "cls": "Specialized",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Neo4j",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Agent",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Notebook Sync",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Data",
    "tier": 4,
    "stage": "Base",
    "layers": 3
  },
  {
    "name": "NotebookLM Agent",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Api",
    "tier": 6,
    "stage": "Parked",
    "layers": 3
  },
  {
    "name": "Open Notebook",
    "cls": "Standard",
    "primary": "Data",
    "secondary": "Ui",
    "tier": 1,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "P7 Room Orchestrator",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Api",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "PDF Ingest",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Data",
    "tier": 4,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "PMOVES CI Bot",
    "cls": "Ci",
    "primary": "Ci",
    "secondary": "Agent",
    "tier": 0,
    "stage": "Active",
    "layers": 1
  },
  {
    "name": "PMOVES Space-Agent",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Worker",
    "tier": 6,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "PMOVES.YT",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 4
  },
  {
    "name": "Podcast Producer",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "PR Hedge Trim",
    "cls": "Utility",
    "primary": "Worker",
    "secondary": "Agent",
    "tier": 4,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "Presign",
    "cls": "Utility",
    "primary": "Api",
    "secondary": "Data",
    "tier": 2,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Prometheus",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Ui",
    "tier": 1,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Prometheus Metrics Specialist",
    "cls": "Specialized",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Active",
    "layers": 3
  },
  {
    "name": "Publisher-Discord",
    "cls": "Standard",
    "primary": "Worker",
    "secondary": "Api",
    "tier": 4,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Qdrant",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Worker",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Remotion Renderer",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Ui",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 2
  },
  {
    "name": "Render Webhook",
    "cls": "Utility",
    "primary": "Api",
    "secondary": "Worker",
    "tier": 2,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "RustDesk",
    "cls": "Utility",
    "primary": "Ui",
    "secondary": "Api",
    "tier": 7,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Supabase",
    "cls": "Utility",
    "primary": "Data",
    "secondary": "Api",
    "tier": 1,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "SupaSerch",
    "cls": "Standard",
    "primary": "Agent",
    "secondary": "Llm",
    "tier": 6,
    "stage": "Stage 2",
    "layers": 5
  },
  {
    "name": "Surf",
    "cls": "Utility",
    "primary": "Agent",
    "secondary": "Ui",
    "tier": 6,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "Swarm Attribution",
    "cls": "Specialized",
    "primary": "Worker",
    "secondary": "Data",
    "tier": 4,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "TensorZero Gateway",
    "cls": "Standard",
    "primary": "Api",
    "secondary": "Llm",
    "tier": 2,
    "stage": "Stage 1",
    "layers": 3
  },
  {
    "name": "TensorZero LLM Observability Specialist",
    "cls": "Specialized",
    "primary": "Llm",
    "secondary": "Data",
    "tier": 3,
    "stage": "Active",
    "layers": 4
  },
  {
    "name": "Transcribe and Fetch",
    "cls": "Specialized",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Ultimate-TTS-Studio",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Llm",
    "tier": 5,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "VPS Fleet Manager",
    "cls": "Utility",
    "primary": "Api",
    "secondary": "Agent",
    "tier": 2,
    "stage": "Base",
    "layers": 2
  },
  {
    "name": "Wealth (Firefly III)",
    "cls": "Specialized",
    "primary": "Ui",
    "secondary": "Data",
    "tier": 7,
    "stage": "Base",
    "layers": 1
  },
  {
    "name": "YouTube Publisher",
    "cls": "Standard",
    "primary": "Media",
    "secondary": "Worker",
    "tier": 5,
    "stage": "Stage 1",
    "layers": 2
  }
];

const NATS_SUBJECTS = [
  {
    "subject": "agent.graphiti.signed.v1",
    "dir": "Pub: DARKXSIDE Persona, KiloCode GLM ▸ Sub: Crush",
    "purpose": "agent · graphiti · signed"
  },
  {
    "subject": "agent.tool.executed.v1",
    "dir": "Pub: Agent Zero ▸ Sub: Jaeger Tracing Specialist",
    "purpose": "agent · tool · executed"
  },
  {
    "subject": "botz.audit.completed.v1",
    "dir": "Pub: BoTZ Auditor",
    "purpose": "botz · audit · completed"
  },
  {
    "subject": "botz.build.completed.v1",
    "dir": "Pub: BoTZ Builder ▸ Sub: BoTZ Auditor",
    "purpose": "botz · build · completed"
  },
  {
    "subject": "botz.heartbeat.v1",
    "dir": "Sub: BoTZ Gateway",
    "purpose": "botz · heartbeat"
  },
  {
    "subject": "botz.plan.created.v1",
    "dir": "Pub: BoTZ Architect ▸ Sub: BoTZ Builder",
    "purpose": "botz · plan · created"
  },
  {
    "subject": "botz.register.v1",
    "dir": "Sub: BoTZ Gateway",
    "purpose": "botz · register"
  },
  {
    "subject": "botz.work.available.v1",
    "dir": "Pub: BoTZ Gateway",
    "purpose": "botz · work · available"
  },
  {
    "subject": "botz.work.claimed.v1",
    "dir": "Sub: BoTZ Gateway",
    "purpose": "botz · work · claimed"
  },
  {
    "subject": "botz.workitem.assigned.v1",
    "dir": "Pub: BoTZ Gateway ▸ Sub: BoTZ Architect",
    "purpose": "botz · workitem · assigned"
  },
  {
    "subject": "botz.workitem.claimed.v1",
    "dir": "Sub: KiloCode GLM",
    "purpose": "botz · workitem · claimed"
  },
  {
    "subject": "branch.<path-segments>.trail.v1",
    "dir": "Pub: PMOVES CI Bot",
    "purpose": "branch · <path-segments> · trail"
  },
  {
    "subject": "chit.signed.v1",
    "dir": "Pub: Fordham Onboarding, Fordham Transaction",
    "purpose": "chit · signed"
  },
  {
    "subject": "cipher.memory.searched.v1",
    "dir": "Pub: Cipher Memory",
    "purpose": "cipher · memory · searched"
  },
  {
    "subject": "cipher.memory.stored.v1",
    "dir": "Pub: Cipher Memory",
    "purpose": "cipher · memory · stored"
  },
  {
    "subject": "cipher.reasoning.stored.v1",
    "dir": "Pub: Cipher Memory",
    "purpose": "cipher · reasoning · stored"
  },
  {
    "subject": "claw.task.assign.v1",
    "dir": "Sub: KiloCode GLM",
    "purpose": "claw · task · assign"
  },
  {
    "subject": "claw.task.complete.v1",
    "dir": "Pub: KiloCode GLM",
    "purpose": "claw · task · complete"
  },
  {
    "subject": "content.publish.approved.v1",
    "dir": "Pub: DARKXSIDE Persona",
    "purpose": "content · publish · approved"
  },
  {
    "subject": "crush.graphiti.discovered.v1",
    "dir": "Pub: Crush",
    "purpose": "crush · graphiti · discovered"
  },
  {
    "subject": "device.cast.discovered.v1",
    "dir": "Pub: Cast TTS Gateway",
    "purpose": "device · cast · discovered"
  },
  {
    "subject": "evoswarm.training.fitness.v1",
    "dir": "Pub: EvoSwarm Controller",
    "purpose": "evoswarm · training · fitness"
  },
  {
    "subject": "evoswarm.training.genome.v1",
    "dir": "Pub: EvoSwarm Controller",
    "purpose": "evoswarm · training · genome"
  },
  {
    "subject": "finance.budget.alert.v1",
    "dir": "Pub: Wealth (Firefly III)",
    "purpose": "finance · budget · alert"
  },
  {
    "subject": "finance.monthly.summary.v1",
    "dir": "Pub: Wealth (Firefly III)",
    "purpose": "finance · monthly · summary"
  },
  {
    "subject": "finance.transactions.ingested.v1",
    "dir": "Pub: Wealth (Firefly III) ▸ Sub: Grafana, Loki, Meilisearch…",
    "purpose": "finance · transactions · ingested"
  },
  {
    "subject": "fleet.enroll.token.v1",
    "dir": "Pub: Fordham Onboarding",
    "purpose": "fleet · enroll · token"
  },
  {
    "subject": "fordham.artifact.published.v1",
    "dir": "Pub: Fordham Creator",
    "purpose": "fordham · artifact · published"
  },
  {
    "subject": "fordham.dashboard.request.v1",
    "dir": "Sub: Fordham Creator, Fordham Voice",
    "purpose": "fordham · dashboard · request"
  },
  {
    "subject": "fordham.dues.received.v1",
    "dir": "Sub: Fordham Transaction",
    "purpose": "fordham · dues · received"
  },
  {
    "subject": "fordham.ledger.entry.v1",
    "dir": "Pub: Fordham Transaction ▸ Sub: Fordham Creator",
    "purpose": "fordham · ledger · entry"
  },
  {
    "subject": "fordham.onboarding.request.v1",
    "dir": "Sub: Fordham Onboarding",
    "purpose": "fordham · onboarding · request"
  },
  {
    "subject": "fordham.roll.updated.v1",
    "dir": "Pub: Fordham Onboarding ▸ Sub: Fordham Creator",
    "purpose": "fordham · roll · updated"
  },
  {
    "subject": "fordham.surplus.updated.v1",
    "dir": "Pub: Fordham Transaction",
    "purpose": "fordham · surplus · updated"
  },
  {
    "subject": "fordham.voice.delivered.v1",
    "dir": "Pub: Fordham Voice",
    "purpose": "fordham · voice · delivered"
  },
  {
    "subject": "geometry.attribution.request.v1",
    "dir": "Sub: Swarm Attribution",
    "purpose": "geometry · attribution · request"
  },
  {
    "subject": "geometry.attribution.result.v1",
    "dir": "Pub: Swarm Attribution ▸ Sub: EvoSwarm Controller",
    "purpose": "geometry · attribution · result"
  },
  {
    "subject": "geometry.cgp.v1",
    "dir": "Sub: DARKXSIDE Persona",
    "purpose": "geometry · cgp"
  },
  {
    "subject": "geometry.consciousness.event.v1",
    "dir": "Pub: Consciousness Service",
    "purpose": "geometry · consciousness · event"
  },
  {
    "subject": "geometry.packet.decoded.v1",
    "dir": "Sub: Flute-Gateway",
    "purpose": "geometry · packet · decoded"
  },
  {
    "subject": "geometry.packet.encoded.v1",
    "dir": "Pub: Hi-RAG v2 ▸ Sub: EvoSwarm Controller",
    "purpose": "geometry · packet · encoded"
  },
  {
    "subject": "geometry.swarm.meta.v1",
    "dir": "Pub: EvoSwarm Controller",
    "purpose": "geometry · swarm · meta"
  },
  {
    "subject": "geometry.visualization.request.v1",
    "dir": "Sub: Hyperdimensions",
    "purpose": "geometry · visualization · request"
  },
  {
    "subject": "health.metrics.scraped.v1",
    "dir": "Pub: Grafana, Loki, Meilisearch…",
    "purpose": "health · metrics · scraped"
  },
  {
    "subject": "health.metrics.updated.v1",
    "dir": "Pub: Health (wger) ▸ Sub: Grafana, Loki, Meilisearch…",
    "purpose": "health · metrics · updated"
  },
  {
    "subject": "health.weekly.summary.v1",
    "dir": "Pub: Health (wger)",
    "purpose": "health · weekly · summary"
  },
  {
    "subject": "health.workout.completed.v1",
    "dir": "Pub: Health (wger) ▸ Sub: Grafana, Loki, Meilisearch…",
    "purpose": "health · workout · completed"
  },
  {
    "subject": "hermes.cron.executed.v1",
    "dir": "Pub: HERMES Agent",
    "purpose": "hermes · cron · executed"
  },
  {
    "subject": "hermes.delegate.completed.v1",
    "dir": "Pub: HERMES Agent",
    "purpose": "hermes · delegate · completed"
  },
  {
    "subject": "hermes.gateway.health.v1",
    "dir": "Pub: HERMES Agent",
    "purpose": "hermes · gateway · health"
  },
  {
    "subject": "hermes.gateway.launched.v1",
    "dir": "Pub: HERMES Agent",
    "purpose": "hermes · gateway · launched"
  },
  {
    "subject": "hermes.mcp.toolcall.v1",
    "dir": "Pub: HERMES Agent",
    "purpose": "hermes · mcp · toolcall"
  },
  {
    "subject": "hermes.skill.curated.v1",
    "dir": "Pub: HERMES Agent",
    "purpose": "hermes · skill · curated"
  },
  {
    "subject": "hf.model.discovered.v1",
    "dir": "Pub: HF Agent ▸ Sub: HF Research Agent",
    "purpose": "hf · model · discovered"
  },
  {
    "subject": "hf.model.evaluated.v1",
    "dir": "Pub: HF Research Agent",
    "purpose": "hf · model · evaluated"
  },
  {
    "subject": "ingest.chapters.ready.v1",
    "dir": "Sub: Publisher-Discord",
    "purpose": "ingest · chapters · ready"
  },
  {
    "subject": "ingest.file.added.v1",
    "dir": "Pub: PMOVES.YT ▸ Sub: Extract Worker, Loki Logs Specialist, Publisher-Discord",
    "purpose": "ingest · file · added"
  },
  {
    "subject": "ingest.summary.ready.v1",
    "dir": "Sub: Publisher-Discord",
    "purpose": "ingest · summary · ready"
  },
  {
    "subject": "ingest.transcript.ready.v1",
    "dir": "Pub: PMOVES.YT ▸ Sub: Publisher-Discord",
    "purpose": "ingest · transcript · ready"
  },
  {
    "subject": "media.ingest.request.v1",
    "dir": "Pub: Cipher Beats Analyst",
    "purpose": "media · ingest · request"
  },
  {
    "subject": "mesh.gpu.model.loaded.v1",
    "dir": "Sub: KiloCode GLM, TensorZero LLM Observability Specialist",
    "purpose": "mesh · gpu · model · loaded"
  },
  {
    "subject": "mesh.gpu.status.v1",
    "dir": "Pub: KiloCode GLM",
    "purpose": "mesh · gpu · status"
  },
  {
    "subject": "mesh.node.announce.v1",
    "dir": "Pub: Mesh Agent ▸ Sub: Agent Zero, HERMES Agent, Health (wger)…",
    "purpose": "mesh · node · announce"
  },
  {
    "subject": "mesh.vps.command.v1",
    "dir": "Sub: VPS Fleet Manager",
    "purpose": "mesh · vps · command"
  },
  {
    "subject": "mesh.vps.deploy.v1",
    "dir": "Pub: VPS Fleet Manager",
    "purpose": "mesh · vps · deploy"
  },
  {
    "subject": "mesh.vps.status.v1",
    "dir": "Pub: VPS Fleet Manager",
    "purpose": "mesh · vps · status"
  },
  {
    "subject": "observability.alert.configured.v1",
    "dir": "Pub: Grafana Dashboard Specialist",
    "purpose": "observability · alert · configured"
  },
  {
    "subject": "observability.dashboard.updated.v1",
    "dir": "Pub: Grafana Dashboard Specialist",
    "purpose": "observability · dashboard · updated"
  },
  {
    "subject": "observability.llm.cost.v1",
    "dir": "Pub: TensorZero LLM Observability Specialist",
    "purpose": "observability · llm · cost"
  },
  {
    "subject": "observability.llm.model_comparison.v1",
    "dir": "Pub: TensorZero LLM Observability Specialist",
    "purpose": "observability · llm · model_comparison"
  },
  {
    "subject": "observability.llm.performance.v1",
    "dir": "Pub: TensorZero LLM Observability Specialist",
    "purpose": "observability · llm · performance"
  },
  {
    "subject": "observability.logs.correlation.v1",
    "dir": "Pub: Loki Logs Specialist",
    "purpose": "observability · logs · correlation"
  },
  {
    "subject": "observability.logs.error.v1",
    "dir": "Pub: Loki Logs Specialist",
    "purpose": "observability · logs · error"
  },
  {
    "subject": "observability.logs.pattern.v1",
    "dir": "Pub: Loki Logs Specialist",
    "purpose": "observability · logs · pattern"
  },
  {
    "subject": "observability.metrics.anomaly.v1",
    "dir": "Pub: Prometheus Metrics Specialist ▸ Sub: Grafana Dashboard Specialist",
    "purpose": "observability · metrics · anomaly"
  },
  {
    "subject": "observability.metrics.trend.v1",
    "dir": "Pub: Prometheus Metrics Specialist",
    "purpose": "observability · metrics · trend"
  },
  {
    "subject": "observability.query.request.v1",
    "dir": "Sub: Grafana Dashboard Specialist, Jaeger Tracing Specialist, Loki Logs Specialist…",
    "purpose": "observability · query · request"
  },
  {
    "subject": "observability.trace.bottleneck.v1",
    "dir": "Pub: Jaeger Tracing Specialist",
    "purpose": "observability · trace · bottleneck"
  },
  {
    "subject": "observability.trace.correlation.v1",
    "dir": "Pub: Jaeger Tracing Specialist",
    "purpose": "observability · trace · correlation"
  },
  {
    "subject": "openclaw.channel.connected.v1",
    "dir": "Pub: ClawZ (OpenClaw)",
    "purpose": "openclaw · channel · connected"
  },
  {
    "subject": "openclaw.message.received.v1",
    "dir": "Pub: ClawZ (OpenClaw)",
    "purpose": "openclaw · message · received"
  },
  {
    "subject": "openclaw.message.sent.v1",
    "dir": "Pub: ClawZ (OpenClaw)",
    "purpose": "openclaw · message · sent"
  },
  {
    "subject": "ops.pr.monitor.completed.v1",
    "dir": "Sub: PR Hedge Trim",
    "purpose": "ops · pr · monitor · completed"
  },
  {
    "subject": "ops.pr.trim.completed.v1",
    "dir": "Pub: PR Hedge Trim",
    "purpose": "ops · pr · trim · completed"
  },
  {
    "subject": "p7.nats.launch",
    "dir": "Sub: HERMES Agent, P7 Room Orchestrator",
    "purpose": "p7 · nats · launch"
  },
  {
    "subject": "p7.nats.launch.v1",
    "dir": "Sub: P7 Room Orchestrator",
    "purpose": "p7 · nats · launch"
  },
  {
    "subject": "p7.nats.session",
    "dir": "Sub: HERMES Agent, P7 Room Orchestrator",
    "purpose": "p7 · nats · session"
  },
  {
    "subject": "p7.nats.session.v1",
    "dir": "Sub: P7 Room Orchestrator",
    "purpose": "p7 · nats · session"
  },
  {
    "subject": "p7.room.checkpoint.v1",
    "dir": "Pub: P7 Room Orchestrator",
    "purpose": "p7 · room · checkpoint"
  },
  {
    "subject": "p7.room.command.failed.v1",
    "dir": "Pub: P7 Room Orchestrator",
    "purpose": "p7 · room · command · failed"
  },
  {
    "subject": "p7.room.session.ended.v1",
    "dir": "Pub: P7 Room Orchestrator",
    "purpose": "p7 · room · session · ended"
  },
  {
    "subject": "p7.room.session.started.v1",
    "dir": "Pub: P7 Room Orchestrator",
    "purpose": "p7 · room · session · started"
  },
  {
    "subject": "p7.room.stage.changed.v1",
    "dir": "Pub: P7 Room Orchestrator",
    "purpose": "p7 · room · stage · changed"
  },
  {
    "subject": "pmoves.darkxside.beats.group.v1",
    "dir": "Pub: Cipher Beats Analyst",
    "purpose": "pmoves · darkxside · beats · group"
  },
  {
    "subject": "pmoves.space.action.v1",
    "dir": "Pub: PMOVES Space-Agent",
    "purpose": "pmoves · space · action"
  },
  {
    "subject": "pmoves.space.event.v1",
    "dir": "Pub: PMOVES Space-Agent",
    "purpose": "pmoves · space · event"
  },
  {
    "subject": "research.autoresearch.result.v1",
    "dir": "Pub: autoresearch",
    "purpose": "research · autoresearch · result"
  },
  {
    "subject": "research.deepresearch.request.v1",
    "dir": "Sub: DeepResearch",
    "purpose": "research · deepresearch · request"
  },
  {
    "subject": "research.deepresearch.result.v1",
    "dir": "Pub: DeepResearch",
    "purpose": "research · deepresearch · result"
  },
  {
    "subject": "room.session.updated.v1",
    "dir": "Pub: Fordham Steward ▸ Sub: DARKXSIDE Persona, Fordham Steward",
    "purpose": "room · session · updated"
  },
  {
    "subject": "shape.trace.recorded.v1",
    "dir": "Pub: Crush",
    "purpose": "shape · trace · recorded"
  },
  {
    "subject": "supaserch.request.v1",
    "dir": "Sub: SupaSerch",
    "purpose": "supaserch · request"
  },
  {
    "subject": "supaserch.result.v1",
    "dir": "Pub: SupaSerch",
    "purpose": "supaserch · result"
  },
  {
    "subject": "tokenism.geometry.event.v1",
    "dir": "Pub: Flute-Gateway",
    "purpose": "tokenism · geometry · event"
  },
  {
    "subject": "tokenism.prosodic.bpm.v1",
    "dir": "Pub: Flute-Gateway ▸ Sub: Fordham Voice",
    "purpose": "tokenism · prosodic · bpm"
  },
  {
    "subject": "voice.cast.completed.v1",
    "dir": "Pub: Cast TTS Gateway",
    "purpose": "voice · cast · completed"
  },
  {
    "subject": "voice.cast.failed.v1",
    "dir": "Pub: Cast TTS Gateway",
    "purpose": "voice · cast · failed"
  },
  {
    "subject": "voice.cast.health_alert.v1",
    "dir": "Pub: Cast TTS Gateway",
    "purpose": "voice · cast · health_alert"
  },
  {
    "subject": "voice.synth.request.v1",
    "dir": "Pub: Fordham Voice",
    "purpose": "voice · synth · request"
  }
];
