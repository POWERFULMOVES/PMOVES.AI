-- =============================================================================
-- PMOVES.AI Remote Desktop & VPN Access Schema
-- =============================================================================
-- Run via: psql -h localhost -U postgres -d cataclysm_pmoves -f migrations/001_remote_access.sql
-- Or via Supabase CLI: supabase db push
-- =============================================================================

-- Set search path
SET search_path TO public, pmoves_core;

-- =============================================================================
-- Remote Desktop Sessions Table
-- =============================================================================
-- Tracks all remote desktop sessions for audit and billing
CREATE TABLE IF NOT EXISTS pmoves_core.remote_sessions (
  -- Primary key
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- User reference (links to Supabase auth.users)
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Session identifier (unique per session)
  session_id TEXT NOT NULL UNIQUE,

  -- Target device information
  target_device TEXT NOT NULL,
  target_hostname TEXT,
  target_ip TEXT,

  -- Connection details
  connection_type TEXT NOT NULL CHECK (connection_type IN ('rustdesk', 'vpn', 'direct')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'ended', 'failed')),

  -- Timing
  started_at TIMESTAMPTZ DEFAULT NOW(),
  ended_at TIMESTAMPTZ,
  duration_seconds INTEGER,

  -- Network statistics
  origin_ip TEXT,
  bytes_sent BIGINT DEFAULT 0,
  bytes_received BIGINT DEFAULT 0,

  -- Metadata for extensibility
  metadata JSONB DEFAULT '{}'::jsonb,

  -- Audit timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- VPN Nodes Registry Table
-- =============================================================================
-- Tracks all VPN nodes connected via Headscale
CREATE TABLE IF NOT EXISTS pmoves_core.vpn_nodes (
  -- Primary key
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Headscale node information
  node_id TEXT NOT NULL UNIQUE,  -- Headscale machine ID
  hostname TEXT NOT NULL,

  -- User reference (links to Supabase auth.users)
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,

  -- VPN configuration
  tags TEXT[] DEFAULT ARRAY[]::TEXT[],
  ip_addresses TEXT[] DEFAULT ARRAY[]::TEXT[],

  -- Node status
  last_seen TIMESTAMPTZ,
  is_online BOOLEAN DEFAULT false,

  -- Route advertisement
  routes_advertised TEXT[] DEFAULT ARRAY[]::TEXT[],

  -- Audit timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Remote Access Policies Table (RBAC)
-- =============================================================================
-- Defines policies for remote access authorization
CREATE TABLE IF NOT EXISTS pmoves_core.remote_access_policies (
  -- Primary key
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Policy identification
  name TEXT NOT NULL UNIQUE,
  description TEXT,

  -- Access rules
  user_tags TEXT[] DEFAULT ARRAY[]::TEXT[],      -- Tags required for users
  target_devices TEXT[] DEFAULT ARRAY[]::TEXT[],  -- Devices accessible under this policy

  -- Time-based restrictions
  allowed_hours TIME[] DEFAULT ARRAY[]::TIME[],  -- Hours when access is allowed

  -- Approval workflow
  requires_approval BOOLEAN DEFAULT false,
  auto_approve_tags TEXT[] DEFAULT ARRAY[]::TEXT[],  -- Tags that bypass approval

  -- Policy status
  enabled BOOLEAN DEFAULT true,

  -- Audit timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- VPN Auth Keys Table
-- =============================================================================
-- Tracks VPN authentication keys for audit
CREATE TABLE IF NOT EXISTS pmoves_core.vpn_auth_keys (
  -- Primary key
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Key information
  key_id TEXT NOT NULL UNIQUE,
  key_value TEXT,  -- Encrypted or hashed (optional)

  -- User reference
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  created_by_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,

  -- Key configuration
  tags TEXT[] DEFAULT ARRAY[]::TEXT[],
  ephemeral BOOLEAN DEFAULT false,

  -- Key status
  is_valid BOOLEAN DEFAULT true,
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,

  -- Audit timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- remote_sessions indexes
CREATE INDEX IF NOT EXISTS idx_remote_sessions_user_id ON pmoves_core.remote_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_remote_sessions_status ON pmoves_core.remote_sessions(status);
CREATE INDEX IF NOT EXISTS idx_remote_sessions_started_at ON pmoves_core.remote_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_remote_sessions_target_device ON pmoves_core.remote_sessions(target_device);
CREATE INDEX IF NOT EXISTS idx_remote_sessions_connection_type ON pmoves_core.remote_sessions(connection_type);

-- vpn_nodes indexes
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_node_id ON pmoves_core.vpn_nodes(node_id);
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_hostname ON pmoves_core.vpn_nodes(hostname);
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_is_online ON pmoves_core.vpn_nodes(is_online);
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_user_id ON pmoves_core.vpn_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_tags ON pmoves_core.vpn_nodes USING GIN(tags);

-- remote_access_policies indexes
CREATE INDEX IF NOT EXISTS idx_remote_access_policies_enabled ON pmoves_core.remote_access_policies(enabled);
CREATE INDEX IF NOT EXISTS idx_remote_access_policies_user_tags ON pmoves_core.remote_access_policies USING GIN(user_tags);

-- vpn_auth_keys indexes
CREATE INDEX IF NOT EXISTS idx_vpn_auth_keys_key_id ON pmoves_core.vpn_auth_keys(key_id);
CREATE INDEX IF NOT EXISTS idx_vpn_auth_keys_user_id ON pmoves_core.vpn_auth_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_vpn_auth_keys_is_valid ON pmoves_core.vpn_auth_keys(is_valid);
CREATE INDEX IF NOT EXISTS idx_vpn_auth_keys_expires_at ON pmoves_core.vpn_auth_keys(expires_at);

-- =============================================================================
-- Row Level Security (RLS) Policies
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE pmoves_core.remote_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.vpn_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.remote_access_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.vpn_auth_keys ENABLE ROW LEVEL SECURITY;

-- remote_sessions policies
CREATE POLICY "Users can view own remote sessions"
  ON pmoves_core.remote_sessions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all remote sessions"
  ON pmoves_core.remote_sessions FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM pmoves_core.vpn_nodes
      WHERE vpn_nodes.user_id = auth.uid()
      AND 'tag:admin' = ANY(vpn_nodes.tags)
    )
  );

CREATE POLICY "Users can insert own remote sessions"
  ON pmoves_core.remote_sessions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- vpn_nodes policies
CREATE POLICY "Users can view own VPN nodes"
  ON pmoves_core.vpn_nodes FOR SELECT
  USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Admins can view all VPN nodes"
  ON pmoves_core.vpn_nodes FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM pmoves_core.vpn_nodes vn
      WHERE vn.user_id = auth.uid()
      AND 'tag:admin' = ANY(vn.tags)
    )
  );

