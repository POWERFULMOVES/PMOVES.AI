-- PMOVES-BoTZ Work Items - Initial Seed Data
-- Seeds work items for all integrations based on Phase 8 backlog

-- PMOVES-Crush Work Items (C1-C8)
INSERT INTO integration_work_items (integration_name, title, description, priority, status, required_skill_level, estimated_complexity, files_to_modify, files_to_create, acceptance_criteria) VALUES
(
    'pmoves-crush',
    'C1: Fork upstream Charm Crush repository',
    'Fork the upstream Charm Bracelet Crush repository to POWERFULMOVES organization. This establishes our PMOVES-branded version.',
    'p1_high',
    'ready',
    'basic',
    'trivial',
    '[]',
    '[]',
    '["Fork exists at github.com/POWERFULMOVES/PMOVES-crush", "All upstream history preserved"]'
),
(
    'pmoves-crush',
    'C2: Create PMOVES.AI-Edition-Hardened branch',
    'Create the standard hardened branch following PMOVES submodule conventions.',
    'p1_high',
    'ready',
    'basic',
    'trivial',
    '[]',
    '[]',
    '["Branch PMOVES.AI-Edition-Hardened exists", "Branch is set as default", "Branch protection rules applied"]'
),
(
    'pmoves-crush',
    'C3: Rename binary to pmoves-crush',
    'Modify .goreleaser.yml to build the binary as pmoves-crush instead of crush.',
    'p1_high',
    'ready',
    'basic',
    'small',
    '["PMOVES-crush/.goreleaser.yml"]',
    '[]',
    '["Binary builds as pmoves-crush", "All platforms (linux, darwin, windows) produce pmoves-crush binary", "Goreleaser workflow succeeds"]'
),
(
    'pmoves-crush',
    'C4: Update attribution strings for PMOVES branding',
    'Modify source code to use PMOVES attribution strings in git commits.',
    'p2_medium',
    'ready',
    'basic',
    'small',
    '["PMOVES-crush/internal/git/commit.go"]',
    '[]',
    '["Commits show Generated with PMOVES-Crush", "Co-author shows PMOVES Agent when enabled", "Attribution configurable via crush.json"]'
),
(
    'pmoves-crush',
    'C5: Add PMOVES system prompts',
    'Create PMOVES-specific system prompts with context about the PMOVES.AI ecosystem.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '["PMOVES-crush/internal/agent/prompts/system.md"]',
    '["PMOVES-crush/internal/agent/prompts/pmoves-context.md"]',
    '["System prompt mentions PMOVES.AI ecosystem", "Context prompt describes available services", "Prompts are loaded when PMOVES mode enabled"]'
),
(
    'pmoves-crush',
    'C6: Integrate TensorZero as default provider',
    'Configure TensorZero as the default LLM provider for PMOVES-Crush.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '["pmoves/tools/crush_configurator.py"]',
    '[]',
    '["TensorZero is first in provider priority", "Default endpoint is http://tensorzero:3030", "Fallback providers configured"]'
),
(
    'pmoves-crush',
    'C7: Add MCP tool integration for PMOVES services',
    'Enable MCP tools for interacting with Agent Zero, Hi-RAG, and other PMOVES services.',
    'p2_medium',
    'ready',
    'mcp_augmented',
    'large',
    '[]',
    '["PMOVES-crush/internal/mcp/pmoves_tools.go"]',
    '["MCP tool for Hi-RAG queries", "MCP tool for Agent Zero commands", "MCP tool for NATS publish", "Tools documented in crush --help"]'
),
(
    'pmoves-crush',
    'C8: Build and publish to GHCR',
    'Set up GitHub Actions workflow to build and publish pmoves-crush to GitHub Container Registry.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '[]',
    '["PMOVES-crush/.github/workflows/release.yml"]',
    '["Workflow triggers on tag push", "Multi-arch builds (amd64, arm64)", "Published to ghcr.io/powerfulmoves/pmoves-crush", "Release notes generated"]'
);

-- Jellyfin Integration Work Items (J1-J3)
INSERT INTO integration_work_items (integration_name, title, description, priority, status, required_skill_level, estimated_complexity, files_to_modify, files_to_create, acceptance_criteria) VALUES
(
    'jellyfin',
    'J1: Create Jellyfin bridge API client',
    'Implement a Python client for the Jellyfin API to enable media metadata synchronization.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '["pmoves/services/jellyfin-bridge/main.py"]',
    '["pmoves/services/jellyfin-bridge/jellyfin_client.py"]',
    '["Client can authenticate with Jellyfin", "Can fetch library items", "Can get item metadata", "Error handling for connection issues"]'
),
(
    'jellyfin',
    'J2: Implement media processing pipeline integration',
    'Connect Jellyfin to the PMOVES.YT/FFmpeg-Whisper pipeline for automatic transcription.',
    'p2_medium',
    'ready',
    'mcp_augmented',
    'large',
    '["pmoves/services/jellyfin-bridge/main.py"]',
    '[]',
    '["New media items trigger transcription", "Transcripts stored with Jellyfin item ID", "Progress published to NATS", "Hi-RAG indexed on completion"]'
),
(
    'jellyfin',
    'J3: Add NATS event publishing for Jellyfin events',
    'Publish Jellyfin events (playback, library updates) to NATS for ecosystem integration.',
    'p3_low',
    'ready',
    'tac_enabled',
    'small',
    '["pmoves/services/jellyfin-bridge/main.py"]',
    '[]',
    '["Events published to jellyfin.*.v1 subjects", "Playback events include user/item info", "Library events include item metadata"]'
);

