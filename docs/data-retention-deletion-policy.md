# PMOVES.AI Data Retention & Deletion Policy

**Version**: 1.0.0
**Effective**: 2026-04-25
**Classification**: Internal — Security
**Authority**: PMOVES.AI Cyber Defence Initiative
**Legal Context**: Aligned with Surveillance Accountability Act (Massie, 2026) principles

---

## 1. Purpose

This policy defines retention periods, deletion procedures, and data minimization controls for all data processed by PMOVES.AI's 66-service compose stack. It exists to:

- Minimize data available for warrantless government purchase via third-party data brokers
- Ensure biometric and session data do not accumulate beyond operational necessity
- Provide auditable deletion trails for compliance verification
- Close the data governance gap identified in the PMOVES.AI Defence Assessment (2026-04-25)

> **Core Principle**: Data that does not exist cannot be purchased, subpoenaed, or leaked. Retention is a liability — default to delete.

---

## 2. Data Classification Tiers

| Tier | Label | Description | Examples | Max Retention |
------|-------|-------------|----------|---------------|
 | **T0** | Ephemeral | Transient computation artifacts, no PII | LLM inference outputs, embedding vectors in-flight, NATS jetstream messages | 1 hour |
 | **T1** | Session | Active user interaction context | Agent Zero chat sessions, Supabase auth sessions, WebSocket connections | 24 hours after session close |
 | **T2** | Derived | AI-processed outputs from user input | Hi-RAG indexed documents, knowledge graph entries, research summaries | 30 days |
 | **T3** | Media | Audio/video processing artifacts | Whisper transcripts, YOLOv8 frame annotations, emotion detection results | 7 days |
 | **T4** | Biometric | Data that could identify a person's physical characteristics | Voice prints (from ffmpeg-whisper), facial detection metadata (from media-video), emotion profiles (from media-audio) | **24 hours** — see Biometric Data Handling Policy |
 | **T5** | Infrastructure | Service logs, metrics, health checks | Prometheus metrics, NATS server logs, container stdout | 14 days |
 | **T6** | Credential | Secrets, tokens, API keys | CHIT passphrases, Hostinger API tokens, Supabase service keys, Tailscale auth keys | **Do not persist in logs** — rotate per schedule |

---

## 3. Service-by-Service Retention Map

### 3.1 Agent Services (11 services)

| Service | Data Types | Classification | Retention | Deletion Method |
---------|------------|----------------|-----------|----------------|
 | agent-zero (:5081) | Chat history, tool call logs, session context, **Hostinger API requests**, **messaging API payloads** (Telegram/Discord), **website deployment records** | T1, T6 | T1: 24h / T6: immediate from logs | Auto-purge via Agent Zero memory rotation; Hostinger/messaging payloads excluded from persistence |
 | archon (:8091) | Supabase-driven agent state, workflow context | T1, T2 | T1: 24h / T2: 30d | Supabase TTL column + cron job |
 | cipher-api (:8105) | Knowledge graph entries, embeddings | T2 | 30 days | Qdrant TTL + Neo4j periodic deletion query |
 | mesh-agent | Node announcements, topology state | T0 | 1 hour | NATS jetstream TTL (`--max_age=3600`) |
 | botz-gateway (:8110) | Skill marketplace metadata | T5 | 14 days | Log rotation |
 | a2ui-nats-bridge (:9224) | Bridge routing state | T0 | 1 hour | NATS jetstream TTL |
 | deepresearch | Research plan state (in-memory) | T0 | Process lifetime | No persistence |
 | supaserch (:8099) | Search orchestration state | T0 | Process lifetime | No persistence |
 | publisher-discord (:8094) | Discord webhook payloads | T1 | 24 hours | Log rotation |
 | gateway-agent (:8100) | MCP tool aggregation logs | T5 | 14 days | Log rotation |
 | github-runner-ctl (:8104) | Runner management state | T5 | 14 days | Log rotation |

### 3.2 Data Stores (4 services)

