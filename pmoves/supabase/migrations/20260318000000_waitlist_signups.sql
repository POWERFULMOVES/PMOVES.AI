-- Waitlist signups table for PMOVES.AI landing page
-- Collects email + tier interest from public signup form
-- RLS: anon can INSERT, only service_role can SELECT

CREATE TABLE IF NOT EXISTS public.waitlist_signups (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text NOT NULL UNIQUE,
  tier_interest text DEFAULT 'community'
    CHECK (tier_interest IN ('community', 'creator', 'pro', 'studio', 'enterprise', 'developer')),
  source text DEFAULT 'landing',
  created_at timestamptz DEFAULT now()
);

COMMENT ON TABLE public.waitlist_signups IS 'PMOVES.AI waitlist email collection';

ALTER TABLE public.waitlist_signups ENABLE ROW LEVEL SECURITY;

-- Anon users (public form) can only insert
CREATE POLICY "anon_insert_waitlist"
  ON public.waitlist_signups
  FOR INSERT
  TO anon
  WITH CHECK (true);

-- Only service_role can read signups (admin/dashboard)
CREATE POLICY "service_read_waitlist"
  ON public.waitlist_signups
  FOR SELECT
  TO service_role
  USING (true);
