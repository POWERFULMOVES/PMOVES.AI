# Distributed Supabase Architecture for PMOVES.AI

**Status:** 🏗️ **Architecture Design**

**Date:** 2026-02-07

---

## Overview

PMOVES.AI implements a **distributed Supabase architecture** that supports:

1. **Standalone Mode** - Service runs with its own Supabase instance
2. **Integrated Mode** - Service connects to PMOVES central Supabase
3. **Dual-Write Mode** - Service has local Supabase + syncs to central

---

## Architecture Diagrams

### Standalone Mode (Service-Specific Supabase)

```
┌─────────────────────────────────────────────────────────────┐
│  Service (e.g., GPU Orchestrator on Jetson)                 │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Application Layer                                  │    │
│  │  - Business Logic                                   │    │
│  │  - Service-specific features                        │    │
│  └───────────────────┬─────────────────────────────────┘    │
│                      │                                       │
│  ┌───────────────────▼─────────────────────────────────┐    │
│  │  Local Supabase (Docker sidecar)                   │    │
│  │  ┌──────────────┐  ┌──────────────┐                │    │
│  │  │ PostgreSQL   │  │  GoTrue      │                │    │
│  │  │  (Local DB)  │  │  (Local Auth)│                │    │
│  │  └──────────────┘  └──────────────┘                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Advantages:                                                 │
│  - No network dependency on central                         │
│  - Fast local access                                        │
│  - Works offline                                            │
└─────────────────────────────────────────────────────────────┘
```

### Integrated Mode (Central Supabase)

```
┌──────────────────────────────────────────────────────────────────┐
│                     PMOVES Central Infrastructure                 │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PMOVES Central Supabase                                 │   │
│  │  ┌─────────────────────────────────────────────────┐     │   │
│  │  │  PostgreSQL Cluster                              │     │   │
│  │  │  - Users & Authentication                       │     │   │
│  │  │  - Shared Configuration                         │     │   │
│  │  │  - Cross-Service Data                           │     │   │
│  │  │  - Audit Logs                                    │     │   │
│  │  └─────────────────────────────────────────────────┘     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │  GoTrue      │  │  PostgREST   │  │  Realtime    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
▲                      ▲                    ▲                      │
│                      │                    │                      │
│  ┌───────────────┐   │   ┌───────────────┐   │   ┌───────────────┐
│  │  Archon       │   │   │  Agent Zero   │   │   │  TensorZero   │
│  │  (Supabase    │   │   │  (Supabase    │   │   │  (Supabase    │
│  │   Client)     │   │   │   Client)     │   │   │   Client)     │
│  └───────────────┘   │   └───────────────┘   │   └───────────────┘
│                      │                      │                      │
└──────────────────────┼──────────────────────┼──────────────────────┘
                       │                      │
                 NATS Message Bus         (Mesh Network)
```

### Dual-Write Mode (Sync Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Service (e.g., GPU Orchestrator)                                   │
│                                                                      │
│  Application                                                         │
│     │                                                                │
│     ├─► Local Supabase (Primary Write) ──┐                          │
│     │                                    │                          │
│     └─► Sync Worker ─────────────────────┼──► PMOVES Central Supabase│
│                                          │     (Read Replica)        │
│  ┌───────────────────────────────────────┼───────────────────────┐  │
│  │  Sync Queue (for offline scenarios)  │                       │  │
│  │  - Pending writes                    │                       │  │
│  │  - Conflict resolution               │                       │  │
│  │  - Retry logic                        │                       │  │
│  └───────────────────────────────────────┴───────────────────────┘  │
│                                                                      │
│  Data Flow:                                                          │
│  1. Write to local Supabase (fast, synchronous)                     │
│  2. Queue sync to central (async, background)                       │
│  3. Sync worker processes queue                                      │
│  4. Handle conflicts with last-write-wins                           │
│  5. Mark records as synced                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Service-Specific Supabase Configuration

### GPU Orchestrator

**Purpose:** Orchestrate GPU jobs across Jetson devices

**Mode:** Dual-Write

```yaml
# env.service.gpu-orchestrator
SUPABASE_MODE=dual-write

# Local Supabase (Primary)
LOCAL_SUPABASE_URL=http://local-supabase:8000
LOCAL_SUPABASE_ANON_KEY=${LOCAL_ANON_KEY}
LOCAL_SUPABASE_SERVICE_ROLE_KEY=${LOCAL_SERVICE_KEY}

# Central Supabase (Secondary/Sync)
CENTRAL_SUPABASE_URL=https://supabase.pmoves.ai
CENTRAL_SUPABASE_ANON_KEY=${CENTRAL_ANON_KEY}
CENTRAL_SUPABASE_SERVICE_ROLE_KEY=${CENTRAL_SERVICE_KEY}

# Sync Configuration
SYNC_ENABLED=true
SYNC_STRATEGY=write-through
SYNC_TABLES=jobs,results,metrics,workers
SYNC_BATCH_SIZE=100
SYNC_INTERVAL_SECONDS=30
CONFLICT_RESOLUTION=last-write-wins
```

