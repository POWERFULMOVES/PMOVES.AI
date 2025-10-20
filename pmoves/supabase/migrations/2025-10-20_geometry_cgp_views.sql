-- Create helper views so PostgREST exposes the canonical CGP payloads
-- consumed by hi-rag-gateway-v2 ShapeStore warmup and downstream tooling.
-- When these views are absent ShapeStore falls back to the normalized tables,
-- but returning a lightweight JSON payload keeps startup logs clean and
-- provides a predictable API surface for other services (evo-controller, etc.).

CREATE OR REPLACE VIEW public.geometry_cgp_v1 AS
SELECT
    jsonb_build_object(
        'spec', 'geometry.cgp.v1',
        'source', 'supabase',
        'super_nodes',
            jsonb_build_array(
                jsonb_build_object(
                    'constellations',
                        jsonb_build_array(
                            jsonb_strip_nulls(
                                jsonb_build_object(
                                    'id', c.id,
                                    'summary', c.summary,
                                    'spectrum', c.spectrum,
                                    'radial_minmax',
                                        CASE
                                            WHEN c.radial_min IS NOT NULL OR c.radial_max IS NOT NULL
                                                THEN jsonb_build_array(c.radial_min, c.radial_max)
                                            ELSE NULL
                                        END,
                                    'meta', NULLIF(c.meta, '{}'::jsonb),
                                    'anchor',
                                        jsonb_strip_nulls(
                                            jsonb_build_object(
                                                'id', a.id,
                                                'kind', a.kind,
                                                'dim', a.dim,
                                                'anchor', a.anchor,
                                                'anchor_enc', a.anchor_enc,
                                                'meta', NULLIF(a.meta, '{}'::jsonb)
                                            )
                                        ),
                                    'points',
                                        COALESCE(
                                            (
                                                SELECT jsonb_agg(
                                                    jsonb_strip_nulls(
                                                        jsonb_build_object(
                                                            'id', sp.id,
                                                            'modality', sp.modality,
                                                            'ref_id', sp.ref_id,
                                                            't_start', sp.t_start,
                                                            't_end', sp.t_end,
                                                            'frame_idx', sp.frame_idx,
                                                            'token_start', sp.token_start,
                                                            'token_end', sp.token_end,
                                                            'proj', sp.proj,
                                                            'conf', sp.conf,
                                                            'meta', NULLIF(sp.meta, '{}'::jsonb)
                                                        )
                                                    )
                                                )
                                                FROM public.shape_points sp
                                                WHERE sp.constellation_id = c.id
                                            ),
                                            '[]'::jsonb
                                        )
                                )
                            )
                        )
                )
            )
    ) AS payload,
    c.created_at
FROM public.constellations c
JOIN public.anchors a ON a.id = c.anchor_id;

CREATE OR REPLACE VIEW public.geometry_cgp_packets AS
SELECT payload, created_at
FROM public.geometry_cgp_v1;

-- Ensure PostgREST roles can read the views.
GRANT SELECT ON public.geometry_cgp_v1 TO anon, authenticated, service_role;
GRANT SELECT ON public.geometry_cgp_packets TO anon, authenticated, service_role;
