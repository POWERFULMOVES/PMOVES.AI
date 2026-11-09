# Persona room — PreTeXt technical panels

Authored technical case studies for the persona living-doc room (Phase 4 of
[`../../../docs/research/persona/07_linkedin_living_doc_room.md`](../../../docs/research/persona/07_linkedin_living_doc_room.md)).
PreTeXt is the authoring source of truth; the room embeds/links the rendered HTML.

## Source
- [`source/main.ptx`](source/main.ptx) — *CHIT and the Metal-Organic Framework: A
  Structural Isomorphism*. Three sections: the external-egress gate as set
  membership (`pmoves_external ∈ N(s)` — ties to the PMOVES_NETWORKS wiring), the
  MOF isomorphism map `Φ`, and the CGP packet `{δ, Hz, κ, A, F}` as a state vector.
- `project.ptx` / `publication/publication.ptx` — standard `pretext new article`
  scaffold, pointed at `source/main.ptx`.

## Build (verified — pretext-cli 2.45.0 / core 2.45.0)

```bash
cd pmoves/rooms/persona/pretext
uv run --no-project --with pretext pretext build web
# → output/web/*.html  (index.html, egress.html, isomorphism.html, cgp.html …)
```

`output/` is generated (gitignored) — rebuild on deploy. The web target renders
math via MathJax, which loads on the deployed pmoves.ai room (no CSP restriction).
The self-contained shell/Artifact preview can't load the MathJax CDN, so it
references this case study and links here rather than inlining the built math.

## Deploy wiring (Phase 4b)
On the pmoves.ai host (behind the #2221 Traefik edge), build this target into a
path served under the persona room and point the room's PreTeXt panel at
`…/pretext/index.html`. Until then the room's slot describes the case study and
links to `source/main.ptx`.