**Local Schema:**
```sql
-- Local tables (primary write)
CREATE TABLE jobs (
    id uuid primary key default gen_random_uuid(),
    worker_id uuid not null,
    status job_status not null,
    created_at timestamp default now(),
    updated_at timestamp default now(),
    -- Local-specific fields
    local_worker_name text,
    local_gpu_id text,
    _synced boolean default false,
    _synced_at timestamp
);

-- Sync queue
CREATE TABLE sync_queue (
    id uuid primary key default gen_random_uuid(),
    table_name text not null,
    operation text not null, -- INSERT, UPDATE, DELETE
    data jsonb not null,
    retry_count int default 0,
    created_at timestamp default now()
);
```

### TensorZero Gateway

**Purpose:** Centralized LLM gateway with observability

**Mode:** Integrated

```yaml
# env.service.tensorzero
SUPABASE_MODE=integrated

# Central Supabase Only
SUPABASE_URL=http://pmoves-supabase:8000
SUPABASE_ANON_KEY=${CENTRAL_ANON_KEY}
SUPABASE_SERVICE_ROLE_KEY=${CENTRAL_SERVICE_KEY}

# ClickHouse (for metrics - separate from Supabase)
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_DATABASE=tensorzero

# Shared configuration
SHARED_METRICS=true
CENTRAL_LOGGING=true
```

### Agent Zero

**Purpose:** Agent orchestration and coordination

**Mode:** Dual-Write (with intelligent fallback)

```yaml
# env.service.agent-zero
SUPABASE_MODE=dual-write

# Local Supabase (for agent state)
LOCAL_SUPABASE_URL=http://local-supabase:8000
LOCAL_SUPABASE_ANON_KEY=${LOCAL_ANON_KEY}

# Central Supabase (for coordination)
CENTRAL_SUPABASE_URL=http://pmoves-supabase:8000
CENTRAL_SUPABASE_ANON_KEY=${CENTRAL_ANON_KEY}

# Sync with fallback
SYNC_ENABLED=true
SYNC_FALLBACK=queue-and-retry
OFFLINE_MODE=true
```

**Local Schema:**
```sql
-- Agent state (local-primary)
CREATE TABLE agents (
    id uuid primary key,
    name text not null,
    status agent_status not null,
    config jsonb not null,
    _synced boolean default false
);

-- Tasks (sync to central)
CREATE TABLE tasks (
    id uuid primary key,
    agent_id uuid not null,
    status task_status not null,
    input jsonb,
    output jsonb,
    _synced boolean default false,
    _central_task_id uuid  -- Reference to central task
);
```

### Archon

**Purpose:** Supabase-driven agent service with prompt management

**Mode:** Integrated (Central)

```yaml
# env.service.archon
SUPABASE_MODE=integrated

# PMOVES Central Supabase
ARCHON_SUPABASE_BASE_URL=http://pmoves-supabase-postgrest:3000
SUPABASE_ANON_KEY=${CENTRAL_ANON_KEY}
SUPABASE_SERVICE_ROLE_KEY=${CENTRAL_SERVICE_KEY}

# Schema
ARCHON_SCHEMA=archon
```

---

## Sync Implementation

### Dual-Write Worker

```typescript
// sync-worker.ts
interface SyncConfig {
  localSupabase: SupabaseClient;
  centralSupabase: SupabaseClient;
  tables: string[];
  batchSize: number;
  interval: number;
}

class DualWriteWorker {
  private queue: Map<string, any[]> = new Map();

  async enqueue(table: string, data: any) {
    if (!this.queue.has(table)) {
      this.queue.set(table, []);
    }
    this.queue.get(table)!.push(data);
  }

  async process() {
    for (const [table, records] of this.queue.entries()) {
      try {
        await this.syncToCentral(table, records);
        await this.markSynced(table, records);
        this.queue.delete(table);
      } catch (error) {
        console.error(`Sync failed for ${table}:`, error);
        // Keep in queue for retry
      }
    }
  }

  async syncToCentral(table: string, records: any[]) {
    // Batch insert to central
    const { error } = await this.centralSupabase
      .from(table)
      .insert(records.map(r => ({
        ...r,
        _source: this.serviceId,
        _synced_at: new Date().toISOString()
      })));

    if (error) {
      // Check for conflicts
      if (error.code === '23505') { // Unique violation
        await this.resolveConflicts(table, records);
      } else {
        throw error;
      }
    }
  }

  async resolveConflicts(table: string, records: any[]) {
    // Last-write-wins based on updated_at
    for (const record of records) {
      await this.centralSupabase
        .from(table)
        .upsert(record, { onConflict: 'id,updated_at' });
    }
  }

  async markSynced(table: string, records: any[]) {
    const ids = records.map(r => r.id);
    await this.localSupabase
      .from(table)
      .update({ _synced: true, _synced_at: new Date().toISOString() })
      .in('id', ids);
  }

  start() {
    setInterval(() => this.process(), this.interval);
  }
}
```

