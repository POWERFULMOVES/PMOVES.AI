# A2UI Integration Audit — 2026-08-14

**Scope:** the A2UI surface across PMOVES.AI — protocol layer, the `pretext` text-layout
library, the HTML5 static surface, and the Remotion render path.

**Method:** static read of code, contracts, and docs. No services were started; no live
behaviour was exercised. Every finding below carries the command that produced it so it can
be re-run.

**Baseline:** `f27d43ed6` (main, `ci(python-tests): make the merge gate capable of failing
(#2526)`). Findings were first gathered against an older tree and **re-verified in full**
against this commit. Two findings were corrected in the course of the audit and are stated
in corrected form: **F3** (the naive grep result changed between passes) and **F4** (the fork
turned out to carry no local commits at all). **F9** was found late, by following a reviewer
prompt to check `PMOVES-DoX`, and is the reason the reconciliation section exists.

**Auditor:** CLAUDE-OPUS-5 (4090 node). **Output:** assessment + recommended sequencing.
No code changed.

---

## Executive summary

The A2UI lane is not broken so much as **overloaded**: one name covers three unrelated
schemas, and the documentation asserts seams that the code does not implement. The
individual pieces are, on the whole, well built — the CHIT gate on the bridge is real and
tested, the vendored web bundle is genuinely self-contained and reproducibly built, and the
Remotion renderer is better instrumented than most services in the repo.

The cheapest, highest-leverage work is **not** engineering. Five of the nine findings are
documentation and registry corrections that cost hours and prevent the next contributor from
building against a seam that isn't there. The version split in **F9** — which looks like the
most alarming finding — turns out to be two wrong strings in one file, not a migration.

---

## F1 — Three incompatible dialects share the name "A2UI"

| Dialect | Contract | Wire shape | Consumers |
|---|---|---|---|
| **Google A2UI v0.8/v0.9** | `PMOVES-A2UI/specification/` | `beginRendering` / `surfaceUpdate`; catalog components | `a2ui-nats-bridge`, `website/stage/`, `a2ui.mjs` |
| **PMOVES A2UI v0.1/v0.2** | `pmoves/contracts/a2ui-v0.1.md` | `pm-*` custom elements; props + slots | `website/tenant-template/tenant-renderer.js` |
| **A2UI Animation v1** | `pmoves/contracts/a2ui-animation-schema.json` | `scenes[].elements[]`, `canvas`, `animation`, `enter_at_ms` | `pmoves/services/a2ui-renderer` (8107) |

Evidence:

```bash
grep -rn "beginRendering\|surfaceUpdate\|updateComponents" pmoves/services/a2ui-renderer/src/ | wc -l
# 0
```

The renderer instead validates `if (!spec.version || !spec.animation || !spec.scenes)`
(`src/index.ts:299`).

**Consequence:** the service named `a2ui-renderer` cannot render what `a2ui-nats-bridge`
publishes. Each dialect is internally coherent and independently defensible — the defect is
purely that one prefix spans three schemas, so "send it to A2UI" is an ambiguous instruction
in design docs, handoffs, and agent briefs.

**This is a naming defect, not necessarily an architecture defect.** See the note on
sequencing item 7 before assuming convergence is the fix.

---

## F2 — The v0.1 contract claims a renderer that is switched off

`pmoves/contracts/a2ui-v0.1.md` asserts it in two places:

- line 7: `> **Renderer**: vendored Lit at website/stage/vendor/a2ui.mjs (consumes these components)`
- line 249: `- **Renderer** (consumes A2UI messages): website/stage/stage.js + vendor/a2ui.mjs (Lit)`

But the stage explicitly disables the only code path that could instantiate a `pm-*` element:

```bash
grep -n "enableCustomElements" website/stage/stage.js
# 145:    el.enableCustomElements = false;
```

In the Lit renderer, `root.ts:65` declares `accessor enableCustomElements = false` and
`root.ts:144` guards the custom-element branch (`componentRegistry.get(component.type)` /
`customElements.get(component.type)`) behind it. With the flag false, a `pm-*` component can
never be reached through `a2ui.mjs`.

The actual consumer of `pm-*` components is `website/tenant-template/tenant-renderer.js`, a
separate hand-rolled renderer that imports `pmoves/web-components/register.js` directly.

**Risk:** a contributor builds a `pm-*` component against the v0.1 contract, expects it on
`/stage/`, and gets silence. Nothing errors.

---

## F3 — pretext is functionally absent from the HTML5 surface

**This finding changed during the audit and is stated in its corrected form.**

A naive grep now returns six hits, which on an older tree returned zero:

