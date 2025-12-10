-- Enable Realtime for chat_messages table
-- Phase 9: Ingestion Control & Agent Chat

-- Add session and agent tracking columns for multi-agent conversations
ALTER TABLE public.chat_messages
  ADD COLUMN IF NOT EXISTS session_id uuid,
  ADD COLUMN IF NOT EXISTS agent_id text,
  ADD COLUMN IF NOT EXISTS message_type text DEFAULT 'text', -- 'text', 'action', 'system', 'approval'
  ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb;

-- Index for efficient session-based queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_session
  ON public.chat_messages(session_id, created_at DESC);

-- Index for agent-based queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_agent
  ON public.chat_messages(agent_id, created_at DESC);

-- Enable Realtime for chat_messages
-- Check if table is already in publication before adding
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
    AND schemaname = 'public'
    AND tablename = 'chat_messages'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.chat_messages;
  END IF;
END $$;

-- Add RLS policy for session-based access
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename = 'chat_messages'
    AND policyname = 'chat_session_read'
  ) THEN
    CREATE POLICY chat_session_read ON public.chat_messages
      FOR SELECT USING (
        auth.role() = 'service_role'
        OR auth.uid() = owner_id
        OR session_id IN (
          SELECT session_id FROM public.claude_sessions
          WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- Function to get recent chat history for a session
CREATE OR REPLACE FUNCTION get_chat_history(
  p_session_id uuid,
  p_limit int DEFAULT 50,
  p_offset int DEFAULT 0
) RETURNS TABLE (
  id bigint,
  role text,
  agent text,
  agent_id text,
  content text,
  message_type text,
  metadata jsonb,
  created_at timestamptz
) LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT
    id, role, agent, agent_id, content, message_type, metadata, created_at
  FROM public.chat_messages
  WHERE session_id = p_session_id
  ORDER BY created_at DESC
  LIMIT p_limit
  OFFSET p_offset;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION get_chat_history TO authenticated;
GRANT EXECUTE ON FUNCTION get_chat_history TO service_role;

COMMENT ON TABLE public.chat_messages IS 'Realtime-enabled chat messages for agent conversations';
