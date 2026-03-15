# NATS Subject Catalog Gaps — Handoff Document

> **Created:** 2026-03-15
> **For:** Next Claude session (infra lane)
> **Priority:** P2
> **Context:** During Z890 security audit, 30+ NATS subjects were found undocumented in `.claude/context/nats-subjects.md`

---

## Action Required

Register the subjects below into `.claude/context/nats-subjects.md` and update any service docs that publish/subscribe to them.

---

## Undocumented Subjects by Namespace

### `agentzero.task.*` (3 subjects) — CRITICAL: Agent Zero Coordination

| Subject | Publisher | Subscriber | Description |
|---------|-----------|------------|-------------|
| `agentzero.task.submit.v1` | Any agent | Agent Zero | Submit task for orchestration |
| `agentzero.task.status.v1` | Agent Zero | Requesting agent | Task status update |
| `agentzero.task.complete.v1` | Agent Zero | Requesting agent | Task completion notification |

### `pmoves.*` (16 subjects) — Agent Lifecycle & Task Management

| Subject | Publisher | Subscriber | Description |
|---------|-----------|------------|-------------|
| `pmoves.agent.register.v1` | Any agent | Agent Zero | Agent self-registration |
| `pmoves.agent.heartbeat.v1` | All agents | Agent Zero | Periodic agent liveness |
| `pmoves.agent.deregister.v1` | Any agent | Agent Zero | Agent graceful shutdown |
| `pmoves.task.assign.v1` | Agent Zero | Target agent | Task assignment to specific agent |
| `pmoves.task.progress.v1` | Working agent | Agent Zero, UI | Task progress update |
| `pmoves.task.error.v1` | Working agent | Agent Zero | Task error report |
| `pmoves.task.cancel.v1` | Agent Zero | Working agent | Task cancellation request |
| `pmoves.a2a.request.v1` | Any agent | Target agent | Agent-to-Agent direct request |
| `pmoves.a2a.response.v1` | Target agent | Requesting agent | Agent-to-Agent direct response |
| `pmoves.skill.invoke.v1` | Any agent | Skill executor | Skill invocation request |
| `pmoves.skill.result.v1` | Skill executor | Requesting agent | Skill execution result |
| `pmoves.config.update.v1` | Admin/UI | All agents | Configuration change broadcast |
| `pmoves.config.reload.v1` | Admin/UI | Specific agent | Force config reload |
| `pmoves.log.agent.v1` | All agents | Loki/aggregator | Structured agent log entry |
| `pmoves.metric.agent.v1` | All agents | Prometheus push | Agent-level metric report |
| `pmoves.event.lifecycle.v1` | All agents | Observability | Agent lifecycle event (start/stop/error) |

### `content.*` (3 subjects) — Content Publishing Pipeline

| Subject | Publisher | Subscriber | Description |
|---------|-----------|------------|-------------|
| `content.publish.request.v1` | UI/Agent | Publisher services | Content publish request |
| `content.publish.complete.v1` | Publisher | UI/Agent | Publish completed notification |
| `content.moderation.v1` | Content pipeline | Moderation service | Content moderation check |

### `analysis.*` (2 subjects) — Topic Extraction

| Subject | Publisher | Subscriber | Description |
|---------|-----------|------------|-------------|
| `analysis.topic.extract.v1` | Extract worker | LangExtract | Topic extraction request |
| `analysis.topic.result.v1` | LangExtract | Extract worker | Topic extraction result |

### `voice.cast.*` (1 subject) — Cast-TTS Health

| Subject | Publisher | Subscriber | Description |
|---------|-----------|------------|-------------|
| `voice.cast.health_alert.v1` | Cast-TTS gateway | Monitoring | Health alert from cast-tts |

### Service Coordination (misc namespaces)

| Subject | Publisher | Subscriber | Description |
|---------|-----------|------------|-------------|
| `archon.crawl.request.v1` | Agent/UI | Archon | Web crawl request |
| `archon.crawl.result.v1` | Archon | Requesting agent | Crawl result |
| `persona.publish.v1` | Archon | Agent Zero | Persona definition publish |
| `persona.update.v1` | Archon | Agent Zero | Persona update |
| `mesh.node.announce.v2` | Mesh Agent | Agent Zero | Node announcement (v2 format) |
| `kb.upsert.request.v1` | Any agent | Hi-RAG | Knowledge base upsert |
| `kb.upsert.result.v1` | Hi-RAG | Requesting agent | Upsert confirmation |
| `compute.vllm.load.v1` | GPU orchestrator | vLLM worker | Model load command |
| `compute.vllm.status.v1` | vLLM worker | GPU orchestrator | vLLM instance status |
| `hf.model.download.v1` | Any agent | HF downloader | HuggingFace model download |
| `hf.model.ready.v1` | HF downloader | Requesting agent | Model download complete |
| `botz.skill.register.v1` | BoTZ gateway | Agent Zero | Skill registration |
| `botz.skill.health.v1` | BoTZ gateway | Monitoring | Skill health status |
| `a2ui.event.v1` | Any agent | A2UI NATS bridge | UI event for real-time display |
| `a2ui.command.v1` | UI | A2UI NATS bridge | User command from UI |

---

## CGP Version Naming Clarification

There is NO actual conflict — the distinction is intentional:

| Context | Format | Example | Purpose |
|---------|--------|---------|---------|
| NATS transport subject | `geometry.cgp.v{N}` | `geometry.cgp.v1` | Subject routing (stays as-is) |
| Payload spec version | `chit.cgp.v{major}.{minor}` | `chit.cgp.v0.1`, `chit.cgp.v0.2` | Schema versioning inside packet |
| Internal canonical | `chit.cgp.v{major}.{minor}` | `chit.cgp.v1.0` | Documentation reference |

**Recommendation:** Add a note to `nats-subjects.md` explaining this layering so future contributors don't try to "fix" the apparent mismatch.

---

## Registration Checklist

- [ ] Add all subjects above to `.claude/context/nats-subjects.md`
- [ ] Group by namespace with publisher/subscriber annotations
- [ ] Add CGP version naming note
- [ ] Update service CLAUDE.md files that publish these subjects
- [ ] Cross-reference with `pmoves/configs/skill-pairings.yaml` for pipeline subjects
- [ ] Update `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` with CGP clarification
