-- PMOVES Social Scheduler Migration
-- Adds social scheduling capabilities to studio_board table
-- Adapted from COS (Content Automation OS) patterns

-- Add social scheduling columns to studio_board
alter table studio_board add column if not exists publish_at timestamptz;
alter table studio_board add column if not exists social_channels text[]; -- ['discord', 'twitter', 'instagram', 'facebook', 'linkedin', 'tiktok']
alter table studio_board add column if not exists content_pillar text; -- e.g., 'education', 'entertainment', 'engagement', 'promotion'
alter table studio_board add column if not exists post_type text; -- e.g., 'image', 'video', 'carousel', 'story', 'reel', 'thread'
alter table studio_board add column if not exists final_content text; -- The actual post content/caption
alter table studio_board add column if not exists ai_image_url text;
alter table studio_board add column if not exists image_prompt text;

-- Platform-specific post tracking (stored in meta JSONB, but adding index helper)
comment on column studio_board.meta is 'Contains platform post IDs and URLs: {discord_post_id, twitter_post_id, instagram_post_id, facebook_post_id, linkedin_post_id, tiktok_post_id, *_post_url}';

-- Create social_posts table for tracking individual platform posts
create table if not exists social_posts (
  id bigserial primary key,
  studio_board_id bigint references studio_board(id) on delete cascade,
  platform text not null, -- 'discord', 'twitter', 'instagram', 'facebook', 'linkedin', 'tiktok'
  post_id text, -- Platform's post ID
  post_url text, -- URL to the post
  status text default 'pending', -- 'pending', 'scheduled', 'published', 'failed'
  scheduled_at timestamptz,
  published_at timestamptz,
  error_message text,
  engagement_stats jsonb default '{}', -- likes, comments, shares, etc.
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Create brand_assets table for multi-brand support (like COS)
create table if not exists brand_assets (
  id bigserial primary key,
  namespace text not null unique,
  brand_name text,
  about_brand text,
  customer_avatar text,
  -- Social account URLs
  discord_webhook_url text,
  twitter_account text,
  instagram_account text,
  facebook_page_url text,
  linkedin_page_url text,
  tiktok_account text,
  -- API credentials (encrypted reference)
  credentials_ref text, -- Reference to encrypted credentials
  -- Brand visual assets
  logo_url text,
  brand_colors jsonb default '{}',
  -- Settings
  default_hashtags text[],
  content_pillars text[],
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Create content_schedule view for easy querying of pending posts
create or replace view content_schedule as
select
  sb.id,
  sb.title,
  sb.namespace,
  sb.content_url,
  sb.final_content,
  sb.social_channels,
  sb.publish_at,
  sb.status,
  sb.content_pillar,
  sb.post_type,
  sb.ai_image_url,
  sb.meta,
  ba.brand_name,
  ba.discord_webhook_url
from studio_board sb
left join brand_assets ba on sb.namespace = ba.namespace
where sb.status = 'approved'
  and sb.publish_at is not null
  and sb.publish_at <= now()
order by sb.publish_at asc;

-- Indexes for efficient scheduling queries
create index if not exists idx_studio_board_publish_at on studio_board(publish_at) where publish_at is not null;
create index if not exists idx_studio_board_status_publish on studio_board(status, publish_at) where status = 'approved';
create index if not exists idx_social_posts_platform on social_posts(platform, status);
create index if not exists idx_social_posts_studio_board on social_posts(studio_board_id);

-- Grant permissions (removed anon for security - only authenticated and service_role)
grant select, insert, update, delete on table social_posts to authenticated, service_role;
grant usage, select on sequence social_posts_id_seq to authenticated, service_role;
grant select, insert, update, delete on table brand_assets to authenticated, service_role;
grant usage, select on sequence brand_assets_id_seq to authenticated, service_role;
grant select on content_schedule to authenticated, service_role;

-- RLS policies
alter table social_posts enable row level security;
alter table brand_assets enable row level security;

-- Policy: Users can see their own namespace's posts (namespace from auth.uid())
create policy social_posts_select_own on social_posts for select
  to authenticated
  using (
    studio_board_id in (
      select id from studio_board where namespace = current_user
    )
  );

-- Policy: Service role can do anything
create policy social_posts_service_all on social_posts for all
  to service_role
  using (true)
  with check (true);

-- Policy: Users can see their own brand assets
create policy brand_assets_select_own on brand_assets for select
  to authenticated
  using (namespace = current_user);

-- Policy: Service role full access to brand_assets
create policy brand_assets_service_all on brand_assets for all
  to service_role
  using (true)
  with check (true);

-- Insert default PMOVES brand
insert into brand_assets (namespace, brand_name, about_brand, content_pillars)
values ('pmoves', 'PMOVES', 'AI-powered holographic content creation platform',
        array['education', 'entertainment', 'technology', 'creativity'])
on conflict (namespace) do nothing;
