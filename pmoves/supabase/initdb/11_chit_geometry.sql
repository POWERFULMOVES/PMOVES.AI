-- CHIT geometry tables (anchors, constellations, shape points/index)
-- Mirrors the Supabase migration so `supabase initdb` stays in sync.

set search_path = public;

create table if not exists anchors (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('text','audio','video','image','latent','multi')),
  dim integer not null check (dim > 0),
  anchor float4[] null,
  anchor_enc jsonb null,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_anchors_kind on anchors (kind);
create index if not exists idx_json_meta_anchors on anchors using gin (meta);

create table if not exists constellations (
  id uuid primary key default gen_random_uuid(),
  anchor_id uuid not null references anchors(id) on delete cascade,
  summary text null,
  radial_min double precision null,
  radial_max double precision null,
  spectrum float4[] null,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_constellations_anchor on constellations (anchor_id);
create index if not exists idx_json_meta_constellations on constellations using gin (meta);

create table if not exists shape_points (
  id uuid primary key default gen_random_uuid(),
  constellation_id uuid not null references constellations(id) on delete cascade,
  modality text not null check (modality in ('text','audio','video','image','latent')),
  ref_id text not null,
  t_start double precision null,
  t_end double precision null,
  frame_idx integer null,
  token_start integer null,
  token_end integer null,
  proj double precision null,
  conf double precision null,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_shape_points_lookup on shape_points (modality, ref_id);
create index if not exists idx_shape_points_time on shape_points (t_start, t_end);
create index if not exists idx_json_meta_points on shape_points using gin (meta);

create table if not exists shape_index (
  shape_id uuid not null,
  modality text not null,
  ref_id text not null,
  loc_hash text not null,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (shape_id, modality, ref_id, loc_hash)
);

create index if not exists idx_shape_index_ref on shape_index (modality, ref_id);
create index if not exists idx_json_meta_shape_index on shape_index using gin (meta);
