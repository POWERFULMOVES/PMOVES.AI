"""persona-thirdref — third-reference persona grounding consumer.

Subscribes to persona.consumption.recorded.v1, joins the consumed item
against the Supabase enrichment columns (resonance_domain,
resonance_secondary, persona_signal, curriculum_track on
pmoves_core.youtube_videos), and emits shape.trace.recorded.v1 with
interaction_type="media" so the shape-discovery pipeline accumulates
persona grounding from shared consumption.

Third reference source: after authored configuration (first ref) and
observed interaction telemetry (second ref), WHAT a human or agent
actually consumes of the shared library is the third reference for who
they are. Consumption is gravitational signal — see
pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md.

Threshold accumulation: after PERSONA_THIRDREF_PROFILE_THRESHOLD events
for one identity, the consumer also publishes shape.profile.updated.v1
carrying the normalized resonance-domain histogram for that identity —
the "personas get enriched" moment.
"""
