-- Demo CHIT/geometry records for local smoke tests.
-- Inserts anchor, constellation, shape points, and shape index rows.

WITH upsert_anchor AS (
    INSERT INTO public.anchors (id, kind, dim, anchor, meta)
    VALUES (
        '6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111',
        'video',
        4,
        ARRAY[0.8, 0.2, 0.0, 0.0]::float4[],
        '{"label":"Sports Broadcast","model":"demo-mini-vec-4d"}'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), anchor_ref AS (
    SELECT id FROM upsert_anchor
    UNION ALL
    SELECT '6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111' WHERE NOT EXISTS (SELECT 1 FROM upsert_anchor)
)
INSERT INTO public.constellations (id, anchor_id, summary, radial_min, radial_max, spectrum, meta)
SELECT
    '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
    id,
    'Basketball practice timeline',
    0.0,
    1.0,
    ARRAY[0.05, 0.15, 0.30, 0.30, 0.20]::float4[],
    '{"namespace":"pmoves","source":"seed"}'::jsonb
FROM anchor_ref
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.shape_points (id, constellation_id, modality, ref_id, t_start, t_end, frame_idx, token_start, token_end, proj, conf, meta)
VALUES
    (
        'a1a1a1a1-1111-4a4a-9c9c-111111111111',
        '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
        'text',
        'doc:codebook#t1',
        NULL,
        NULL,
        NULL,
        0,
        6,
        0.95,
        0.92,
        '{"summary":"Basketball practice and drills"}'::jsonb
    ),
    (
        'a2a2a2a2-2222-4b4b-9d9d-222222222222',
        '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
        'text',
        'doc:codebook#t8',
        NULL,
        NULL,
        NULL,
        7,
        12,
        0.90,
        0.90,
        '{"summary":"Ball handling basics"}'::jsonb
    ),
    (
        'a3a3a3a3-3333-4c4c-9e9e-333333333333',
        '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
        'video',
        'yt_dQw4w9WgXcQ',
        37.2,
        39.7,
        1112,
        NULL,
        NULL,
        0.86,
        0.88,
        '{"scene":"free throws","notes":"slow pan"}'::jsonb
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.shape_index (shape_id, modality, ref_id, loc_hash, meta)
VALUES
    (
        '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
        'text',
        'doc:codebook',
        'doc:codebook#t1-6',
        '{"point_id":"a1a1a1a1-1111-4a4a-9c9c-111111111111"}'::jsonb
    ),
    (
        '8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111',
        'video',
        'yt_dQw4w9WgXcQ',
        'yt_dQw4w9WgXcQ#37.2-39.7',
        '{"point_id":"a3a3a3a3-3333-4c4c-9e9e-333333333333"}'::jsonb
    )
ON CONFLICT (shape_id, modality, ref_id, loc_hash) DO NOTHING;
