-- sqlfluff: disable=all

-- Demo geometry constellation to mirror docs/pmoves_chit_all_in_one fixture.
-- Populates anchors/constellations/shape_points/shape_index with sample data.

set search_path = public;

insert into anchors (id, kind, dim, anchor, meta)
values (
  '6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111',
  'text',
  4,
  array[0.8, 0.2, 0.0, 0.0]::float4[],
  jsonb_build_object(
    'label', 'sports/basketball',
    'source', 'docs/pmoves_chit_all_in_one',
    'demo', true
  )
)
on conflict (id) do nothing;

insert into constellations (id, anchor_id, summary, radial_min, radial_max, spectrum, meta)
values (
  '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
  '6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111',
  'Basketball-ish topics',
  0.0,
  1.0,
  array[0.05, 0.15, 0.30, 0.30, 0.20]::float4[],
  jsonb_build_object(
    'bins', 5,
    'demo', true,
    'source', 'docs/pmoves_chit_all_in_one'
  )
)
on conflict (id) do nothing;

insert into shape_points (id, constellation_id, modality, ref_id, t_start, t_end, frame_idx,
                          token_start, token_end, proj, conf, meta)
values
  (
    'a1a1a1a1-1111-4a4a-9c9c-111111111111',
    '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
    'text',
    'doc:codebook#t1',
    null,
    null,
    null,
    0,
    6,
    0.95,
    0.92,
    jsonb_build_object(
      'description', 'Basketball practice and drills',
      'x', 0.1,
      'y', 0.2,
      'source', 'docs/pmoves_chit_all_in_one'
    )
  ),
  (
    'a2a2a2a2-2222-4b4b-9d9d-222222222222',
    '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
    'text',
    'doc:codebook#t8',
    null,
    null,
    null,
    7,
    12,
    0.90,
    0.90,
    jsonb_build_object(
      'description', 'Ball handling basics',
      'x', 0.2,
      'y', 0.1,
      'source', 'docs/pmoves_chit_all_in_one'
    )
  ),
  (
    'a3a3a3a3-3333-4c4c-9e9e-333333333333',
    '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
    'video',
    'yt_dQw4w9WgXcQ',
    37.2,
    39.7,
    1112,
    null,
    null,
    0.86,
    0.88,
    jsonb_build_object(
      'description', 'Free throws; slow pan',
      'source_ref', 'v:yt_dQw4w9WgXcQ#t=37.2-39.7',
      'source', 'docs/pmoves_chit_all_in_one'
    )
  )
on conflict (id) do nothing;

insert into shape_index (shape_id, modality, ref_id, loc_hash, meta)
values
  (
    'a1a1a1a1-1111-4a4a-9c9c-111111111111',
    'text',
    'doc:codebook',
    'doc:codebook#0-6',
    jsonb_build_object(
      'token_start', 0,
      'token_end', 6,
      'source', 'docs/pmoves_chit_all_in_one'
    )
  ),
  (
    'a2a2a2a2-2222-4b4b-9d9d-222222222222',
    'text',
    'doc:codebook',
    'doc:codebook#7-12',
    jsonb_build_object(
      'token_start', 7,
      'token_end', 12,
      'source', 'docs/pmoves_chit_all_in_one'
    )
  ),
  (
    'a3a3a3a3-3333-4c4c-9e9e-333333333333',
    'video',
    'yt_dQw4w9WgXcQ',
    'yt_dQw4w9WgXcQ#37.2-39.7',
    jsonb_build_object(
      't_start', 37.2,
      't_end', 39.7,
      'frame_idx', 1112,
      'source', 'docs/pmoves_chit_all_in_one'
    )
  )
on conflict do nothing;
