-- Work Orders Schema Compatibility Layer
-- Migration: 2025-12-11_work_orders_schema_compatibility.sql
-- Purpose: Add backward-compatible views and aliases for test compatibility
--          while maintaining production schema integrity
--
-- This migration provides:
-- 1. View aliases with test-expected naming (archon_work_orders_active, archon_work_orders_with_steps)
-- 2. Backward compatibility without breaking existing Archon service

-- ============================================================================
-- View Alias: archon_work_orders_active
-- Purpose: Alias for archon_active_work_orders (test compatibility)
-- ============================================================================

CREATE OR REPLACE VIEW archon_work_orders_active AS
SELECT * FROM archon_active_work_orders;

COMMENT ON VIEW archon_work_orders_active IS
    'Backward-compatible alias for archon_active_work_orders view';

-- ============================================================================
-- View: archon_work_orders_with_steps
-- Purpose: Work orders with their associated steps (test requirement)
-- ============================================================================

CREATE OR REPLACE VIEW archon_work_orders_with_steps AS
SELECT
    wo.agent_work_order_id,
    wo.repository_url,
    wo.sandbox_identifier,
    wo.sandbox_type,
    wo.git_branch_name,
    wo.status,
    wo.current_phase,
    wo.user_request,
    wo.github_pull_request_url,
    wo.git_commit_count,
    wo.git_files_changed,
    wo.created_at,
    wo.updated_at,
    json_agg(
        json_build_object(
            'id', s.id,
            'step', s.step,
            'agent_name', s.agent_name,
            'success', s.success,
            'output', s.output,
            'error_message', s.error_message,
            'duration_seconds', s.duration_seconds,
            'timestamp', s.timestamp
        ) ORDER BY s.timestamp
    ) FILTER (WHERE s.id IS NOT NULL) AS steps,
    count(s.id) AS step_count,
    count(s.id) FILTER (WHERE s.success = true) AS successful_steps,
    count(s.id) FILTER (WHERE s.success = false) AS failed_steps
FROM archon_agent_work_orders wo
LEFT JOIN archon_agent_work_order_steps s ON s.agent_work_order_id = wo.agent_work_order_id
GROUP BY wo.agent_work_order_id
ORDER BY wo.created_at DESC;

COMMENT ON VIEW archon_work_orders_with_steps IS
    'Work orders with aggregated step information for comprehensive overview';

-- ============================================================================
-- Row Level Security for new views
-- ============================================================================

-- Note: Views inherit RLS policies from underlying tables
-- But we explicitly grant access for clarity

-- Grant SELECT to service_role (full access)
GRANT SELECT ON archon_work_orders_active TO service_role;
GRANT SELECT ON archon_work_orders_with_steps TO service_role;

-- Grant SELECT to authenticated users (read-only)
GRANT SELECT ON archon_work_orders_active TO authenticated;
GRANT SELECT ON archon_work_orders_with_steps TO authenticated;

-- Grant SELECT to anon (public read for specific use cases)
GRANT SELECT ON archon_work_orders_active TO anon;
GRANT SELECT ON archon_work_orders_with_steps TO anon;
