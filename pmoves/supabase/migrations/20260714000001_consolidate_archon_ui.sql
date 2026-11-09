-- Migration: consolidate_archon_ui
-- The archon-ui service has been merged into archon (single container).
-- Update the archon catalog row to include UI tags/metadata.
-- Remove the standalone archon-ui row.

UPDATE pmoves_core.service_catalog
SET tags = '{"agent": true, "supabase": true, "prompts": true, "ui": true}'::jsonb,
    metadata = '{"mcp_port": 8051, "agents_port": 8052, "ui_port": 3737}'::jsonb
WHERE slug = 'archon';

DELETE FROM pmoves_core.service_catalog WHERE slug = 'archon-ui';