-- remote_access_policies policies
CREATE POLICY "Authenticated users can view enabled policies"
  ON pmoves_core.remote_access_policies FOR SELECT
  USING (enabled = true);

-- vpn_auth_keys policies
CREATE POLICY "Users can view own VPN auth keys"
  ON pmoves_core.vpn_auth_keys FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all VPN auth keys"
  ON pmoves_core.vpn_auth_keys FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM pmoves_core.vpn_nodes
      WHERE vpn_nodes.user_id = auth.uid()
      AND 'tag:admin' = ANY(vpn_nodes.tags)
    )
  );

CREATE POLICY "Users can insert own VPN auth keys"
  ON pmoves_core.vpn_auth_keys FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- =============================================================================
-- Triggers for Automatic Timestamp Updates
-- =============================================================================

-- Updated at trigger function
CREATE OR REPLACE FUNCTION pmoves_core.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables
CREATE TRIGGER update_remote_sessions_updated_at
  BEFORE UPDATE ON pmoves_core.remote_sessions
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at_column();

CREATE TRIGGER update_vpn_nodes_updated_at
  BEFORE UPDATE ON pmoves_core.vpn_nodes
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at_column();

CREATE TRIGGER update_remote_access_policies_updated_at
  BEFORE UPDATE ON pmoves_core.remote_access_policies
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at_column();

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to check if a user has remote access to a device
CREATE OR REPLACE FUNCTION pmoves_core.check_remote_access(
  p_user_id UUID,
  p_target_device TEXT
) RETURNS TABLE (
  has_access BOOLEAN,
  policy_name TEXT,
  requires_approval BOOLEAN
) AS $$
DECLARE
  v_user_tags TEXT[];
  v_has_access BOOLEAN := false;
  v_policy_name TEXT := NULL;
  v_requires_approval BOOLEAN := false;
BEGIN
  -- Get user's VPN tags
  SELECT ARRAY_AGG(DISTINCT unnest(tags)) INTO v_user_tags
  FROM pmoves_core.vpn_nodes
  WHERE user_id = p_user_id AND is_online = true;

  -- If no tags found, no access
  IF v_user_tags IS NULL THEN
    v_user_tags := ARRAY[]::TEXT[];
  END IF;

  -- Check for matching policy
  SELECT
    TRUE,
    rap.name,
    rap.requires_approval
  INTO v_has_access, v_policy_name, v_requires_approval
  FROM pmoves_core.remote_access_policies rap
  WHERE rap.enabled = true
    AND (
      -- Device is in policy's target list
      p_target_device = ANY(rap.target_devices)
      OR -- Policy applies to all devices
      rap.target_devices = ARRAY[]::TEXT[]
    )
    AND (
      -- User has required tags
      v_user_tags && rap.user_tags
      OR -- Policy applies to all users
      rap.user_tags = ARRAY[]::TEXT[]
    )
  LIMIT 1;

  RETURN QUERY SELECT v_has_access, v_policy_name, v_requires_approval;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute on helper function
GRANT EXECUTE ON FUNCTION pmoves_core.check_remote_access TO authenticated;

-- =============================================================================
-- Initial Data (Optional)
-- =============================================================================

-- Insert default remote access policy for admins
INSERT INTO pmoves_core.remote_access_policies (name, description, user_tags, target_devices, requires_approval, enabled)
VALUES (
  'admin-full-access',
  'Administrators have full remote access to all devices',
  ARRAY['tag:admin'],
  ARRAY[]::TEXT[],  -- All devices
  false,
  true
) ON CONFLICT (name) DO NOTHING;

-- Insert default remote access policy for support
INSERT INTO pmoves_core.remote_access_policies (name, description, user_tags, target_devices, requires_approval, enabled)
VALUES (
  'support-user-access',
  'Support team can access user devices for troubleshooting',
  ARRAY['tag:support'],
  ARRAY[]::TEXT[],  -- All devices
  false,
  true
) ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Migration Complete
-- =============================================================================
-- Verify tables were created
SELECT
  'remote_sessions' as table_name,
  COUNT(*) as row_count
FROM pmoves_core.remote_sessions
UNION ALL
SELECT
  'vpn_nodes',
  COUNT(*)
FROM pmoves_core.vpn_nodes
UNION ALL
SELECT
  'remote_access_policies',
  COUNT(*)
FROM pmoves_core.remote_access_policies
UNION ALL
SELECT
  'vpn_auth_keys',
  COUNT(*)
FROM pmoves_core.vpn_auth_keys;
