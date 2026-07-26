# LinkedIn Persona → Living-Doc Room (Design Plan)

> **Status:** DESIGN PLAN (scope-only, no build in this pass)
> **Companion to:** [`06_linkedin_profile.md`](06_linkedin_profile.md) (the content source of truth)
> **Requested:** a "better version" of the LinkedIn profile — a *living doc with a web overlay* that shows **Remotion** + **PreTeXt** skills, uses **design elements from the website and rooms**, and eventually becomes **a room on pmoves.ai proper (not Cloudflare Pages)**.

---

## 1. Vision

The static LinkedIn profile (§`06`) is the *portable* artifact you paste into LinkedIn. This plan is its *living* counterpart: a designed **persona room** on pmoves.ai that renders the same content as an interactive experience and doubles as the employer-facing **portfolio package** notes2.md calls for:

1. A 3-minute **architecture walkthrough** (Remotion video).
2. One **working end-to-end demonstration** (embed).
3. One **case study** (PreTeXt technical doc).
4. A **code-and-evidence page** (repo/commits/tests/diagrams).
5. A **School of PMOVES teaching sample** (Remotion clip).

The room *is* the "better version": profile content + video + rendered technical docs + the rooms/website design language, in one addressable place.

## 2. Why a room (not just a page)

PMOVES already models UI surfaces as **rooms on a stage** (`pmoves/config/rooms/catalog.json`, P7 stage manager). Making the persona a first-class room means it inherits the catalog, the stage lifecycle (rehearsal → live → review → archive), and the shared design system — and it demonstrates the platform *by being built on it*. The medium becomes the proof.

## 3. Components

| Layer | What | Source in-repo |
|-------|------|----------------|
| **Content model** | The profile as structured data (headline, about, experience, skills, featured, translation) | `06_linkedin_profile.md` → parsed/front-mattered |
| **Room shell** | Page/layout using website design tokens (fonts, `hyperdim` viz, `embeds`) + rooms-on-a-stage framing | `website/` (`assets`, `fonts`, `hyperdim`, `embeds`), rooms catalog |
| **Remotion layer** | 3-min architecture walkthrough + short loops (beats→code, convergence wave, "agents read the room") | a2ui Remotion renderer (headless render → MP4/frames → served assets) |
| **PreTeXt layer** | Deep technical docs (CHIT math, MOF isomorphism, CGP {δ,Hz,κ,A,F}) authored once, rendered to accessible HTML+math | PreTeXt (XML → HTML/MathJax); source from `architecture/` docs |
| **Evidence panel** | Live repo signals — PRs, commits, tests, submodule map | GitHub API / static snapshot |
| **Design system** | Armor tokens / rooms visual language (ties to the DL-1B CHIT-tour reskin lane) | website design + rooms tokens |

## 4. Host (open decision — NOT Cloudflare Pages)

The current `website/` is CF Pages (`_headers`, `_redirects`). pmoves.ai *proper* is to be hosted elsewhere. Candidates (decision pending):

- **Fleet-hosted behind Traefik + Tailscale/Cloudflare-DNS TLS** — reuse the SSO gateway edge stood up in #2221 (Traefik on `pmoves_external`, forward-auth available for gated sections like the financial model). Keeps it local-first + sovereign, matches the platform thesis.
- **A VPS node** (Hostinger fleet) fronted the same way.
- **A non-CF static/edge host** if a pure-static build is preferred.

Recommendation: **fleet-hosted behind the #2221 Traefik edge** — public persona room + optional forward-auth-gated panels (investor/financial), consistent with the SSO work and the privacy-mesh rule.

## 5. Architecture sketch

```
06_linkedin_profile.md  ──parse──▶  persona content model (JSON/front-matter)
architecture/*.md       ──PreTeXt─▶ technical HTML panels (math via MathJax)
a2ui Remotion           ──render──▶ walkthrough.mp4 + loop clips (assets)
                                   │
website/rooms design ───────────────┼──▶  persona ROOM (catalog entry + page)
                                   │        served on pmoves.ai (Traefik edge)
GitHub API ─────────────evidence───┘        public + optional gated panels
```

The room registers in `pmoves/config/rooms/catalog.json` and is stage-managed by P7 like any other room.

## 6. Phases

1. **Content model** — front-matter/parse `06_linkedin_profile.md` into structured data; single source of truth (LinkedIn paste + room both derive from it).
2. **Room shell** — static page with website/rooms design tokens; sections mirror the profile; register the catalog entry (rehearsal stage).
3. **Remotion walkthrough** — script + render the 3-min architecture video via the a2ui renderer; embed.
4. **PreTeXt panels** — author 1–2 technical case studies in PreTeXt; render to HTML+math; embed as the depth/evidence layer.
5. **Host on pmoves.ai proper** — deploy behind the Traefik edge (non-CF), public + gated panels; promote the room rehearsal → live.

## 7. Open decisions (need your call before build)

- **Host**: confirm fleet-hosted-behind-Traefik vs VPS vs other (§4).
- **PreTeXt vs alternatives**: PreTeXt is strong for math/technical books; MyST/Quarto are lighter for web-first. Confirm PreTeXt is the intended tool (you named it) or open to MyST/Quarto.
- **Public vs gated**: which panels are public (architecture, code-evidence, teaching) vs forward-auth-gated (financial model, investor materials).
- **Remotion scope**: one 3-min walkthrough first, or the full clip set (beats→code, convergence, teaching) up front.
- **Domain cutover**: how/when pmoves.ai DNS points at the new (non-CF) host.

## 8. Non-goals (this pass)

No build, no host provisioning, no DNS change. This is the scoped plan; implementation is a separate, phased effort gated on §7.
