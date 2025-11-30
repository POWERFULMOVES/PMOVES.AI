insert into anchors (id, model, dim, anchor, label, modality)
values ('6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111','mini-vec-4d',4, ARRAY[0.8,0.2,0,0], 'sports/basketball','text')
on conflict (id) do nothing;
insert into constellations (id, anchor_id, modality, spectrum, radial_min, radial_max, bins, summary)
values ('8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111','6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111','text', ARRAY[0.05,0.15,0.30,0.30,0.20], 0.0, 1.0, 5, 'Basketball-ish topics')
on conflict (id) do nothing;
insert into shape_points (id, constellation_id, source_ref, proj, conf, x, y, modality, text)
values
  ('a1a1a1a1-1111-4a4a-9c9c-111111111111','8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111','doc:codebook#t1', 0.95, 0.92, 0.1, 0.2, 'text', 'Basketball practice and drills'),
  ('a2a2a2a2-2222-4b4b-9d9d-222222222222','8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111','doc:codebook#t8', 0.90, 0.90, 0.2, 0.1, 'text', 'Ball handling basics'),
  ('a3a3a3a3-3333-4c4c-9e9e-333333333333','8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111','v:yt_dQw4w9WgXcQ#t=37.2-39.7', 0.86, 0.88, 0.0, 0.0, 'video', 'free throws; slow pan')
on conflict (id) do nothing;
insert into modalities (point_id, modality, ref_id, t_start, t_end, frame_idx, token_start, token_end, extra)
values
  ('a3a3a3a3-3333-4c4c-9e9e-333333333333','video','yt_dQw4w9WgXcQ',37.2,39.7,1112,null,null,'{"scene":"free throws"}'),
  ('a1a1a1a1-1111-4a4a-9c9c-111111111111','doc','codebook',null,null,null,0,6,'{}'),
  ('a2a2a2a2-2222-4b4b-9d9d-222222222222','doc','codebook',null,null,null,7,12,'{}')
on conflict do nothing;
insert into shape_index (shape_hash, owner, sig)
values ('DEMO_SHAPE_HASH_0001','demo@pmoves.ai','{"alg":"HMAC-SHA256","kid":"demo"}');
