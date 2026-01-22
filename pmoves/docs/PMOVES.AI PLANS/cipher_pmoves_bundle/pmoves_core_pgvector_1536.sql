CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE SCHEMA IF NOT EXISTS pmoves_core;
CREATE TABLE IF NOT EXISTS pmoves_core.sessions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id TEXT,
  title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON pmoves_core.sessions (user_id);
CREATE INDEX IF NOT EXISTS sessions_updated_at ON pmoves_core.sessions (updated_at DESC);
CREATE TABLE IF NOT EXISTS pmoves_core.messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES pmoves_core.sessions(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('system','user','assistant','tool')),
  content TEXT NOT NULL,
  tool_name TEXT,
  tool_args JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS messages_session_time_idx ON pmoves_core.messages (session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS messages_gin_meta_idx ON pmoves_core.messages USING GIN (metadata);
CREATE TABLE IF NOT EXISTS pmoves_core.memory (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID REFERENCES pmoves_core.sessions(id) ON DELETE SET NULL,
  kind TEXT,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS memory_kind_idx ON pmoves_core.memory (kind);
CREATE INDEX IF NOT EXISTS memory_session_idx ON pmoves_core.memory (session_id);
CREATE INDEX IF NOT EXISTS memory_updated_at_idx ON pmoves_core.memory (updated_at DESC);
CREATE INDEX IF NOT EXISTS memory_gin_meta_idx ON pmoves_core.memory USING GIN (metadata);
CREATE TABLE IF NOT EXISTS pmoves_core.embeddings (
  id BIGSERIAL PRIMARY KEY,
  object_type TEXT NOT NULL,
  object_id UUID,
  content TEXT,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS embeddings_ivfflat_l2_idx
ON pmoves_core.embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 200);
CREATE INDEX IF NOT EXISTS embeddings_object_idx ON pmoves_core.embeddings (object_type, object_id);
CREATE INDEX IF NOT EXISTS embeddings_created_idx ON pmoves_core.embeddings (created_at DESC);
CREATE INDEX IF NOT EXISTS embeddings_gin_meta_idx ON pmoves_core.embeddings USING GIN (metadata);
CREATE TABLE IF NOT EXISTS pmoves_core.event_log (
  id BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,
  actor_id TEXT,
  payload JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS event_log_type_time_idx ON pmoves_core.event_log (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS event_log_gin_payload ON pmoves_core.event_log USING GIN (payload);