| Service | Data Types | Classification | Retention | Deletion Method |
---------|------------|----------------|-----------|----------------|
 | qdrant (:6333) | Embedding vectors, document metadata | T2 | 30 days | Qdrant collection TTL or periodic sweep `
 | meilisearch (:7700) | Search indices | T2 | 30 days | Index rebuild with filtered source |
 | neo4j (:7474) | Knowledge graph nodes/edges | T2 | 30 days | Cypher deletion query: `MATCH (n) WHERE n.created_at < datetime() - duration({days: 30}) DETACH DELETE n` |
 | minio (:9000) | Object storage (media artifacts) | T3, T4 | T3: 7d / T4: 24h | MinIO lifecycle policy + bucket rules |

### 3.3 Supabase Stack (7 services)

| Service | Data Types | Classification | Retention | Deletion Method |
---------|------------|----------------|-----------|----------------|
 | supabase-db (:5432) | User auth sessions, profiles, agent state | T1 | 24 hours after session close | PostgreSQL `pg_cron` + TTL column on `auth.sessions` |
 | supabase-gotrue (:9999) | JWT tokens, refresh tokens | T6 | Token lifetime only (15m access / 7d refresh) | Built-in expiry — no extension |
 | supabase-postgrest (:3010) | API request logs | T5 | 14 days | PostgREST log config |
 | supabase-kong (:8000) | API gateway logs (may contain PII in query params) | T5, T6 | T5: 14d / T6: strip from logs | Kong log plugin — redact auth headers, query params with tokens |
 | supabase-realtime (:4000) | WebSocket message logs | T0 | 1 hour | Built-in message TTL |
 | supabase-storage (:5000) | Uploaded files | T3 | 7 days | Storage lifecycle policy |
 | supabase-studio (:54323) | Admin UI — no data persistence | N/A | N/A | N/A |

### 3.4 Media Pipeline (6 services) — **HIGH SENSITIVITY**

| Service | Data Types | Classification | Retention | Deletion Method |
---------|------------|----------------|-----------|----------------|
 | ffmpeg-whisper (:8078) | **Audio recordings, voice transcripts, voice prints** | T3, **T4** | T3: 7d / **T4: 24h** | Input audio: immediate post-processing. Transcript text: 7d. Voice print features: 24h max — see Biometric Policy |
 | media-video (:8079) | **Video frames, YOLOv8 detections, facial detection metadata** | T3, **T4** | T3: 7d / **T4: 24h** | Input video: immediate post-processing. Detection metadata: 7d. Facial detection boxes: 24h — see Biometric Policy |
 | media-audio (:8082) | **Audio segments, emotion detection profiles, voice characteristics** | T3, **T4** | T3: 7d / **T4: 24h** | Input audio: immediate post-processing. Emotion labels: 7d. Voice characteristic vectors: 24h — see Biometric Policy |
 | pmoves-yt (:8077) | YouTube metadata, download temp files | T2, T3 | T2: 30d / T3: immediate after processing | Temp files: tmpfs (non-persistent). Metadata: 30d in DB |
 | bgutil-pot-provider | Background utility state | T0 | Process lifetime | No persistence |
 | channel-monitor (:8097) | Channel monitoring state | T5 | 14 days | Log rotation |

### 3.5 LLM/AI Infrastructure (7 services)

| Service | Data Types | Classification | Retention | Deletion Method |
---------|------------|----------------|-----------|----------------|
 | tensorzero-gateway (:3030) | Inference requests (may contain PII in prompts), clickhouse metrics | T0, T5 | T0: immediate / T5: 14d | Prompt logging: disabled in production. Metrics: ClickHouse TTL |
 | tensorzero-clickhouse (:8123) | Metrics, inference metadata | T5 | 14 days | ClickHouse TTL engine |
 | tensorzero-ui (:4000) | Dashboard cache | T0 | Session only | No persistence |
 | pmoves-ollama (:11434) | Model inference (in-memory), model files | T0 | Process lifetime | No logging of prompts — verify `OLLAMA_ORIGINS` and `OLLAMA_HOST` config |
 | gpu-orchestrator | GPU allocation state | T0 | Process lifetime | No persistence |
 | evo-controller (:8113) | Evolution experiment state | T2 | 30 days | Periodic cleanup of completed experiments |
 | llama-throughput-lab | Benchmark results | T2 | 30 days | File cleanup cron |

### 3.6 Remaining Services (NATS, Workers, UI, Invidious, Infra)

All remaining services default to **T0 (1 hour)** for transient data and **T5 (14 days)** for logs. No PII is expected in these services. Full mapping in `docs/service-hardening-inventory.md`.

---

## 4. Outbound Data Flow Controls

### 4.1 Hostinger API (via Agent Zero :5081)

| Concern | Control |
---------|--------|
| API requests may contain PII in deployment payloads | **Never embed user data in website deployments**. Website content must be generated content only — no session data, no user identifiers, no chat history. |
| Hostinger infrastructure logs all API calls | Minimize API call frequency. Batch operations. No user-identifying parameters in DNS/SSL requests. |
| Hostinger is a third-party subject to their ToS | Document: Hostinger's data retention is external to our control. Classify any data sent to Hostinger as **T2 minimum** and assume 90-day retention on their side. |

### 4.2 Messaging Services (Telegram, Discord)

| Concern | Control |
---------|--------|
| Message payloads sent to Telegram/Discord APIs | **Strip all PII before sending**. Notifications must contain only: service name, status, generic description. No user content, no session excerpts, no identifiers. |
| Platform metadata (message IDs, chat IDs) | Store locally for dedup only (T5: 14 days). Never send to third-party analytics. |
| Platform ToS grants them broad data rights | Classify all data sent to messaging platforms as **permanently exposed** — assume no deletion control once transmitted. Minimize what is sent. |

### 4.3 Website Deployment

| Concern | Control |
---------|--------|
| Deployed websites are public | **Zero user data in deployments**. Websites are for generated/published content only. Audit any template or deployment script that references session data, environment variables, or internal identifiers. |
| Cloudflare CDN caches deployed content | Set `Cache-Control` headers appropriately. Use purge API for rapid takedown if accidental PII exposure is detected. |

---

## 5. Deletion Procedures

### 5.1 Automated Deletion (Primary)

```
Cron schedule (run on host or dedicated init container):

