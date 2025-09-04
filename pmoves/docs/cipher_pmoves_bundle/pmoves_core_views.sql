CREATE OR REPLACE VIEW pmoves_core.session_last_message AS
SELECT DISTINCT ON (m.session_id)
  m.session_id,
  m.id AS message_id,
  m.role,
  LEFT(m.content, 400) AS content_preview,
  m.created_at
FROM pmoves_core.messages m
ORDER BY m.session_id, m.created_at DESC;
CREATE OR REPLACE VIEW pmoves_core.memory_latest AS
SELECT id, session_id, kind, LEFT(content, 800) AS content_preview, updated_at, metadata
FROM pmoves_core.memory
ORDER BY updated_at DESC;
CREATE OR REPLACE VIEW pmoves_core.embeddings_latest AS
SELECT id, object_type, object_id, LEFT(content, 400) AS content_preview, created_at
FROM pmoves_core.embeddings
ORDER BY created_at DESC;
CREATE OR REPLACE VIEW pmoves_core.message_embeddings AS
SELECT e.id AS embedding_id, m.id AS message_id, m.session_id, m.role, LEFT(m.content, 800) AS message_preview, e.created_at AS embedded_at
FROM pmoves_core.embeddings e
JOIN pmoves_core.messages m
  ON e.object_type='message' AND e.object_id=m.id
ORDER BY e.created_at DESC;
CREATE OR REPLACE VIEW pmoves_core.memory_embeddings AS
SELECT e.id AS embedding_id, mem.id AS memory_id, mem.session_id, mem.kind, LEFT(mem.content, 800) AS memory_preview, e.created_at AS embedded_at
FROM pmoves_core.embeddings e
JOIN pmoves_core.memory mem
  ON e.object_type='memory' AND e.object_id=mem.id
ORDER BY e.created_at DESC;
CREATE OR REPLACE FUNCTION pmoves_core.embed_search_l2(
  query_vec vector,
  k integer DEFAULT 10,
  probes integer DEFAULT 10
)
RETURNS TABLE (
  id bigint,
  object_type text,
  object_id uuid,
  content text,
  distance real,
  created_at timestamptz,
  metadata jsonb
)
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM set_config('ivfflat.probes', probes::text, true);
  RETURN QUERY
  SELECT e.id, e.object_type, e.object_id, e.content,
         (e.embedding <-> query_vec)::real AS distance, e.created_at, e.metadata
  FROM pmoves_core.embeddings e
  ORDER BY e.embedding <-> query_vec
  LIMIT k;
END;
$$;
CREATE OR REPLACE FUNCTION pmoves_core.upsert_embedding(
  p_object_type text,
  p_object_id uuid,
  p_content text,
  p_embedding vector,
  p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE new_id bigint;
BEGIN
  DELETE FROM pmoves_core.embeddings
   WHERE object_type=p_object_type AND object_id=p_object_id;
  INSERT INTO pmoves_core.embeddings (object_type, object_id, content, embedding, metadata)
  VALUES (p_object_type, p_object_id, p_content, p_embedding, p_metadata)
  RETURNING id INTO new_id;
  RETURN new_id;
END;
$$;