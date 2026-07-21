# PR #2134 LEARNINGS — A2UI v0.2 implementation (review-style trim)

> CodeRabbit/Codex/peer-CLAUDE review threads are a learning signal, not just a
> fix candidate. This file is the persistent, agent-readable record of what PR
> #2134 taught us — readable cold on any node with no GraphQL access.

---

## PR metadata

| Field | Value |
|-------|-------|
| PR number | `#2134` |
| Branch | `feat/a2ui-v02-impl-review-style` |
| AGNOTE CLAIM | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (a2ui-v0.2 lane) |
| AGNOTE RELEASE | pending signoff |
| Conformance pre-PR | `19/19 python (pmoves/tools/compose/tests)` |
| Conformance post-trim | `19/19 python` |
| Reviewer surfaces | peer CLAUDE (verified findings) |
| Trim mode | batch (7 logical commits) |
| CHIT trail sign | pending `/chit:sign-trail` |

## Thread classification (5-class spine, extended)

This PR: **6** verified review findings (all legitimate).

| Class | Count | Notes |
|-------|-------|-------|
| Legitimate (real bug/drift) | 6 | all fixed — commits A–F |
| Already-fixed (in HEAD) | 0 | — |
| Owner-addressed (rationale accepted) | 0 | — |
| Out-of-scope (separate PR) | 0 | — |
| Pre-existing (not introduced) | 0 | — |

---

## Bucket 1 — missed-signal (what the reviewer saw that we missed)

### `pm-ballot:castVote-async-in-sync` — dead vote button (P1)

- **What the reviewer flagged:** `castVote()` was synchronous but called the
  async `_hashReceipt()` without `await`, so `receiptHash` was a Promise and
  `.slice(0,16)` threw a TypeError — NO vote could ever be cast, no receipt, the
  `vote-cast` event never fired.
- **Why we missed it:** the conformance gate is render-only (Python compose
  tests). Nothing clicked the button. The component "rendered" green while the
  primary interaction was dead.
- **What we changed:** commit A (`5b5c480883`) — made `castVote` async, awaited
  the hash; the click handler now disables the button during the async cast and
  `.catch()`es to an inline `status-error` state.
- **Upstream fix to prevent recurrence:** browser ballot-flow verification is
  deferred to the parent session (see conformance delta); the render-only gate
  cannot catch async-in-sync call-site bugs.

### `pm-ballot:FNV-silent-downgrade` — receipt lies about crypto (P2)

- **What the reviewer flagged:** `_hashReceipt` silently falls back from
  `crypto.subtle` sha256 to non-cryptographic FNV-1a on non-secure contexts, but
  the receipt UI still told the voter to verify with sha256 and claimed the vote
  was "signed and recorded in the public CHIT trail" while `signature` is a
  `chit-stub:` placeholder.
- **Why we missed it:** the fallback path only executes off a secure context —
  never exercised in the happy-path demo.
- **What we changed:** commit A — `_hashReceipt` returns `{ hash, algo }`; the UI
  omits the sha256 verify instruction and says "non-cryptographic local demo
  checksum" on the FNV path, and both paths soften to "recorded (CHIT signature
  pending signing-card registration)". Added `TODO(v0.2 spec §5.4 rev):
  nonce-commitment receipts` (spec amend landing in PR #2133).

### `a2ui-deploy:blank-deployed-page` — deploy root never tested as deployed (P1)

- **What the reviewer flagged:** the renderer imported
  `../../pmoves/web-components/register.js`, which escapes the CF Pages root
  (`website/tenant-template/`) → 404 on the deployed site, components never
  register, every deployed tenant page renders blank. Local proofs passed only
  because pages were served from the repo root.
- **Why we missed it:** "works from repo root" was mistaken for "works from
  deploy root" — the two contexts have different module-resolution roots.
- **What we changed:** commit D (`e0dcb1dff6`) — `ensureRegistered()` tries
  `./components/register.js` first (staged under the deploy root) and falls back
  to the dev path; `deploy-tenant` stages template + a copy of `web-components`
  into `.a2ui-stage/<tenant>/components` before `wrangler pages deploy`.

### `tenant-renderer:method-allowlist` — arbitrary method invocation (P2)

- **What the reviewer flagged:** `wireEvents` whitelisted the event NAME but not
  the method — `target[method](arg)` could invoke ANY function-valued property on
  any element by id from tenant JSON.
- **Why we missed it:** the wire format looked constrained (only 3 event names)
  so the method side wasn't scrutinized.
- **What we changed:** commit C (`8c4c5f1d7f`) — `ALLOWED_METHODS = {show,
  pulse}`, warn+skip otherwise.

### `a2ui:CDN-in-website` — external media in a self-host-only tree (P2)

- **What the reviewer flagged:** both tenant fixtures/data loaded
  `images.unsplash.com` + an `archive.org` mp3; repo rule is website/ self-hosts
  everything.
- **Why we missed it:** the fixtures were seeded with placeholder CDN URLs during
  authoring and never swapped for self-hosted assets.
- **What we changed:** commit E (`4620344f65`) — self-hosted placeholder SVG +
  4s silent mp3, honest captions/titles, regenerated data JSON. Zero `https?://`
  remain in either shipped data JSON.

