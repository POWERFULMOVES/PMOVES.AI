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

---

## Addendum — upstream provenance, and the pattern is repo-wide

Added after research (`cipher-provenance`), then re-verified locally. The rule
applied: *the specs are set by the parts it is comprised of* — provenance docs,
example code, the code it was built from.

### Upstream has no revoke to inherit

| | |
|---|---|
| upstream | `campfirein/cipher`, rebranded **ByteRover CLI** (`byterover-cli` v3.16.1) |
| fork distance | 798 ahead / 3097 behind; the "ahead" commits are **stale upstream code, not PMOVES work** (`TAC_CIPHER.md:260`) |
| genuine PMOVES additions | 6 commits on fork `main` + 2 on `PMOVES.AI-Edition-Hardened` |

Upstream **does** ship auth — `token-store.ts`, OAuth/OIDC, PKCE, refresh
exchange — but for ByteRover's own SaaS login, not the REST surface.
`TAC_CIPHER.md:273` states the split outright:

> `Auth | Bearer middleware (PMOVES-added) | OAuth + API key for ByteRover cloud sync (not REST middleware)`

And upstream has **no revoke concept either**: `ITokenStore` exposes only
`clear/load/save`; `brv logout` hard-clears the local credential file. There is
no "retire this token while others stay live" anywhere upstream. So the PMOVES
REST auth surface — and its revocation — is PMOVES-owned end to end. There was
no upstream pattern to match, which is why inventing one here is correct rather
than presumptuous.

### FOUR parts specify revocation; the doc was the outlier

| part | anchor |
|---|---|
| column | `20260728100000:10` `revoked_at TIMESTAMPTZ NULL` |
| index **built for it** | `:19-21` `ON (agent_id, revoked_at)` — *"Agent index for audit and revocation"* |
| middleware enforces it | `auth.ts:68` filter + `:122` 401 |
| **grant permits it** | `:48` `GRANT SELECT, INSERT, UPDATE, DELETE` — **issuance alone never needs UPDATE** |

`TAC_CIPHER_VILLAGE.md` mentions revocation once, as a column name. Four parts
against one passing mention: the parts are the spec.

### The gap is repo-wide, not a cipher quirk

Three tables declare `revoked_at` and, before this change, **nothing in the tree
ever set any of them**:

- `20250108000000_remote_access.sql:141`
- `20260802000000_voice_cloning_provenance.sql:39-40` (also `revoked_reason`)
- `20260728100000_cipher_agent_tokens.sql:10`

Verified: the only writer of `revoked_at` anywhere is
`pmoves/scripts/revoke_cipher_token.py`, added here. Soft-revocation was
designed three times and implemented zero times. The other two remain open and
are **not** closed by this change.

### Prior art checked and deliberately NOT copied

`yt_oauth_flow.py:561-584` (`cmd_revoke`) revokes at the external IdP and then
**hard-deletes** the row. That is a different pattern and the wrong one here:
cipher's schema keeps the row and stamps `revoked_at`, which is what preserves
*when* a credential was retired — the one fact a compromise audit needs.

### Open, and not decided here

`cipher_access_log` is granted `SELECT, INSERT` only (append-only by grant).
Whether a revocation should write an event there is undecided: the table
documents *"authenticated cipher tool usage"*, and an operator revoking a token
is not that. Left for the operator rather than assumed.
