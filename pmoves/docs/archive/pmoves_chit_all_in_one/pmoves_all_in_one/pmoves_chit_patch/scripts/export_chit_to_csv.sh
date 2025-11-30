#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?Set DATABASE_URL (e.g. postgres://user:pass@host:5432/db)}"
OUT_DIR="${1:-exports}"
mkdir -p "$OUT_DIR"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT id::text, model, dim, label, modality FROM anchors) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/anchors.csv"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT id::text, coalesce(anchor_id,'')::text AS anchor_id, spectrum::text AS spectrum, radial_min, radial_max, bins, modality, coalesce(summary,'') AS summary FROM constellations) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/constellations.csv"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT id::text, constellation_id::text, source_ref, proj, conf, x, y, modality, coalesce(text,'') AS text FROM shape_points) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/points.csv"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT concat_ws('|', modality, ref_id, coalesce(token_start::text,'')||'-'||coalesce(token_end::text,'')||coalesce(t_start::text,'')||'-'||coalesce(t_end::text,'')) AS uid, modality, ref_id, t_start, t_end, frame_idx, token_start, token_end, coalesce(extra::text,'{}') AS extra FROM modalities) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/mediarefs.csv"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT a.id::text AS anchor_id, c.id::text AS constellation_id FROM constellations c JOIN anchors a ON a.id = c.anchor_id) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/forms.csv"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT c.id::text AS constellation_id, p.id::text AS point_id FROM shape_points p JOIN constellations c ON c.id = p.constellation_id) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/has.csv"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "\COPY (SELECT p.id::text AS point_id, concat_ws('|', m.modality, m.ref_id, coalesce(m.token_start::text,'')||'-'||coalesce(m.token_end::text,'')||coalesce(m.t_start::text,'')||'-'||coalesce(m.t_end::text,'')) AS media_uid FROM modalities m JOIN shape_points p ON p.id = m.point_id) TO STDOUT WITH CSV HEADER" > "$OUT_DIR/locates.csv"
echo "Exported CHIT CSVs to $OUT_DIR/"