### `a2ui-hook:subject-unregistered` — advisory subject not in catalog (P3)

- **What the reviewer flagged:** `branch.<branch>.a2ui.trail.v1` was published by
  the hook but not registered in `nats-subjects.md`; audit-lane consumers of
  `branch.>` had no way to know it is unsigned.
- **Why we missed it:** the hook was mirrored from shift-crew but the subject-doc
  step wasn't.
- **What we changed:** commit F (`00010e3258`) — registered the subject, flagged
  ADVISORY/UNSIGNED (no spec/signing_card_id/HMAC).

## Bucket 2 — fix-pattern (patch the generator, not the symptom)

### Pattern: "async-in-sync call site" (await dropped at the caller)

- **First seen:** PR #2134, commit A.
- **Recurrence count (this PR):** 1 (`castVote` → `_hashReceipt`).
- **Root cause:** a method was made `async` (for `crypto.subtle`) but a
  synchronous caller kept treating its return as a value. Render-only tests can't
  catch this — the Promise stringifies without throwing until it's `.slice()`d.
- **Generator fix:** any component method that touches `crypto.subtle` (async)
  must have every call site awaited; interactive handlers must be exercised by a
  browser conformance pass, not just render assertions.

### Pattern: "works from repo root" ≠ "works from deploy root"

- **First seen:** PR #2134, commit D.
- **Recurrence count (this PR):** 1 (relative `../../` import escaping CF root).
- **Root cause:** local proofs served from the repo root resolve `../../pmoves/`
  paths that a deployed subtree cannot. The deploy artifact must be self-contained
  under its own root.
- **Generator fix:** deploy targets stage a self-contained bundle (components
  copied under the deploy root) and the renderer prefers the co-located path.

## Bucket 3 — wrong-suggestion (the reviewer's reasoning was off)

- None this cycle — all six findings reproduced and were legitimate.

## Bucket 4 — already-addressed (signal our PR description is unclear)

> These were already correct in HEAD before this trim — recorded so we don't
> "re-fix" them and so the strengths are visible.

- **pm-ballot escaping complete:** `_escapeText` / `_escapeAttr` are applied to
  all string props in `pm-ballot.js` render — no XSS via choice label.
- **pm-toast textContent (no HTML):** `show()` uses `textContent`, never
  `innerHTML` — the body-wipe bug (commit B) was a container-vs-span target
  error, not an escaping error.
- **hook exit-0 discipline:** both trail hooks always `exit 0` and suppress
  stderr on the a2ui side; advisory, never block a tool call.
- **fail-fast deploy-all:** `deploy-all-tenants` stops on first failure
  (`|| exit 1`) rather than silently skipping a broken tenant.

---

## Conformance delta (pre-fix → post-fix)

| Surface | Pre-trim | Post-trim | Delta |
|---------|----------|-----------|-------|
| Python tests (`pmoves/tools/compose/tests`) | 19/19 | 19/19 | 0 |
| Browser ballot flow (click → receipt) | not run | deferred to parent session | n/a |
| External URLs in shipped data JSON | 4 (2 img + 2 mp3) | 0 | −4 |

> Browser ballot verification (actually clicking Cast vote and checking the
> receipt renders) is deferred to the parent session in Chrome — the render-only
> Python gate cannot exercise the async interaction that commit A fixed.

## Trail sign

```
make -C pmoves sign-trail \
  SUMMARY="PR #2134 Trim: fixed 6 verified findings (A–F), conformance 19/19→19/19, browser ballot deferred"
```

---

## See also

- `.claude/hooks/a2ui-crew-trail.sh` — companion hook that emits the advisory
  NATS trail on a2ui file edits (subject registered in this trim)
- `.claude/context/nats-subjects.md` — `branch.<branch>.a2ui.trail.v1` entry
- `pmoves/tools/compose/compose.py` — `A2UI_VERSION` (source of the stamped
  `a2uiVersion`, bumped 0.1 → 0.2 in commit E)