# T4 Biometric data — every hour
0 * * * * /opt/pmoves/scripts/delete-biometric-data.sh --max-age=24h

# T3 Media artifacts — daily at 03:00
0 3 * * * /opt/pmoves/scripts/delete-media-artifacts.sh --max-age=7d

# T2 Derived data — daily at 04:00
0 4 * * * /opt/pmoves/scripts/delete-derived-data.sh --max-age=30d

# T1 Session data — every 6 hours
0 */6 * * * /opt/pmoves/scripts/delete-session-data.sh --max-age=24h

# T5 Infrastructure logs — daily at 02:00
0 2 * * * /opt/pmoves/scripts/rotate-infrastructure-logs.sh --max-age=14d
```

### 5.2 Manual Deletion (Emergency)

```bash
# Purge ALL user data across all stores (break-glass)
/opt/pmoves/scripts/emergency-data-purge.sh --confirm --audit-log

# Purge specific user/session
/opt/pmoves/scripts/delete-user-data.sh --session-id <id> --cascade

# Verify deletion completed
/opt/pmoves/scripts/verify-deletion.sh --session-id <id> --all-stores
```

### 5.3 Verification

After any deletion operation, verify across all stores:

| Store | Verification Method |
-------|-------------------|
| Supabase (PostgreSQL) | `SELECT COUNT(*) FROM sessions WHERE updated_at < now() - interval '24 hours'` — expect 0 (sessions older than the 24h policy window must be purged) |
| Qdrant | `scroll` collection with filter `created_at < threshold` — expect 0 results |
| Neo4j | `MATCH (n) WHERE n.created_at < datetime() - duration({days: 30}) RETURN count(n)` — expect 0 |
| MinIO | `mc ls --recursive minio/bucket/ --older-than 7d` — expect 0 |
| Agent Zero memory | Verify FAISS index does not contain deleted session IDs |

---

## 6. Exemptions

| Exemption | Approval Required | Max Duration | Audit |
-----------|-------------------|--------------|-------|
 | Legal hold (litigation/subpoena) | Written legal counsel approval | Duration of hold + 30 days | Log exemption with case reference |
 | Security incident investigation | Security lead approval | 14 days | Log with incident ID |
 | Model training dataset (anonymized) | CTO approval | Project duration | Must pass anonymization verification before retention extension |

No exemption applies to T4 (biometric) data — biometric data is **always** deleted within 24 hours regardless of exemption status.

---

## 7. Compliance Verification

- **Automated**: Deletion scripts log every action to `/var/log/pmoves/data-deletion-audit.log` (T5: 14 day retention on audit logs themselves)
- **Periodic**: Monthly automated sweep — run `verify-deletion.sh --all-stores --report` and alert on any data exceeding TTL
- **On-demand**: Security audit can trigger full verification via `/opt/pmoves/scripts/compliance-report.sh`

---

## 8. Related Documents

- Biometric Data Handling Policy: `docs/biometric-data-handling-policy.md`
- Service Hardening Inventory: `docs/service-hardening-inventory.md`
- Phase 1 Security Hardening Index: `docs/phase1-security-hardening-index.md`
- Phase 2 Security Hardening Plan: `docs/phase2-security-hardening-plan.md`
- Hardening Tracker: `docs/hardening/PMOVES-hardening-tracker.md`

---

## Appendix A: Implementation Status

| Item | Status | Target Date |
------|--------|-------------|
 | Deletion scripts (§5.1) | 🔨 TODO | 2026-05-02 |
 | Supabase TTL columns | 🔨 TODO | 2026-05-02 |
 | MinIO lifecycle policies | 🔨 TODO | 2026-05-02 |
 | Qdrant collection TTL config | 🔨 TODO | 2026-05-02 |
 | Neo4j periodic deletion cron | 🔨 TODO | 2026-05-05 |
 | Agent Zero memory rotation validation | 🔨 TODO | 2026-05-05 |
 | TensorZero prompt logging disabled | ⚠️ VERIFY | 2026-04-28 |
 | Ollama prompt logging verification | ⚠️ VERIFY | 2026-04-28 |
 | Hostinger API PII audit | 🔨 TODO | 2026-05-09 |
 | Messaging payload PII strip | 🔨 TODO | 2026-05-09 |
 | Emergency purge script | 🔨 TODO | 2026-05-05 |