```bash
grep -rn "pretext" website/ | wc -l
# 6
```

All six are **non-functional**:

| Location | What it actually is |
|---|---|
| `website/chit-tour/data.js:362` | Tour narration prose describing the feature |
| `website/stage/data/public-rooms.json:247` | A display string: `"Apps: persona-shell · pretext-casestudies · remotion-walkthrough (planned)"` |
| `website/stage/data/room-layouts.json` ×4 | A room-manifest entry (`id`, `route`, `provider`, `action_namespace`) |

Checking for the layout API rather than the word:

```bash
grep -rn "resolveTextLayout\|@chenglou/pretext\|layoutWithLines\|measureLineStats\|prepareWithSegments\|text_layout" website/
# 1 hit — and it is the prose string in chit-tour/data.js:362
```

So: **zero functional use of the pretext layout engine in the browser surface.** The
deterministic layout path exists only inside `a2ui-renderer` (video). The same string can
therefore wrap differently in the HTML5 preview and the rendered video — which is precisely
the class of bug pretext exists to eliminate.

**The good news — it is already shaped for extraction.**
`pmoves/services/a2ui-renderer/src/remotion/pretextLayout.ts` exposes a single entry point,
`resolveTextLayout(text, style, layout, size, canvasWidth)`, which:

- returns `null` unless `layout.engine === 'pretext'` (safe opt-in), and
- returns `null` when no measurement runtime exists, via `hasCanvasMeasurementRuntime()` —
  which already tests for `'OffscreenCanvas' in runtime || 'document' in runtime`.

That second check means the module is **already browser-compatible by construction**. It
also carries real capability: line breaking, `shrinkWrap`, `maxLines` overflow detection,
locale via `setLocale`, letter-spacing, and `debugBoxes`.

This is the single best enhancement opportunity in the lane, and it is a lift-and-share, not
a rewrite.

---

## F4 — `Pmoves-pretext` submodule is an unfulfilled intent

```bash
git submodule status Pmoves-pretext
# -bb224e08d08995cbad2c773ae22e0a00cb9616b1 Pmoves-pretext
```

The leading `-` means uninitialized; the directory is empty. The dependency that actually
works is the npm package:

```bash
grep -n "chenglou/pretext" pmoves/services/a2ui-renderer/package.json
# 18:    "@chenglou/pretext": "^0.0.6",
```

The submodule is **not** vestigial — `website/chit-tour/data.js:362` states the intent
plainly: *"Pmoves tracks the POWERFULMOVES/Pmoves-pretext fork for ongoing alignment."* So
this is a declared strategy that was never completed, which is worse than either finishing
or dropping it: the repo advertises a fork-tracking posture it does not have.

**Measured delta (2026-08-14).** Initializing the submodule and adding the
upstream remote settles what the fork actually contains:

```bash
git rev-list --count upstream/main..HEAD   # 0   commits the fork adds
git rev-list --count HEAD..upstream/main   # 32  commits the fork is behind
git describe --tags HEAD                   # v0.0.6-7-gbb224e0
```

**The fork carries zero PMOVES commits.** It is a clean mirror of upstream,
parked 7 commits past the `v0.0.6` tag and 32 commits behind current
`upstream/main`; upstream has since released `v0.0.7` and `v0.0.8`.

This matters for the decision: "vendor the fork" does not mean "preserve our
customizations", because there are none. It means pinning to a stale
mid-release upstream snapshot. Customization has not started.

One real hazard does survive: fork HEAD is 7 commits past the `v0.0.6` tag while
`package.json` still reads `0.0.6`, and the service installs `^0.0.6` from npm —
which under npm semver resolves `>=0.0.6 <0.0.7`, i.e. the published `0.0.6`
tarball. So the tracked fork and the installed package are **different code
under the same version string**, and neither is current.

Two secondary concerns:

1. **`^0.0.6` gives no protection.** Under semver, `0.0.x` releases may break arbitrarily and
   a caret range on `0.0.6` still floats. For a library that determines *layout geometry*, a
   silent patch bump can shift every line break in every rendered video.
2. There is an established in-repo precedent for the alternative — `website/stage/vendor/`
   demonstrates a build-once-commit vendoring pattern with a documented rebuild recipe and a
   recorded source commit. The same pattern would apply cleanly here.

---

## F5 — NATS subject registry drift

```bash
grep -c "a2ui" pmoves/contracts/topics.json
# 2   (both lines belong to the single entry a2ui.render.completed.v1)
```

In use or documented but **unregistered**:

| Subject | Where it lives | Registered? |
|---|---|---|
| `a2ui.render.v1` | `bridge.py:36` (+ dynamic `a2ui.render.v1.<surface_id>`, `bridge.py:390`) | No |
| `a2ui.request.v1` | `bridge.py:37` | No |
| `a2ui.event.v1` | `.claude/context/nats-subjects.md:1789` | No |
| `a2ui.command.v1` | `.claude/context/nats-subjects.md:1790` | No |
| `a2ui.render.completed.v1` | `a2ui-renderer/src/index.ts:350,476,569` | **Yes** |

Credit where due: the one registered subject is registered *correctly*, with a schema
reference, and is genuinely published from three call sites.

A `nats-subject-auditor` agent and a `pmoves-nats-subject-audit` skill already exist to keep
this honest — the registry drifted anyway, which suggests the audit is not wired into a gate
that can fail.

### The two ghost subjects have never existed in code

`a2ui.event.v1` and `a2ui.command.v1` are a different class of problem from the rest of
F5. Tracing their origin:

```bash
git log --reverse -S"a2ui.event.v1" -- .claude/context/nats-subjects.md
# 1e0b727a3  2026-03-15  feat(infra): Tailscale brand defaults, ACL policy, and NATS subjects (#952)
git log --reverse -S"a2ui.event.v1" -- pmoves/docs/reviews/nats-subject-catalog-gaps.md
# 828003374  2026-03-15  fix(security): add JWT auth to 6 unauthenticated pmovesui API routes (#951)

git log -S"a2ui.event.v1" -- '*.py' '*.ts' '*.tsx' '*.js' '*.yml' '*.yaml' '*.json'
# (no output — never present in any code file, in any commit)
```

Both entered on **2026-03-15** via `pmoves/docs/reviews/nats-subject-catalog-gaps.md`, a
handoff from a Z890 security audit whose stated premise was that *"30+ NATS subjects were
found **undocumented**"* and whose action item was to register them. The catalog entry
followed the same day.

**For these two the premise does not hold.** They were never in code — not then, not since,
not in any commit. The gaps review lists their subscriber as the A2UI NATS bridge, and
`bridge.py` has never referenced them either. They were intent written up as discovery.

The consequence is that `.claude/context/nats-subjects.md` — the canonical catalog agents
are told to consult — has asserted for five months that the bridge handles UI events and
user commands. It does not.

**Recommendation:** delete both entries, or re-label them `PROPOSED — no implementation`.
Registering schemas for them would harden a contract that nothing has ever spoken. This is
distinct from `a2ui.render.v1`, which is real, cross-submodule, and genuinely under-registered.

---

## F6 — The renderer's README documents inputs it does not have

`pmoves/services/a2ui-renderer/README.md` states:

> Renders A2UI message streams (`comfy.collab.*.v1` NATS subjects) …
>
> ## Inputs
> - `comfy.collab.prompt.v1` — design intent (style, motion language)
> - `comfy.collab.progress.v1` — render progress updates
> - `comfy.collab.artifact.v1` — final artifact notification

The code contains none of it:

```bash
grep -rn "subscribe\|comfy.collab" pmoves/services/a2ui-renderer/src/ | wc -l
# 0
```

The service is **HTTP-in, NATS-out**. Its real surface is:

| Route | Guards |
|---|---|
| `GET /healthz` | none |
| `GET /metrics` | none |
| `POST /render` | `renderLimiter`, `requireAuth` |
| `POST /render/chart` | `renderLimiter`, `requireAuth` |
| `POST /render/provenance` | `renderLimiter`, `requireAuth` |

It publishes `ingest.file.added.v1`, `a2ui.render.completed.v1`, and
`agent.graphiti.signed.v1`.

**Risk:** the Creator-pipeline documentation implies an event-driven seam that does not
exist, so anything built expecting the renderer to react to `comfy.collab.*` will wait
forever.

---

## F7 — The renderer has no CHIT coverage entry

```bash
grep -c "a2ui-renderer\|8107" pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md
# 0
```

`CHIT_INTEGRATION_STATUS.md` documents the **bridge** thoroughly (§6: consumer-edge
signature gate via `cgp_passes_signature_gate()` / `verify_cgp`, tampered packets always
dropped when a key is set, unsigned dropped under `CHIT_REQUIRE_SIGNATURE`, rejections
counted in `a2ui_geometry_events_rejected_total`, tests in `tests/test_signature_gate.py`).
That is a genuinely good gate.