### NATS-Based Sync

```typescript
// nats-sync.ts
import { connect } from 'nats';

class NATSSyncPublisher {
  private nc: NatConnection;

  async connect(url: string) {
    this.nc = await connect({ servers: url });
  }

  async publishSync(table: string, operation: string, data: any) {
    const subject = `supabase.sync.${table}.${operation}`;
    await this.nc.publish(subject, JSON.stringify({
      source: this.serviceId,
      table,
      operation,
      data,
      timestamp: new Date().toISOString()
    }));
  }
}

class NATSSyncSubscriber {
  async subscribe(table: string, callback: (data: any) => void) {
    const subject = `supabase.sync.${table}.>`;
    const sub = this.nc.subscribe(subject);

    for await (const msg of sub) {
      const data = JSON.parse(msg.data);
      await callback(data);
    }
  }
}
```

---

## Docker Compose Configuration

### Service-Specific Supabase (Sidecar)

```yaml
# docker-compose.service-supabase.yml
services:
  local-supabase:
    <<: *base-service
    image: supabase/postgres:15.8.1.085
    container_name: ${SERVICE_NAME}-supabase-db
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD=${SERVICE_POSTGRES_PASSWORD}
      POSTGRES_DB=${SERVICE_POSTGRES_DB}
    volumes:
      - ${SERVICE_NAME}-supabase-data:/var/lib/postgresql/data
      - ./supabase/initdb:/docker-entrypoint-initdb.d:ro
    networks:
      - pmoves_service
    profiles:
      - standalone
      - dual-write

  ${SERVICE_NAME}-gotrue:
    <<: *base-service
    image: supabase/gotrue:v2.186.0
    container_name: ${SERVICE_NAME}-supabase-auth
    depends_on:
      local-supabase:
        condition: service_healthy
    environment:
      GOTRUE_JWT_SECRET=${SERVICE_JWT_SECRET}
      GOTRUE_JWT_EXP=${SERVICE_JWT_EXP}
      GOTRUE_DB_DATABASE_URL=postgres://postgres:${SERVICE_POSTGRES_PASSWORD}@local-supabase:5432/${SERVICE_POSTGRES_DB}
    networks:
      - pmoves_service
    profiles:
      - standalone
      - dual-write

  ${SERVICE_NAME}-postgrest:
    <<: *base-service
    image: postgrest/postgrest:v14.3
    container_name: ${SERVICE_NAME}-supabase-rest
    depends_on:
      local-supabase:
        condition: service_healthy
    environment:
      PGRST_DB_URI=postgres://postgres:${SERVICE_POSTGRES_PASSWORD}@local-supabase:5432/${SERVICE_POSTGRES_DB}
      PGRST_JWT_SECRET=${SERVICE_JWT_SECRET}
    networks:
      - pmoves_service
    profiles:
      - standalone
      - dual-write

  sync-worker:
    <<: *base-service
    image: ghcr.io/powerfulmoves/pmoves-supabase-sync:latest
    container_name: ${SERVICE_NAME}-sync-worker
    depends_on:
      - local-supabase
    environment:
      LOCAL_SUPABASE_URL=http://local-supabase:8000
      CENTRAL_SUPABASE_URL=${CENTRAL_SUPABASE_URL}
      SYNC_TABLES=${SYNC_TABLES}
      SYNC_INTERVAL=${SYNC_INTERVAL:-30}
      SERVICE_NAME=${SERVICE_NAME}
    networks:
      - pmoves_service
      - pmoves_bus  # For NATS
    profiles:
      - dual-write

volumes:
  ${SERVICE_NAME}-supabase-data:

networks:
  pmoves_service:
    driver: bridge
  pmoves_bus:
    external: true
```

---

## Deployment by Service

### Jetson Orin Deployment

