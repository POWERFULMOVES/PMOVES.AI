// Seeds the CHIT geometry demo constellation described in
// docs/pmoves_chit_all_in_one/pmoves_all_in_one/pmoves_chit_patch/neo4j/seed/001_fixture.cql
// Adjustments keep the import idempotent and ensure relationships are created without
// relying on session-scoped variables.

MERGE (anchor:Anchor {id:'6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111'})
  SET anchor.model='mini-vec-4d',
      anchor.dim=4,
      anchor.label='sports/basketball',
      anchor.modality='text';

MERGE (constellation:Constellation {id:'8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111'})
  SET constellation.spectrum=[0.05,0.15,0.30,0.30,0.20],
      constellation.radial_min=0.0,
      constellation.radial_max=1.0,
      constellation.bins=5,
      constellation.summary='Basketball-ish topics';

MERGE (anchor)-[:FORMS]->(constellation);

MERGE (p1:Point {id:'a1a1a1a1-1111-4a4a-9c9c-111111111111'})
  SET p1.source_ref='doc:codebook#t1',
      p1.proj=0.95,
      p1.conf=0.92,
      p1.x=0.1,
      p1.y=0.2,
      p1.modality='text',
      p1.text='Basketball practice and drills';

MERGE (p2:Point {id:'a2a2a2a2-2222-4b4b-9d9d-222222222222'})
  SET p2.source_ref='doc:codebook#t8',
      p2.proj=0.90,
      p2.conf=0.90,
      p2.x=0.2,
      p2.y=0.1,
      p2.modality='text',
      p2.text='Ball handling basics';

MERGE (p3:Point {id:'a3a3a3a3-3333-4c4c-9e9e-333333333333'})
  SET p3.source_ref='v:yt_dQw4w9WgXcQ#t=37.2-39.7',
      p3.proj=0.86,
      p3.conf=0.88,
      p3.x=0.0,
      p3.y=0.0,
      p3.modality='video',
      p3.text='free throws; slow pan';

MATCH (constellation:Constellation {id:'8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111'}),
      (p:Point)
WHERE p.id IN ['a1a1a1a1-1111-4a4a-9c9c-111111111111',
               'a2a2a2a2-2222-4b4b-9d9d-222222222222',
               'a3a3a3a3-3333-4c4c-9e9e-333333333333']
MERGE (constellation)-[:HAS]->(p);

MERGE (m1:MediaRef {uid:'doc|codebook|0-6'})
  SET m1.modality='doc',
      m1.ref_id='codebook',
      m1.token_start=0,
      m1.token_end=6;

MERGE (m2:MediaRef {uid:'doc|codebook|7-12'})
  SET m2.modality='doc',
      m2.ref_id='codebook',
      m2.token_start=7,
      m2.token_end=12;

MERGE (m3:MediaRef {uid:'video|yt_dQw4w9WgXcQ|37.2-39.7'})
  SET m3.modality='video',
      m3.ref_id='yt_dQw4w9WgXcQ',
      m3.t_start=37.2,
      m3.t_end=39.7,
      m3.frame_idx=1112,
      m3.scene='free throws';

MATCH (p:Point {id:'a1a1a1a1-1111-4a4a-9c9c-111111111111'}),
      (m:MediaRef {uid:'doc|codebook|0-6'})
MERGE (p)-[:LOCATES]->(m);

MATCH (p:Point {id:'a2a2a2a2-2222-4b4b-9d9d-222222222222'}),
      (m:MediaRef {uid:'doc|codebook|7-12'})
MERGE (p)-[:LOCATES]->(m);

MATCH (p:Point {id:'a3a3a3a3-3333-4c4c-9e9e-333333333333'}),
      (m:MediaRef {uid:'video|yt_dQw4w9WgXcQ|37.2-39.7'})
MERGE (p)-[:LOCATES]->(m);
