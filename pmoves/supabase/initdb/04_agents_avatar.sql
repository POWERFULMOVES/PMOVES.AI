-- Expose agents with avatar_url for UI and assign operations
alter table if exists pmoves_core.agent
  add column if not exists avatar_url text;

-- NOTE: RLS policies for pmoves_core.agent are defined in 00_pmoves_schema.sql
-- (C-02 hardening). This file only adds the avatar_url column.
-- Any permissive anon policies from prior versions are dropped there.