The renderer has **no entry at all**. It does enforce JWT (`jwt.verify` against
`SUPABASE_JWT_SECRET`) plus rate limiting, which is real protection — but there is no CHIT
signature verification on render *input*, and the renderer's output feeds
`POST /render/provenance` and `agent.graphiti.signed.v1`. Unsigned input flowing into a
provenance artifact path is the gap worth closing.

---

## F8 — A room manifest pins an "active" app whose route is not in the tree

`website/stage/data/room-layouts.json` declares:

```json
{
  "id": "pretext-casestudies",
  "route": "/persona/pretext",
  "provider": "pmoves-pretext",
  "pinned": true,
  "status": "active",
  "active": true
}
```

But nothing serves that route from the static tree:

```bash
find website/persona -type f
# boot.js  persona-resolver.js  persona-theme.js  showtime-live.js  surface-cf.js
grep -n "persona" website/_redirects        # no matches
```

No document, no redirect, and no route-resolution logic in `stage.js` or `persona/boot.js`.

Note the **honesty asymmetry within the same file**: the sibling entry `remotion-walkthrough`
(`provider: a2ui-renderer`, `route: /persona/walkthrough`) correctly declares
`"status": "planned"`, `"active": false`. The pretext entry claims active and pinned.

**Caveat, stated deliberately:** this manifest is consumed by the OpenRoom shell adapter
(`2c4ad95db feat(rooms): manifest→OpenRoom shell layout adapter (layer 4)`), which is the
Mavis-5090 lane. Whether that shell resolves `/persona/pretext` at runtime was **not
verified** — this audit only establishes that the route is absent from the static website
tree. Confirm with that lane before treating it as a defect.

---

## F9 — DoX advertises A2UI v0.9 and emits v0.8

`PMOVES-DoX` is a fourth A2UI participant that the first pass of this audit
missed. It matters because its declared version and its actual output disagree.

**What it advertises** (`backend/app/api/routers/a2a.py:231`), in its A2A agent
capability:

```python
uri="https://a2ui.org/a2a-extension/a2ui/v0.9",
params={"supportedCatalogIds":
    ["https://a2ui.dev/specification/v0_9/standard_catalog.json"]}
```

**What it emits** (`backend/app/services/a2ui_service.py`):

```python
{"surfaceUpdate": {...}}                              # v0.8 message name
{"Text": {"text": {"literalString": ...}, "usageHint": ...}}   # v0.8 component shape
```

Nested component key, `literalString` wrapper, `usageHint`, and the
`beginRendering` / `surfaceUpdate` pair are all **v0.8**. Under v0.9 the same
component is flat — `"component": "Text"` with a bare `text` and `variant`.

An A2A client that honoured the advertisement would fetch the v0.9 catalog,
expect flat components, and receive nested ones. It would also expect
`ChoicePicker` where DoX can only produce `MultipleChoice`.

DoX also has a live NATS seam: `frontend/app/a2ui/page.tsx:42` subscribes to
`a2ui.render.v1` — the same unregistered subject from § F5, which makes that
registration gap a **cross-submodule** contract gap rather than an internal one.

**This is a two-string defect, not an architecture defect.** See the
reconciliation scope below.

## Reconciliation scope — what one spec version would cost

Establishing the actual spread:

| Component | Emits / renders | Evidence |
|---|---|---|
| `a2ui-nats-bridge` | v0.8 | `A2UI_BEGIN_RENDERING`, `A2UI_SURFACE_UPDATE` |
| `website/stage/` + `a2ui.mjs` | v0.8 | `public-rooms.json` uses `literalString` / `usageHint` |
| A2UI editor (`tools/editor`) | v0.8 | imports `v0_8` from `@a2ui/lit` |
| `PMOVES-DoX` generator | v0.8 | `a2ui_service.py` |
| `PMOVES-DoX` agent card | **advertises v0.9** | `a2a.py:231` |

**Everything that actually moves bytes is already v0.8.** The only v0.9 in the
system is a pair of metadata strings in one file.

There is also a hard constraint on moving the other way: `@a2ui/lit` implements
**only** v0.8 — `renderers/lit/src/` contains a single `0.8` directory. Upgrading
the web surface to v0.9 is therefore blocked on upstream renderer support that
does not exist yet, regardless of what PMOVES decides.

**Recommended reconciliation — correct the advertisement, do not migrate.**

1. Change the two strings in `a2a.py` to the v0.8 extension URI and the v0.8
   catalog id, so DoX advertises what it emits. Effort: minutes.
2. Add a regression test asserting the advertised catalog version matches the
   version `a2ui_service.py` generates, so the two cannot drift apart again.
3. Register `a2ui.render.v1` (§ F5) — it is now known to be a cross-submodule
   contract between the bridge and the DoX frontend.