-- Firefly III Integration Work Items (F1-F3)
INSERT INTO integration_work_items (integration_name, title, description, priority, status, required_skill_level, estimated_complexity, files_to_modify, files_to_create, acceptance_criteria) VALUES
(
    'firefly',
    'F1: Implement OAuth flow for Firefly III',
    'Replace manual token generation with proper OAuth authentication flow.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '["pmoves/scripts/integration-auth-setup.sh"]',
    '["pmoves/services/firefly-integration/oauth.py"]',
    '["OAuth flow works via CLI", "Tokens stored securely", "Refresh token handling", "Documented in integration guide"]'
),
(
    'firefly',
    'F2: Create bank import automation',
    'Automate bank statement import from supported banks/formats.',
    'p3_low',
    'ready',
    'mcp_augmented',
    'large',
    '[]',
    '["pmoves/services/firefly-integration/import_worker.py"]',
    '["Supports CSV import", "Supports OFX format", "Duplicate detection", "Categorization suggestions"]'
),
(
    'firefly',
    'F3: Build wealth dashboard integration',
    'Create dashboard widgets showing Firefly data in PMOVES monitoring.',
    'p3_low',
    'ready',
    'tac_enabled',
    'medium',
    '[]',
    '["pmoves/grafana/dashboards/wealth-overview.json"]',
    '["Dashboard shows account balances", "Transaction trends visible", "Budget progress displayed", "Refreshes automatically"]'
);

-- wger Integration Work Items (W1-W2)
INSERT INTO integration_work_items (integration_name, title, description, priority, status, required_skill_level, estimated_complexity, files_to_modify, files_to_create, acceptance_criteria) VALUES
(
    'wger',
    'W1: Implement Supabase sync for wger data',
    'Sync wger workout and nutrition data to Supabase for unified querying.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '[]',
    '["pmoves/services/wger-sync/main.py", "pmoves/supabase/migrations/wger_sync.sql"]',
    '["Workouts synced to Supabase", "Nutrition logs synced", "Incremental sync support", "Conflict resolution handled"]'
),
(
    'wger',
    'W2: Index health metrics in Hi-RAG',
    'Enable semantic search over workout and nutrition data via Hi-RAG.',
    'p3_low',
    'ready',
    'mcp_augmented',
    'medium',
    '["pmoves/services/wger-sync/main.py"]',
    '[]',
    '["Workout descriptions indexed", "Nutrition notes searchable", "Temporal queries work", "Results include metadata"]'
);

-- Open Notebook Integration Work Items (O1-O2)
INSERT INTO integration_work_items (integration_name, title, description, priority, status, required_skill_level, estimated_complexity, files_to_modify, files_to_create, acceptance_criteria) VALUES
(
    'open-notebook',
    'O1: Implement notebook sync service',
    'Create bi-directional sync between Open Notebook and Hi-RAG.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'medium',
    '["pmoves/services/notebook-sync/main.py"]',
    '[]',
    '["Notes sync to Hi-RAG", "Hi-RAG results can create notes", "Sync status tracked", "Conflict detection"]'
),
(
    'open-notebook',
    'O2: Enable Hi-RAG bi-directional integration',
    'Allow Hi-RAG search results to be saved as Open Notebook notes.',
    'p3_low',
    'ready',
    'mcp_augmented',
    'medium',
    '["pmoves/services/hirag-gateway/main.py"]',
    '[]',
    '["Save to notebook endpoint exists", "Note includes search context", "Backlinks created", "Tags from query preserved"]'
);

-- BoTZ Ecosystem Work Items
INSERT INTO integration_work_items (integration_name, title, description, priority, status, required_skill_level, estimated_complexity, files_to_modify, files_to_create, acceptance_criteria) VALUES
(
    'botz-gateway',
    'B1: Implement skill tree progression system',
    'Create the skill tree upgrade mechanism for BoTZ instances.',
    'p2_medium',
    'ready',
    'tac_enabled',
    'large',
    '["pmoves/services/botz-gateway/main.py", "pmoves/supabase/migrations/2025-12-08_botz_work_items.sql"]',
    '[]',
    '["Skill points accumulated on completion", "Level up triggers at thresholds", "New capabilities unlocked", "NATS event on level up"]'
),
(
    'botz-gateway',
    'B2: Add TensorZero integration for BoTZ LLM calls',
    'Route BoTZ LLM requests through TensorZero for unified observability.',
    'p2_medium',
    'ready',
    'mcp_augmented',
    'medium',
    '["pmoves/services/botz-gateway/main.py"]',
    '[]',
    '["LLM calls go through TensorZero", "Token usage tracked per BoTZ", "Model selection per skill level", "Metrics visible in ClickHouse"]'
),
(
    'botz-gateway',
    'B3: Create BoTZ coordination dashboard',
    'Build Grafana dashboard for BoTZ ecosystem monitoring.',
    'p3_low',
    'ready',
    'tac_enabled',
    'medium',
    '[]',
    '["pmoves/grafana/dashboards/botz-ecosystem.json"]',
    '["Active BoTZ count shown", "Work items by status", "Completion rate trends", "Skill level distribution"]'
);

-- Add comments
COMMENT ON TABLE integration_work_items IS 'Seeded with initial Phase 8 backlog items for PMOVES integrations';
