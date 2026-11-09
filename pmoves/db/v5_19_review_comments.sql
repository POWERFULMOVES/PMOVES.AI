-- v5_19 Review Comment Archive — retro learning for agents and operators.
-- Collects GitHub PR review comments (CodeRabbit, Codex, Claude, human) into
-- Supabase for analysis on the SPARK node. Actionable items are surfaced
-- automatically; patterns become retro learning for future agents.

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.review_comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- GitHub source
    repo            TEXT NOT NULL,                    -- e.g. "PMOVES.AI" or "Pmoves-cipher"
    pr_number       INTEGER NOT NULL,
    comment_id      BIGIGNINT,                        -- GitHub REST API comment ID
    -- Comment metadata
    author          TEXT NOT NULL,                    -- e.g. "chatgpt-codex-connector", "coderabbitai", "darkxside"
    author_type     TEXT NOT NULL DEFAULT 'bot',      -- bot|human|agent
    path            TEXT,                             -- file path the comment is on
    line            INTEGER,                         -- line number
    severity        TEXT,                             -- P1|P2|P3|nitpick|praise|question
    body            TEXT NOT NULL,                    -- full comment text
    -- Classification (filled by retro-learning pipeline)
    category        TEXT,                             -- missed-signal|fix-pattern|wrong-suggestion|already-addressed|security|style|contract
    is_actionable   BOOLEAN,                          -- true = needs a code change
    is_resolved     BOOLEAN NOT NULL DEFAULT false,
    resolution      TEXT,                             -- fixed|wontfix|duplicate|stale
    fix_commit      TEXT,                             -- SHA of the commit that addressed it
    -- Retro learning (filled by SPARK analysis)
    learning        TEXT,                             -- one-line takeaway for future agents
    pattern_key     TEXT,                             -- dedup key for recurring patterns
    -- Audit
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Constraints
    CONSTRAINT rc_severity_chk CHECK (severity IS NULL OR severity IN
        ('P1', 'P2', 'P3', 'nitpick', 'praise', 'question')),
    CONSTRAINT rc_author_type_chk CHECK (author_type IN ('bot', 'human', 'agent')),
    CONSTRAINT rc_resolution_chk CHECK (resolution IS NULL OR resolution IN
        ('fixed', 'wontfix', 'duplicate', 'stale'))
);

CREATE INDEX IF NOT EXISTS rc_repo_pr_idx     ON pmoves_core.review_comments (repo, pr_number);
CREATE INDEX IF NOT EXISTS rc_actionable_idx  ON pmoves_core.review_comments (is_actionable) WHERE is_actionable AND NOT is_resolved;
CREATE INDEX IF NOT EXISTS rc_pattern_idx     ON pmoves_core.review_comments (pattern_key) WHERE pattern_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS rc_severity_idx    ON pmoves_core.review_comments (severity) WHERE severity IS NOT NULL;

-- Row Level Security
ALTER TABLE pmoves_core.review_comments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rc_service_bypass ON pmoves_core.review_comments;
CREATE POLICY rc_service_bypass ON pmoves_core.review_comments
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Authenticated users can read (operators reviewing retro learning)
DROP POLICY IF EXISTS rc_read ON pmoves_core.review_comments;
CREATE POLICY rc_read ON pmoves_core.review_comments
    FOR SELECT TO authenticated USING (true);

-- Only service role can write (collector script uses service key)
DROP POLICY IF EXISTS rc_service_write ON pmoves_core.review_comments;
CREATE POLICY rc_service_write ON pmoves_core.review_comments
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DO $$
BEGIN
    EXECUTE 'GRANT USAGE ON SCHEMA pmoves_core TO anon, authenticated, service_role';
    EXECUTE 'GRANT SELECT ON pmoves_core.review_comments TO authenticated, service_role';
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.review_comments TO service_role';
END $$;

COMMENT ON TABLE pmoves_core.review_comments IS
    'Review comment archive for retro learning. Collects PR review comments from CodeRabbit, Codex, Claude, and human reviewers. SPARK node analyzes patterns and surfaces actionable items. See fleet-fork-sync skill and review collection pipeline.';
