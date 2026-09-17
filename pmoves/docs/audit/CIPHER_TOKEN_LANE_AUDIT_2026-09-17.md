# Cipher token lane — anchored audit

GRAPHITI_MARK: `PHI-4482-CIPHER::TOKEN-LANE-AUDIT::2026-09-17`

> **Method:** every claim below is a thumbtack to ONE anchor — a file:line or a
> re-measured command — not to the surrounding narrative. Anything that could
> not be pinned is marked so. Re-measured 2026-09-17 on z890; nothing is cited
> from memory.
>
> **Why this file exists:** three claims made about this lane in session were
> wrong or imprecise, and two of them were mine. An audit that maps back to
> anchors is checkable by the next agent without re-deriving the story.

## Design source

`pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` § Phase B PR 2 (lines 78-86) — cited by
the migration header itself.

## The anchors

| # | Claim | Anchor | Verdict |
|---|-------|--------|---------|
| 1 | The stored row **is** the bearer | `mint_cipher_token.py:123` `token = f"cipher_{token_uuid.hex}"` + `:127` `"token_uuid": str(token_uuid)` | **proven** |
| 2 | No hash column exists | `20260728100000_cipher_agent_tokens.sql` — `grep -c hash` = **0** | **proven** |
| 3 | Only one cipher-token migration | `ls migrations \| grep -ci cipher.*token` = **1** | **proven** |
| 4 | Enforcement honours revocation | `auth.ts:68` `?token_uuid=eq.${uuid}&revoked_at=is.null` | **proven** |
| 5 | Revoked tokens are rejected | `auth.ts:122` `401 'Unauthorized — invalid or revoked token'` | **proven** |
| 6 | **Nothing sets `revoked_at`** | tree-wide grep over `*.py *.sh *.mk *.ts *.sql`: occurrences are DDL (3), two test fixtures, two unrelated migrations. **No UPDATE/PATCH anywhere** | **proven by absence** |
| 7 | The spec **mandates** printing the token | `TAC_CIPHER_VILLAGE.md:86` "→ prints token" | **proven** |
| 8 | The spec mandates a mint endpoint | `TAC_CIPHER_VILLAGE.md:82` `POST /api/agents/mint-token` (admin-only) | **proven** |
| 9 | That endpoint was never built | registered routes: `/health`, `/memory`, `/memory/:id`, `/memory/search`, `/sse`, `/messages` — no `/api/agents/*` | **proven by absence** |
| 10 | Revocation is specified as storage, never as an act | `grep -ci revoke` = **1**, and that one is `revoked_at` in the column list at `:80` | **proven** |

## What the anchors say together

**Two of three legs exist.** The schema stores revocation (1,2,3), the
middleware already honours and enforces it (4,5) — and nothing can set it (6).
This is not a missing feature. It is a system fully prepared to reject a revoked
token, with no way to revoke one. A compromised credential stays valid because
the only act that would retire it has no implementation.

**The printing is specified, not accidental** (7). Changing it silently would
put code and design doc out of sync; the spec line has to move with the code.

**The mint is a local script because its endpoint was never built** (8,9). That
is why minting needs `SUPABASE_SERVICE_KEY` in the environment — the admin-only
HTTP path the design called for does not exist, so there is no authenticated
remote way to mint.

## Constraint any revoke surface must carry

Because the stored `token_uuid` **is** the bearer (1,2), a revoke tool must never
print or list `token_uuid`. "Show me which tokens exist" would reprint every
live credential. This constraint belongs in the spec before a tool exists.

## Corrections this audit makes to claims made in session

- ~~"The mint printing the bearer is a defect."~~ It is **specified** (7). The
  remedy is to amend spec and code together, not to change behaviour silently.
- ~~"There is no revoke path at all."~~ Imprecise. Enforcement is live (4,5);
  only the setter is missing (6). The sharper statement is the true one.
- ~~"Revocation was never specified anywhere."~~ It appears once (10) — as a
  column. Specified as storage, never as an act. Stated precisely rather than
  approximately.

## Open, and deliberately not decided here

A revoke surface needs decisions this audit does not make: per-token or
per-agent; who may perform it; whether it writes `cipher_access_log`; whether it
is an endpoint (matching the unbuilt `:82` pattern) or a make target. Those are
design choices, and the design doc's silence is the gap — not the missing code.
