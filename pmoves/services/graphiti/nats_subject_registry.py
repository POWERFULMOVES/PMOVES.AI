"""GRAPHITI NATS Subject Registry.

Tracks all 88 GRAPHITI-related NATS subjects defined in TAC trees.
Each subject has a status: 'wired' (has subscriber code), 'stub' (has stub subscriber), 'defined_only' (TAC tree only).

Generated: 2026-04-17
Source: pmoves/configs/tac_trees/ (6 files with GRAPHITI/CHIT references)
See: research/part1_tac_trees_analysis.md section 4 for full subject catalog
"""

from typing import Dict, List

from pmoves.services.common.nats_types import SubjectEntry


SUBJECT_REGISTRY: List[SubjectEntry] = [
    # ----------------------------------------------------------------
    # pr-monitor-graphiti-chit Pipeline (6 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("ops.pr.monitor.completed.v1", "stub", "pr-monitor",
                 "pmoves/services/graphiti/stage1_pr_monitor.py",
                 "codex", "Stub — raises NotImplementedError"),
    SubjectEntry("ops.pr.trim.completed.v1", "stub", "pr-trim",
                 "pmoves/services/graphiti/stage2_pr_trim.py",
                 "claude-opus", "Stub — raises NotImplementedError"),
    SubjectEntry("ops.pr.learnings.encoded.v1", "stub", "chit-encode",
                 "pmoves/services/graphiti/stage3_chit_encode.py",
                 "tokenism", "Stub — raises NotImplementedError"),
    SubjectEntry("ops.pr.review.completed.v1", "defined_only", "pr-review",
                 "", "archon", "TAC tree defined — no subscriber code"),
    SubjectEntry("ops.pr.monitor.failed.v1", "defined_only", "pr-monitor",
                 "", "codex", "TAC tree defined — no subscriber code"),
    SubjectEntry("skills.pipeline.pr-monitor-graphiti-chit.v1", "defined_only", "orchestration",
                 "", "floos-resolver", "Pipeline orchestration — no subscriber code"),

    # ----------------------------------------------------------------
    # Stage 4: Sign Trail (1 subject) — WIRED
    # ----------------------------------------------------------------
    SubjectEntry("agent.graphiti.signed.v1", "wired", "sign-trail",
                 "pmoves/tools/sign_trail.py",
                 "archon", "Implemented — delegates to chit_security"),

    # ----------------------------------------------------------------
    # CHIT/CGP Geometry Bus (8 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("geometry.cgp.v1", "defined_only", "geometry",
                 "", "tokenism", "CGP transport via Supabase Realtime"),
    SubjectEntry("geometry.cgp.calibration.v1", "defined_only", "geometry",
                 "", "evo-controller", "CGP calibration"),
    SubjectEntry("geometry.event.v1", "defined_only", "geometry",
                 "", "tokenism", "Raw geometry events"),
    SubjectEntry("geometry.packet.encoded.v1", "defined_only", "geometry",
                 "", "tokenism", "CGP packet encoded — chit-encode output"),
    SubjectEntry("geometry.swarm.meta.v1", "defined_only", "geometry",
                 "", "tokenism", "Swarm metadata"),
    SubjectEntry("tokenism.cgp.ready.v1", "defined_only", "evolution",
                 "", "consciousness_service", "CGP packet readiness"),
    SubjectEntry("tokenism.cgp.weekly.v1", "defined_only", "evolution",
                 "", "tokenism", "Weekly CGP export"),
    SubjectEntry("tokenism.simulation.result.v1", "defined_only", "evolution",
                 "", "tokenism", "Simulation results"),

    # ----------------------------------------------------------------
    # Tokenism / Evolution (5 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("tokenism.swarm.population.v1", "defined_only", "evolution",
                 "", "tokenism", "Swarm population updates"),
    SubjectEntry("tokenism.attribution.recorded.v1", "defined_only", "evolution",
                 "", "tokenism", "Attribution recording"),
    SubjectEntry("tokenism.credential.rotated.v1", "defined_only", "evolution",
                 "", "tokenism", "Credential rotation audit"),
    SubjectEntry("tokenism.geometry.event.v1", "defined_only", "evolution",
                 "", "flute_gateway", "Voice attribution from flute-gateway"),
    SubjectEntry("tokenism.prosodic.bpm.v1", "defined_only", "evolution",
                 "", "flute_gateway", "BPM prosodic timeline from flute-gateway"),

    # ----------------------------------------------------------------
    # Training Pipeline (6 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("training.job.started.v1", "defined_only", "training",
                 "", "trainer", "Training job started"),
    SubjectEntry("training.job.completed.v1", "defined_only", "training",
                 "", "trainer", "Training job completed"),
    SubjectEntry("training.job.failed.v1", "defined_only", "training",
                 "", "trainer", "Training job failed"),
    SubjectEntry("training.eval.result.v1", "defined_only", "training",
                 "", "trainer", "Evaluation result"),
    SubjectEntry("training.model.published.v1", "defined_only", "training",
                 "", "trainer", "Model published"),
    SubjectEntry("training.model.deployed.v1", "defined_only", "training",
                 "", "trainer", "Model deployed"),

    # ----------------------------------------------------------------
    # Skill Pipeline Orchestration (10 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("skills.pipeline.model-benchmark-viz.v1", "defined_only", "skills",
                 "", "floos-resolver", "Model benchmark viz pairing"),
    SubjectEntry("skills.pipeline.ingest-chit-index.v1", "defined_only", "skills",
                 "", "floos-resolver", "Ingest CHIT index pairing"),
    SubjectEntry("skills.pipeline.research-render.v1", "defined_only", "skills",
                 "", "floos-resolver", "Research render pairing"),
    SubjectEntry("skills.pipeline.chit-3d-viz.v1", "defined_only", "skills",
                 "", "floos-resolver", "CHIT 3D visualization pairing"),
    SubjectEntry("skills.pipeline.voice-synthesis.v1", "defined_only", "skills",
                 "", "floos-resolver", "Voice synthesis pairing"),
    SubjectEntry("skills.pipeline.agent-card-gen.v1", "defined_only", "skills",
                 "", "floos-resolver", "Agent card generation pairing"),
    SubjectEntry("skills.pipeline.health-sync.v1", "defined_only", "skills",
                 "", "floos-resolver", "Health sync pairing"),
    SubjectEntry("skills.pipeline.finance-sync.v1", "defined_only", "skills",
                 "", "floos-resolver", "Finance sync pairing"),
    SubjectEntry("skills.pipeline.training-eval-deploy.v1", "defined_only", "skills",
                 "", "floos-resolver", "Training eval deploy pairing"),
    SubjectEntry("skills.pipeline.*.v1", "defined_only", "skills",
                 "", "floos-resolver", "Wildcard monitoring (chit:floos)"),

    # ----------------------------------------------------------------
    # Skill Step Hooks (14 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("skills.step.model-trainer.done.v1", "defined_only", "skills",
                 "", "trainer", "Model trainer step done"),
    SubjectEntry("skills.step.hf-benchmark.done.v1", "defined_only", "skills",
                 "", "benchmarker", "HF benchmark step done"),
    SubjectEntry("skills.step.a2ui-chart.done.v1", "defined_only", "skills",
                 "", "a2ui", "A2UI chart step done"),
    SubjectEntry("skills.step.remotion-render.done.v1", "defined_only", "skills",
                 "", "remotion", "Remotion render step done"),
    SubjectEntry("skills.step.extract-worker.done.v1", "defined_only", "skills",
                 "", "extract-worker", "Extract worker step done"),
    SubjectEntry("skills.step.text-generate.done.v1", "defined_only", "skills",
                 "", "text-generator", "Text generate step done"),
    SubjectEntry("skills.step.prosodic-analyze.done.v1", "defined_only", "skills",
                 "", "prosodic-analyzer", "Prosodic analysis step done"),
    SubjectEntry("skills.step.tts-synthesize.done.v1", "defined_only", "skills",
                 "", "tts", "TTS synthesize step done"),
    SubjectEntry("skills.step.theme-lookup.done.v1", "defined_only", "skills",
                 "", "theme-lookup", "Theme lookup step done"),
    SubjectEntry("skills.step.comfyui-generate.done.v1", "defined_only", "skills",
                 "", "comfyui", "ComfyUI generate step done"),
    SubjectEntry("skills.step.chit-encode.done.v1", "defined_only", "skills",
                 "", "tokenism", "CHIT encode step done (implicit from geometry.packet.encoded.v1)"),
    SubjectEntry("skills.pipeline.ingest-chit-index.done.v1", "defined_only", "skills",
                 "", "indexer", "Ingest CHIT index done"),
    SubjectEntry("skills.pipeline.chit-3d-viz.done.v1", "defined_only", "skills",
                 "", "viz-renderer", "CHIT 3D viz done"),
    SubjectEntry("skills.pipeline.voice-synthesis.done.v1", "defined_only", "skills",
                 "", "voice-synthesizer", "Voice synthesis done"),

    # ----------------------------------------------------------------
    # Orchestration Team (5 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("supaserch.request.v1", "defined_only", "orchestration",
                 "", "orchestrator", "Supaserch request"),
    SubjectEntry("supaserch.result.v1", "defined_only", "orchestration",
                 "", "supaserch", "Supaserch result"),
    SubjectEntry("agent.tool.executed.v1", "defined_only", "orchestration",
                 "", "agent-runtime", "Agent tool executed"),
    SubjectEntry("botz.mcp.github.tool.executed.v1", "defined_only", "orchestration",
                 "", "botz-gateway", "BoTZ MCP GitHub tool executed"),
    SubjectEntry("botz.mcp.github.pr.created.v1", "defined_only", "orchestration",
                 "", "botz-gateway", "BoTZ MCP GitHub PR created"),

    # ----------------------------------------------------------------
    # Research Team (7 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("research.deepresearch.request.v1", "defined_only", "research",
                 "", "researcher", "Deep research request"),
    SubjectEntry("research.deepresearch.result.v1", "defined_only", "research",
                 "", "researcher", "Deep research result"),
    SubjectEntry("research.autoresearch.result.v1", "defined_only", "research",
                 "", "autoresearch", "Autoresearch result"),
    SubjectEntry("cipher.memory.stored.v1", "defined_only", "research",
                 "", "cipher-mcp", "Cipher memory stored"),
    SubjectEntry("cipher.memory.searched.v1", "defined_only", "research",
                 "", "cipher-mcp", "Cipher memory searched"),
    SubjectEntry("cipher.reasoning.stored.v1", "defined_only", "research",
                 "", "cipher-mcp", "Cipher reasoning stored"),
    SubjectEntry("ingest.file.added.v1", "defined_only", "research",
                 "", "ingest", "File added to ingest queue"),

    # ----------------------------------------------------------------
    # Media / Voice (4 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("ingest.transcript.ready.v1", "defined_only", "media",
                 "", "transcribe", "Transcript ready"),
    SubjectEntry("ingest.summary.ready.v1", "defined_only", "media",
                 "", "summarizer", "Summary ready"),
    SubjectEntry("ingest.chapters.ready.v1", "defined_only", "media",
                 "", "chapter-splitter", "Chapters ready"),
    SubjectEntry("voice.agent.response.v1", "defined_only", "media",
                 "", "voice-relay", "Voice agent response — voice-relay publishes here"),

    # ----------------------------------------------------------------
    # Data / Infra (3 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("mesh.node.announce.v1", "defined_only", "infra",
                 "", "node-agent", "Mesh node announcement"),
    SubjectEntry("test.smoke.v1", "defined_only", "infra",
                 "", "smoke-tester", "Smoke test result"),
    SubjectEntry("dev.debug.v1", "defined_only", "infra",
                 "", "debug-service", "Debug event"),

    # ----------------------------------------------------------------
    # UI Team (5 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("remote.session.started.v1", "defined_only", "ui",
                 "", "remote-session", "Remote session started"),
    SubjectEntry("remote.session.ended.v1", "defined_only", "ui",
                 "", "remote-session", "Remote session ended"),
    SubjectEntry("openclaw.message.received.v1", "defined_only", "ui",
                 "", "openclaw", "OpenClaw message received"),
    SubjectEntry("openclaw.message.sent.v1", "defined_only", "ui",
                 "", "openclaw", "OpenClaw message sent"),
    SubjectEntry("openclaw.channel.connected.v1", "defined_only", "ui",
                 "", "openclaw", "OpenClaw channel connected"),

    # ----------------------------------------------------------------
    # Automation Team (2 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("health.workouts.synced.v1", "defined_only", "automation",
                 "", "publisher-discord", "Health workouts synced"),
    SubjectEntry("finance.transactions.synced.v1", "defined_only", "automation",
                 "", "publisher-discord", "Finance transactions synced"),

    # ----------------------------------------------------------------
    # Evolution Team — GPU/Mesh (7 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("mesh.gpu.status.v1", "defined_only", "evolution",
                 "", "gpu-agent", "GPU status update"),
    SubjectEntry("mesh.gpu.model.loaded.v1", "defined_only", "evolution",
                 "", "gpu-agent", "GPU model loaded"),
    SubjectEntry("mesh.gpu.model.unloaded.v1", "defined_only", "evolution",
                 "", "gpu-agent", "GPU model unloaded"),
    SubjectEntry("mesh.gpu.command.v1", "defined_only", "evolution",
                 "", "gpu-agent", "GPU command"),
    SubjectEntry("mesh.gpu.command.result.v1", "defined_only", "evolution",
                 "", "gpu-agent", "GPU command result"),
    SubjectEntry("model.registry.updated.v1", "defined_only", "evolution",
                 "", "model-registry", "Model registry updated"),
    SubjectEntry("agentgym.train.completed.v1", "defined_only", "evolution",
                 "", "agentgym", "AgentGym train completed"),

    # ----------------------------------------------------------------
    # Infrastructure — VPN (4 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("vpn.node.connected.v1", "defined_only", "infra",
                 "", "vpn-agent", "VPN node connected"),
    SubjectEntry("vpn.node.disconnected.v1", "defined_only", "infra",
                 "", "vpn-agent", "VPN node disconnected"),
    SubjectEntry("vpn.auth_key.created.v1", "defined_only", "infra",
                 "", "vpn-agent", "VPN auth key created"),
    SubjectEntry("vpn.route.advertised.v1", "defined_only", "infra",
                 "", "vpn-agent", "VPN route advertised"),

    # ----------------------------------------------------------------
    # External (1 subject)
    # ----------------------------------------------------------------
    SubjectEntry("claude.code.tool.executed.v1", "defined_only", "external",
                 "", "claude-code", "Claude Code tool executed"),

    # ----------------------------------------------------------------
    # Life Integration (6 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("health.metrics.updated.v1", "defined_only", "life",
                 "", "health-service", "Health metrics updated"),
    SubjectEntry("health.workout.completed.v1", "defined_only", "life",
                 "", "health-service", "Health workout completed"),
    SubjectEntry("health.weekly.summary.v1", "defined_only", "life",
                 "", "health-service", "Health weekly summary"),
    SubjectEntry("finance.transactions.ingested.v1", "defined_only", "life",
                 "", "finance-service", "Finance transactions ingested"),
    SubjectEntry("finance.budget.alert.v1", "defined_only", "life",
                 "", "finance-service", "Finance budget alert"),
    SubjectEntry("finance.monthly.summary.v1", "defined_only", "life",
                 "", "finance-service", "Finance monthly summary"),

    # ----------------------------------------------------------------
    # Discord (1 subject)
    # ----------------------------------------------------------------
    SubjectEntry("Discord.messages.fetched.v1", "defined_only", "discord",
                 "", "discord-bot", "Discord messages fetched"),

    # ----------------------------------------------------------------
    # AgentGym — sandbox (2 subjects)
    # ----------------------------------------------------------------
    SubjectEntry("agentgym.train.started.v1", "defined_only", "evolution",
                 "", "agentgym", "AgentGym train started"),
    SubjectEntry("agentgym.model.published.v1", "defined_only", "evolution",
                 "", "agentgym", "AgentGym model published"),
]


def get_subjects_by_status(status: str) -> List[SubjectEntry]:
    """Filter subjects by wiring status."""
    return [s for s in SUBJECT_REGISTRY if s.status == status]


def get_subjects_by_stage(stage: str) -> List[SubjectEntry]:
    """Filter subjects by pipeline stage or team."""
    return [s for s in SUBJECT_REGISTRY if s.stage == stage]


def get_status_summary() -> Dict[str, int]:
    """Return count of subjects per status."""
    summary: Dict[str, int] = {}
    for s in SUBJECT_REGISTRY:
        summary[s.status] = summary.get(s.status, 0) + 1
    return summary


def get_stage_summary() -> Dict[str, int]:
    """Return count of subjects per stage/team."""
    summary: Dict[str, int] = {}
    for s in SUBJECT_REGISTRY:
        summary[s.stage] = summary.get(s.stage, 0) + 1
    return summary


# Quick sanity check on load
assert len(SUBJECT_REGISTRY) == 97, f"Expected 97 subjects, got {len(SUBJECT_REGISTRY)}"  # Fixed: original count 88 was stale; 97 reflects current TAC tree scan (P1-8)