**Explicitly not recommended:** migrating the estate to v0.9. It would buy
nothing today, and the web renderer cannot follow.

## What is already right

Worth protecting during any remediation:

- **Vendored bundle is in sync.** `website/stage/vendor/README.md` records source commit
  `2d961ba2…`, which matches the `PMOVES-A2UI` submodule HEAD exactly. No drift.
- **The bundle's safety property is documented *with its verification command*** —
  `grep -c "eval(" a2ui.mjs` (0) and a URL extraction that yields only license strings. A
  claim that ships with its own test is the right pattern.
- **The bridge's CHIT gate is real**, tested, and emits a rejection metric.
- **The renderer is well instrumented** — `summarizeLayoutUsage()` exports `text_elements`,
  `pretext_elements`, `debug_layout_elements`, `bounded_text_elements`, and the set of
  engines in use. That telemetry is what made F3 precisely diagnosable.
- **Render routes are authenticated and rate-limited.**

---

## Recommended sequencing

Ranked by *(unblocks-others × risk-if-ignored) ÷ effort*. Items 1–4 are documentation and
config only.

| # | Action | Findings | Effort | Rationale |
|---|---|---|---|---|
| 1 | Give the three dialects distinct names in docs + contracts | F1 | S | Every downstream conversation, brief, and handoff is ambiguous until this lands. Zero code risk. |
| 2 | Correct the two false doc claims | F2, F6 | S | They actively mislead implementers today. |
| 3 | Register the four missing subjects in `topics.json`; wire the subject audit into a gate that can fail | F5 | S | The auditor exists but drift happened anyway. |
| 4 | Resolve `Pmoves-pretext`: vendor it or drop it; pin `0.0.6` exactly | F4 | S | Removes an advertised-but-absent dependency before anyone builds on it. |
| 5 | Reconcile the room manifest with reality (with the 5090 lane) | F8 | S | Cheap once ownership is confirmed. |
| 5b | Correct DoX's advertised A2UI version to match what it emits, + a drift test | F9 | S | Two strings. Everything that moves bytes is already v0.8. |
| 6 | **Extract pretext into a shared layout module used by both web and video** | F3 | M | The substantive enhancement. Interface is already correct and already browser-safe. |
| 7 | CHIT-gate the renderer; add it to `CHIT_INTEGRATION_STATUS.md` | F7 | M | Closes unsigned input into a provenance path. |
| 8 | Protocol → Animation adapter | F1 | L | **Do not start without answering the question below.** |

### On item 8 — apply YAGNI first

Before anyone builds an adapter from A2UI Protocol messages to the Animation schema, answer:
**does a live agent-driven UI surface ever genuinely need to become a video?**

If the honest answer is no, then F1 is fully resolved by item 1 (renaming) at a fraction of
the cost, and the two systems should be allowed to stay separate. Converging schemas that
only ever shared a prefix by accident would add a permanent maintenance seam to buy nothing.

Item 6 delivers most of the "one consistent output" value on its own, because shared *text
layout* is what makes web and video agree visually — shared *message schema* is not required
for that.

---

## Coordination

The 5090 node (Mavis) is active in adjacent territory — OpenRoom, room manifests, website/UI,
and living docs. Overlap points to negotiate before executing:

- **F8** sits inside the OpenRoom manifest lane. Confirm ownership first.
- **F2** touches `website/stage/` and `pmoves/contracts/`, both live surfaces for that lane.
- Items 1–3 are repo-wide doc/contract edits and will conflict with any concurrent edit to
  the same files.

The Active Claim Register (`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`) has no entries after
`2026-07-31`, so it does not currently reflect in-flight August work. Treat its silence as
missing data, not as an all-clear.

---

## Verification status

**Verified by direct read at `f27d43ed6`:** F1, F2, F3, F4, F5, F6, F7, F8 — each with the
command recorded inline above. All findings were re-run against this commit rather than
carried forward from the earlier baseline.

**Explicitly not verified:**

- No services were started. Nothing here is live-behaviour evidence.
- Whether the OpenRoom shell resolves `/persona/pretext` at runtime (F8 caveat).
- Whether `@a2ui/lit` is published to a public npm registry.
- Runtime behaviour of the CHIT gate — the code and tests were read, not executed.

**Known limitation of this audit:** a static read cannot prove absence of runtime wiring, only
absence of source references. F6's claim that the renderer has no subscribers is strong
(zero `subscribe` calls in `src/`), but a dynamic subscription constructed at runtime from
config would not appear in that grep. No such mechanism was found.