```yaml
# docker-compose.jetson-standalone.yml
services:
  gpu-orchestrator:
    <<: *base-service
    image: ghcr.io/powerfulmoves/pmoves-gpu-orchestrator:latest-arm64
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      # Local Supabase (standalone mode)
      SUPABASE_URL=http://gpu-orchestrator-supabase:8000
      SUPABASE_ANON_KEY=${GPU_ORCHESTRATOR_ANON_KEY}
      # GPU configuration
      CUDA_VISIBLE_DEVICES=0
      TORCH_CUDA_ARCH_LIST="8.7"
    depends_on:
      - gpu-orchestrator-supabase
```

### Central VPS Deployment

```yaml
# docker-compose.vps-central.yml
services:
  # PMOVES Central Supabase
  pmoves-supabase-db:
    <<: *base-service
    image: supabase/postgres:15.8.1.085
    container_name: pmoves-supabase-db
    environment:
      POSTGRES_PASSWORD=${CENTRAL_POSTGRES_PASSWORD}
      POSTGRES_DB=pmoves_central
    volumes:
      - pmoves-supabase-data:/var/lib/postgresql/data
    networks:
      - pmoves_central

  pmoves-supabase-postgrest:
    <<: *base-service
    image: postgrest/postgrest:v14.3
    container_name: pmoves-supabase-postgrest
    environment:
      PGRST_DB_URI=postgres://postgres:${CENTRAL_POSTGRES_PASSWORD}@pmoves-supabase-db:5432/pmoves_central
      PGRST_JWT_SECRET=${CENTRAL_JWT_SECRET}
    networks:
      - pmoves_central
```

---

## Migration Path

### Phase 1: Standalone Setup

1. Each service runs with local Supabase
2. No dependency on central infrastructure
3. Full offline capability

### Phase 2: Add Central Supabase

1. Deploy central Supabase on VPS
2. Configure services for integrated mode
3. Migrate users to central authentication

### Phase 3: Enable Dual-Write

1. Add local Supabase back to services
2. Implement sync workers
3. Configure dual-write mode
4. Enable conflict resolution

### Phase 4: Optimize

1. Fine-tune sync intervals
2. Implement smart conflict resolution
3. Add sync monitoring and alerting
4. Optimize database schemas for sync

---

## Conflict Resolution Strategies

### Last-Write-Wins (Default)

```sql
-- Central table with conflict detection
CREATE TABLE jobs (
    id uuid primary key,
    worker_id uuid not null,
    status job_status not null,
    updated_at timestamp default now(),
    _source text not null,
    _source_updated_at timestamp not null
);

-- Upsert with last-write-wins
INSERT INTO jobs (id, worker_id, status, updated_at, _source, _source_updated_at)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (id)
DO UPDATE SET
    worker_id = EXCLUDED.worker_id,
    status = CASE
        WHEN EXCLUDED._source_updated_at > jobs._source_updated_at
        THEN EXCLUDED.status
        ELSE jobs.status
    END,
    updated_at = GREATEST(EXCLUDED.updated_at, jobs.updated_at),
    _source_updated_at = GREATEST(EXCLUDED._source_updated_at, jobs._source_updated_at);
```

### Custom Business Logic

```sql
-- For tasks, prefer "running" status over others
CREATE TABLE tasks (
    id uuid primary key,
    status task_status not null,
    -- ...
);

-- Custom conflict resolution
INSERT INTO tasks (id, status, ...)
VALUES ($1, $2, ...)
ON CONFLICT (id)
DO UPDATE SET
    status = CASE
        -- Running takes priority over other statuses
        WHEN EXCLUDED.status = 'running' THEN 'running'
        WHEN tasks.status = 'running' THEN 'running'
        -- Otherwise, last-write-wins
        WHEN EXCLUDED.updated_at > tasks.updated_at THEN EXCLUDED.status
        ELSE tasks.status
    END;
```

---

## Monitoring Sync Health

### Sync Status Table

```sql
CREATE TABLE sync_status (
    id uuid primary key default gen_random_uuid(),
    service_name text not null,
    table_name text not null,
    last_sync_at timestamp,
    last_sync_status text,
    pending_records int default 0,
    failed_records int default 0,
    last_error text,
    updated_at timestamp default now()
);

-- Query for sync health
SELECT
    service_name,
    table_name,
    last_sync_at,
    pending_records,
    failed_records,
    CASE
        WHEN last_sync_at < now() - interval '5 minutes' THEN 'stale'
        WHEN failed_records > 100 THEN 'failing'
        WHEN pending_records > 1000 THEN 'lagging'
        ELSE 'healthy'
    END as health_status
FROM sync_status
ORDER BY service_name, table_name;
```

---

## Related Documentation

- `ARCHITECTURE_DISTRIBUTED.md` - Overall distributed architecture
- `SUPABASE_UNIFIED_SETUP.md` - Supabase setup guide
- `PMOVES_SUPABASE_PRODUCTION_PATTERNS.md` - Production patterns
