-- Voice Messages (n8n voice agents)
-- Creates public.voice_messages for logging voice agent interactions.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.voice_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  platform text NOT NULL,
  user_id text NOT NULL,
  user_name text,
  transcript text,
  response_text text,
  model_used text,
  status text NOT NULL DEFAULT 'completed',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_voice_messages_created_at
  ON public.voice_messages(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_voice_messages_platform
  ON public.voice_messages(platform);

CREATE INDEX IF NOT EXISTS idx_voice_messages_user_id
  ON public.voice_messages(user_id);

ALTER TABLE public.voice_messages ENABLE ROW LEVEL SECURITY;

-- service_role has full access (n8n uses the service role key for inserts)
DROP POLICY IF EXISTS voice_messages_service_role ON public.voice_messages;
CREATE POLICY voice_messages_service_role
  ON public.voice_messages
  FOR ALL
  TO service_role
  USING (current_role = 'service_role')
  WITH CHECK (current_role = 'service_role');

COMMENT ON TABLE public.voice_messages IS 'Voice agent interaction logs (platform, transcript, response, metadata)';
