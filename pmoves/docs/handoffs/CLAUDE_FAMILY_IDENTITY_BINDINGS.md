# CLAUDE family identity bindings (A.12)

**Lane:** `feat/claude-family-identity-bindings` — B850-CLAUDE (Knuckles), 2026-10-08.
**Doctrine:** `plans/HYPERAGINTZ_ORCHESTRATION_SCOPE_2026-09-19.md` §A.12. PMOVES-Registry carries
harnesses (`claude-acp`), not identities. Identity travels on three substrates:
`signing_identity_cards.yaml` (WHO signs), `agent_registry.yaml` (`signature`,
`topology.node_affinity`) plus `agent-teams.yaml` (coupling), and
`node-vocabulary.yaml` (`default_identity.<harness>`, `cipher_agent_id.<harness>`), with
`identity_vocabulary.yaml` declaring the spellings and the `register_form`.
**Template:** `knuckles-kimi` — card 051 + registry `kimi_knuckles` + vocabulary binding.

## 1. Audit matrix

All structured files were parsed with `yaml.safe_load`; nothing below comes from grep.
Measured on `origin/main` @ `a477c3a7f`.

**Inputs parsed:** cards = 30 · registry agents = 111 · `external_contributors` = 18 ·
node-vocabulary nodes = 17 · identity-vocabulary identities = 23 ·
`agent_signatures.yaml` entries = 26 · teams = 14 (111 memberships).

**Family discovery:** every card `agent_id`, identity-vocabulary canonical, and registry
`signature` that ends in `-claude`. That gives six: `4090-claude`, `5090-claude`,
`b850-claude`, `z890-claude`, `spark-claude`, `cowork-claude`. `knuckles-kimi` is listed
as the template row.

| Identity | Card (active) | Registry key → `node_affinity` → canonical | Team | identity_vocabulary (node · register_form · registry key aliased) | node-vocab `default_identity.<h>` | node-vocab `cipher_agent_id.<h>` | agent_signatures | vs template |
|---|---|---|---|---|---|---|---|---|
| **knuckles-kimi** (template, h=kimi) | 051 (interim) | `kimi_knuckles` → `[pmoves-b850]` → knuckles | orchestration | knuckles · *none* · yes | `kimi_knuckles` | `knuckles-kimi` | no | — |
| 4090-claude | 012 | `claude_4090` → `[laptop-4090]` → 4090 | orchestration | 4090 · `4090-CLAUDE` · yes | `claude_4090` | `4090-claude` | yes | **complete** |
| 5090-claude | 011 | `claude_5090` → `[5090]` → 5090 | orchestration | 5090 · `5090-CLAUDE` · yes | `claude_5090` | `5090-claude` | yes | **complete** |
| b850-claude | 036 | `claude_b850` → `[pmoves-b850]` → knuckles | orchestration | knuckles · `B850-CLAUDE (Knuckles)` · yes | `claude_b850` | `b850-claude` | yes | **complete** |
| z890-claude | 010 | `claude_z890` → `[z890]` → z890 | orchestration | z890 · `Z890-CLAUDE` · yes | `claude_z890` | `z890-claude` | yes | **complete** |
| spark-claude | **MISSING** | **MISSING** | — | spark · `SPARK-CLAUDE` · n/a (no key) | **absent** (spark declares no `default_identity` at all) | **absent** | no | **gap: card, registry, team, vocab binding** |
| cowork-claude | MISSING | MISSING | — | *no node* · none | n/a | n/a | no | not a node identity (see below) |

The cipher `agentId` spelling equals the card `agent_id` on every bound row.

The four node CLAUDEs are ahead of the template on one axis: each has a `register_form`.
`knuckles-kimi` has none, so `kimi-pmoves` on Knuckles gets no register name.

**Runtime confirmation.** This runs the resolver the launcher calls, `pmoves/tools/node_identity.py --harness claude-code --shell`,
with `PMOVES_NODE_IDENTITY`, `PMOVES_CIPHER_AGENT_ID` and `PMOVES_REGISTER_IDENTITY` unset:

| `PMOVES_NODE_ID` | resolved identity | cipher agentId | register form |
|---|---|---|---|
| 4090 | `claude_4090` | `4090-claude` | `4090-CLAUDE` |
| 5090 | `claude_5090` | `5090-claude` | `5090-CLAUDE` |
| z890 | `claude_z890` | `z890-claude` | `Z890-CLAUDE` |
| knuckles | `claude_b850` | `b850-claude` | `B850-CLAUDE (Knuckles)` |
| spark | *(empty)*: "no identity is declared for harness 'claude-code' (declared harnesses: none)" | *(empty)* | *(empty)* |

### Non-gaps, recorded so they are not re-audited

- **`cowork-claude`** is a single register-name declaration (one entry). It has no `node`,
  and the vocabulary note says it is "kept rather than folded". It is not a node identity,
  and binding it to anything would invent history.
- **`b850-claude-funnel`** (second steward session on Knuckles) is register-only by
  design. It is selected with `PMOVES_REGISTER_IDENTITY=B850-CLAUDE-FUNNEL`, keeps registry
  identity `claude_b850` and cipher `b850-claude`, and gets its own register owner string.
  It needs no card or registry entry.
- **`b850-{delivery-agent,code-review,control-agent,memory-agent}`** (cards 052–055) are
  inactive body cards. They are not part of the `*-claude` family.

## 2. Safe fixes: none needed for existing identities on their home nodes

The brief allowed one class of fix: add entries that are missing for an EXISTING identity
on its EXISTING home node, where the template makes the value unambiguous. The matrix has
no such gap. Each of 4090/5090/z890/b850 carries all five bindings, plus team membership
and an `agent_signatures` entry. That covers the card, the registry entry with signature
and affinity, team membership, the vocabulary spelling with the registry key aliased, the
`default_identity`, and the `cipher_agent_id`. **No identity config file was edited in
this lane.**

The only incomplete identity is `spark-claude`. Its first missing piece is a signing card,
which this lane must not mint because cards carry key material and governance. The
proposed entries are in §3.

## 3. SPARK-CLAUDE: proposed entries (operator / SPARK-owned; NOT applied)

**Owner.** `identity_vocabulary.yaml` names the follow-up owner as SPARK-CLAUDE /
CRUSH-SPARK, and says card `00000000-0000-4000-8000-000000000014` and an
`agent_signatures.yaml` key `spark-claude` are "claimed on the SPARK node but NOT present on
main". This audit re-checked on 2026-10-08. `git grep 000000000014 origin/main -- pmoves`
hits only `identity_vocabulary.yaml` and the claim register, and no ref carries a
`spark-claude` card.

**Merge-order hazard: open PR #3078.** That PR (`chore/cli-prereq-preflight`, last updated
2026-09-21) adds `spark.default_identity: {crush: crush_spark}` with the comment that a
claude-code entry is "deliberately absent until that harness actually runs on this node".
The premise is now stale: #3235 carried 10 `SPARK-CLAUDE` / `spark-claude` register rows
onto main. Both changes write the same `default_identity:` block on the spark node, so
whichever lands second must merge the two keys rather than take one side.

Apply in this order. The gates enforce it:
`test_node_identity.py` requires every `cipher_agent_id` to name an ACTIVE card, and
`validate_agent_registry.py` §5 requires every `default_identity` to be registered,
affinity-matched and teamed.

1. **`pmoves/config/signing_identity_cards.yaml`** (operator issues). The shape is
   card 011 / 051. Glyph and colour are the operator's choice. Spark's runner card
   (034) uses `#EA580C`, so pick something distinct:
   ```yaml
   - card_id: "00000000-0000-4000-8000-000000000014"
     issued_at: "<issue time>"
     active: true
     ml:
       primary_method: github-app
       github_app_installation_id:
       ci_runner_label:
     h:
       agent_id: "spark-claude"
       display_name: "SPARK Claude"
       glyph: "<operator>"
       color: "<operator>"
       voice: terse
       role: agent
     metadata:
       created: "<date>"
       interim: true
       notes: >-
         Claude Code harness identity on the SPARK (DGX GB10) node. Interim pending
         operator key issuance.
   ```
2. **`pmoves/config/agent_signatures.yaml`**: add a `spark-claude:` entry. This is the H-half
   sync source named in the card file header.
3. **`pmoves/config/agent_registry.yaml`**: append `spark-claude` to
   `external_contributors`, then add the entry:
   ```yaml
     claude_spark:
       name: "SPARK Claude"
       class: standard
       primary_type: ui
       secondary_type: agent
       port: null
       health: null
       layers: [L0, L2, L4]
       evolution_stage: stage_1
       signature: spark-claude
       nats:
         publishes: []
         subscribes: []
       topology:
         node_affinity: [spark]
         team: orchestration
         ci_runner: null
         compose_profile: null
       description: "SPARK/DGX-GB10 node Claude Code CLI identity"
   ```
4. **`pmoves/configs/agent-teams.yaml`**: add `claude_spark` to `orchestration`.
5. **`pmoves/config/identity_vocabulary.yaml`**: add `claude_spark` to the `spark-claude`
   aliases. It is needed so `resolve_register_name` can look the registry key up.
6. **`pmoves/configs/node-vocabulary.yaml`**, on the `spark` node:
   ```yaml
     default_identity:
       claude-code: claude_spark
       crush: crush_spark          # only if #3078 has landed
     cipher_agent_id:
       claude-code: spark-claude
   ```
7. **On SPARK:** set `PMOVES_NODE_ID=spark` in `.claude/settings.local.json` `env`, or rely
   on a hostname alias. Mint the per-agent cipher token per
   `pmoves/docs/operations/CIPHER_AUTH_RUNBOOK.md` §2. That is an operator step.

## 4. Runbook: binding a CLAUDE identity on a NEW node (e.g. a St Maarten host)

### What the launcher reads

`claude-pmoves.sh:144-145` sources `pm-node-identity.sh` and calls
`pm_node_identity "$ROOT" claude-code claude-pmoves`. That function:

1. needs a Python with `yaml` (`pm_pick_python yaml`, which tries `.venv-pmoves`,
   `python3`, `py -3`, then `python`). Without one the session launches unbound.
2. takes `PMOVES_NODE_ID` from the environment, or else from `.claude/settings.local.json`
   → `env.PMOVES_NODE_ID`.
3. runs `pmoves/tools/node_identity.py --harness claude-code --shell`, which resolves in
   three separate namespaces:
   - **node:** `PMOVES_NODE_ID` first, falling back to the hostname. The value must be a
     canonical name or alias in `node-vocabulary.yaml`. Measured with
     `PMOVES_NODE_ID=st-maarten`, the resolver answered "`'st-maarten'` is not a declared
     node name. Add it as an alias in node-vocabulary.yaml".
   - **registry identity:** `PMOVES_NODE_IDENTITY`, if set.
     - It must name a registered agent, and it binds on any machine node.
     - When the node is outside the agent's `node_affinity`, the explanation records
       "off-affinity on <node>". Affinity is a preference, not a gate.
     - Otherwise `<node>.default_identity.claude-code` is used. That auto-binding still
       requires the default's affinity to claim the node.
   - **cipher agentId:**
     - When the bound identity is the node's default, it is
       `<node>.cipher_agent_id.claude-code`.
     - Otherwise it is the `cipher_agent_id` declared beside that identity on its home
       node. The card follows the identity.
     - Declared, never derived.
   - **register name:** the `identity_vocabulary.yaml` entry whose canonical or alias
     matches the registry key, and which has a `register_form`.
     - On its home node: the declared `register_form`, unchanged.
     - On any other node: `<BASE> (<fact>)`. The `<fact>` is the declared
       `node_relations` token if one exists, and otherwise the node's canonical name.
4. then `pm-cipher-identity.sh` checks the cipher id against a signing card and the
   `CIPHER_API_TOKEN` visible to the process.

**The aggregate model (operator correction, 2026-10-08).** "node_relations are not the
determinant of identity. Identity is the collection aggregate that may or may not include
a node." That aggregate is:
- the signing card
- the signature
- alters (`agent_signatures.yaml` `alters`, identity_vocabulary `alter_lineage`)
- roles
- lineage
- the ACK trail

A node is a FACT about a session, never a permission to be the identity. Nodes differ in
depth: some are tip-only, some host the mesh, some join it. A node may also spawn new
alters or roles for the work done there.

So a new node gets its own default identity (the table below), AND any existing identity
can be worn there. Two earlier write-ups of this are superseded:
- "Option A vs Option B" was a false choice.
- "Resolve only through a declared mirror" was the wrong premise.

### Wearing an existing identity on node X (e.g. B850-CLAUDE on a St Maarten host)

To wear B850-CLAUDE on node X:
1. Node X must be in `node-vocabulary.yaml`. Its node fact has to be nameable;
   placeholders and classes such as `cloud` or `jetson` still do not bind.
2. Launch with `PMOVES_NODE_IDENTITY=claude_b850`.

Nothing else is needed:
- **No `node_affinity` edit.** The binding is recorded as `off-affinity on X`.
- **No `node_relations` row.**
- **No `cipher_agent_id` on X.**

Result, from fixtures in `pmoves/tests/test_node_identity_worn.py`:
- identity `claude_b850`
- cipher `b850-claude` (the card follows the identity, not X's default)
- register form `B850-CLAUDE (X)`

**Optional annotation.** A `node_relations` row `{token, node: X, mirrored_from: knuckles}`
in `identity_vocabulary.yaml` replaces the node name in the owner string with the token,
used verbatim. That is what happens to the one real row today: on 5090,
`PMOVES_NODE_IDENTITY=claude_z890` signs as `Z890-CLAUDE (Z890-mirror-on-5090)`. If two
rows declare the same mirror, neither token is used: the node name is, and the
explanation names both tokens.

**Spelling of the node fact.** The node's canonical name from `node-vocabulary.yaml` (e.g.
`B850-CLAUDE (spark)`, `Z890-CLAUDE (knuckles)` on the real files). I did not invent it.
identity_vocabulary's parenthetical doctrine lists the node as one of the parenthetical's
declared kinds, with examples `Z890`, `SPARK` and `Knuckles`. `identity_lineage.wearing()`
also already parses any node alias there as `node`: `wearing("B850-CLAUDE (5090)")` gives
`node=5090` with nothing unclassified. The home node is unchanged: its declared form
`B850-CLAUDE (Knuckles)` is still used there.

**`PMOVES_REGISTER_IDENTITY` keeps its same-node rule.** It names a second session's BASE
on its own node. It renames only the register owner string. If it named another
identity, the session would sign as one aggregate while cipher and the registry carry a
different one. Wearing another identity is `PMOVES_NODE_IDENTITY`, which moves all three
namespaces together.

### Two sessions of one identity: owner strings, and the collision gate

The resolver now gives two concurrent sessions of one identity DISTINCT owner strings
across nodes, e.g. `B850-CLAUDE (Knuckles)` and `B850-CLAUDE (spark)`. On the same node a
second session still needs a distinct BASE via `PMOVES_REGISTER_IDENTITY`.

**FIXED in #3313 (2026-10-08).** Before the fix the collision gate folded them together.
The fold happens in `.claude/hooks/governance/claim-collision-pre.py`:
- `canonical_owner()` mapped every owner string through
  `identity_lineage.canonical_identity`, which strips the parenthetical.
- `_pair_register()` keys open claims on that fold (and `register_status.py` /
  `register_append.py` read through the same `canonical_owner()` / `open_claims_in()`).

So `B850-CLAUDE (spark)` and `B850-CLAUDE (Knuckles)` were one owner there, and a bare
RELEASE by either closed both sessions' lanes. This is the cross-node form of the
2026-09-26 B850-CLAUDE-FUNNEL incident.

**Keying the gate on the full register form would NOT close it safely.** I measured this
over the real register: 766 CLAIM/RELEASE rows, 64 distinct owner strings. 9 identities
are written under more than one string, 50 strings in all. B850 alone uses `(Knuckles)`,
`(Knuckles, opus 4.7 1M)`, `(Opus 5)` and `(Claude Opus 5)`. The fold exists so that a
RELEASE under one spelling closes a CLAIM opened under another. Keying on the full string
reintroduces exactly the defect that left a lane open for a week.

**The key that would close it** is `(canonical identity, wearing().node)`, where an absent
node token defaults to the identity's declared home node. Measured over the same 766 rows,
**0 rows** carry a node token other than their identity's home, so this key re-pairs no
existing row. It separates only worn sessions, which do not exist in the register yet.

**Implemented in #3313** as exactly that key. `canonical_owner()` returns the bare canonical
identity for every home spelling (unchanged from before), and `` <identity>`@<node> `` (a key no raw owner string can spell; see `NODE_KEY_SEP`) only
when `identity_lineage.wearing()` finds a declared MACHINE in the parenthetical (a
node-vocabulary alias, or a `node_relations` token such as `Z890-mirror-on-5090` -> 5090)
that is not the identity's home. Stays folded, by design: no node named (`(Opus 5)`),
and non-machine words (`(any)`). An unreadable node vocabulary, or an ambiguous
parenthetical, is asked about rather than folded silently. Corpus control on
origin/main's register: 792 owner reads (390 CLAIM, 382 RELEASE, 20 co-owner; 69 distinct
strings), **0** keys changed, open claims 73 -> 73 with an empty symmetric difference.
Pinned by `pmoves/tests/test_claim_collision_hook.py` (the "One identity, two machines"
block).

**No-home identities split too (operator decision 2026-10-08).** The node a session runs on
is a measured fact (launcher node resolution, bootstrap probes); the model is never part of
the key (crush runs a newer GLM and still idents as crush_glm_5.2). So `claude-opus`,
`crush`, `hermes-agent` and any drop-in identity with no declared home get
`` <identity>`@<node> `` when the parenthetical names a real node (including a
`node_relations` token), and the bare key when it names none. Corpus control on origin/main
347e354a1, old key (ac51e81c1) vs new: 792 owner reads (69 distinct strings); **47 reads /
9 distinct strings** change key (claude-opus, crush, hermes-agent node spellings); open
claims **73 -> 74**, 0 peer closes either way, 0 real owners on the ask path.

**Finding: register row 1795 reopens, correctly.** `CLAIM CRUSH-GLM52 (SPARK)` on
`feat/cipher-agent-scope` (2026-07-28) was closed under the old fold by row 1849, a bare
`CRUSH` RELEASE filed on Knuckles about a different PR; `feat/cipher-agent-scope` has no PR.
That is the #3313 defect in the old ledger: one machine's session closed another's lane.
No RELEASE is filed for it here; the coordinator is raising it with crush/spark.

### Binding is attribution, not authentication

**Nothing in this resolver proves that a session IS the identity it names.** Once the node
gate is gone, `PMOVES_NODE_IDENTITY=claude_b850` alone makes any session on any node
B850-CLAUDE:
- in the registry namespace
- in the register owner string
- in the cipher agentId it is told to use

The node gate never authenticated anything either: it read the same env var and a
hostname. But it at least narrowed where a wrong claim could come from. Without it the
claim is purely declarative. Every output here is **attribution**: a name the session
carries. None of it is **authentication**: proof that the session holds that name.

Cipher's per-agent token is not a substitute. It is a bearer secret, and
`CIPHER_AUTH_RUNBOOK.md` §5 records that MCP has no per-agent authorization. It also
proves possession of a token, not of an identity. The CHIT trail MAC is a deployment-wide
key, so it names a signer without proving which one.

**Target design** (design note only; nothing implemented):
- **An identity key.** Each identity card carries an Ed25519 public key. That fits
  `ml.ssh_fingerprint` / `ssh_allowed_signers_line`, or a dedicated `ml.ed25519_pub`.
- **Where the private key lives.** With the identity's holder, not the node. A worn
  identity carries its key to the node it is worn on, which is what makes "the identity
  is the aggregate" verifiable rather than declared.
- **What it signs.**
  - A session announcement at launch: identity, node fact, harness, model, session
    nonce, timestamp.
  - ACKs, CLAIM rows and RELEASE rows.
  - Domain-separated per message kind, so an ACK signature cannot be replayed as a
    claim.
- **Who verifies.** Any node's cipher, and the claim-collision gate, using only the
  public keys on the cards. No shared secret, so third-party verifiable.
- **Pattern to follow.**
  `PMOVES-ToKenism-Multi/integrations/contracts/tally-signer-ed25519.ts` already does
  Ed25519 k-of-n signing over a domain-tagged preimage (`TALLY_DOMAIN =
  'pmoves.tally.v1'`), "third-party verifiable on public keys only". Copy its *verifier*
  shape.
- **Counter-example, not to copy.** `integrations/firefly/settlement-executor.ts:392`
  `isSigned()`, which at the locally checked-out pin `04285b8` is
  `Boolean(alg && kid && hmac)`: a presence check, not verification.
- **Until then.** The resolver output must be read as "the session SAYS it is X". The
  launcher prompt and any UI should not present it as verified.

### The node's own default identity (resolves all three namespaces)

### The node's own default identity (resolves all three namespaces)

Replace `<n>` with the node's canonical name and `<N>` with its upper-case form. These are
the exact entries:

| # | File | Entry |
|---|---|---|
| 1 | `pmoves/configs/node-vocabulary.yaml` | `- canonical: <n>` · `kind: node` · `reach: pmoves-<n>` (tailnet name) · `aliases: [<n>, pmoves-<n>, <hostname>]` · `default_identity: {claude-code: claude_<n>}` · `cipher_agent_id: {claude-code: <n>-claude}`. An alias may belong to only one node; `load_vocabulary` raises globally otherwise. |
| 2 | `pmoves/config/signing_identity_cards.yaml` | Operator-issued card, `h.agent_id: "<n>-claude"`, next free `card_id`, `interim: true` until keys land. **Must be `active: true` before #1's `cipher_agent_id` merges**, or `test_node_identity.py` goes red. |
| 3 | `pmoves/config/agent_signatures.yaml` | `<n>-claude:` H-half entry (display_name, glyph, color, voice). |
| 4 | `pmoves/config/agent_registry.yaml` | `external_contributors += <n>-claude`. Add `claude_<n>:` using the `claude_5090` shape, with `signature: <n>-claude` and `topology.node_affinity: [<n>]`. |
| 5 | `pmoves/configs/agent-teams.yaml` | `orchestration` members `+= claude_<n>`. Without it, `validate_agent_registry.py` §5 errors with "registered but belongs to no team". |
| 6 | `pmoves/config/identity_vocabulary.yaml` | `- canonical: <n>-claude` · `aliases: ["<N>-CLAUDE", "claude_<n>"]` · `node: <n>` · `register_form: "<N>-CLAUDE"`. The registry-key alias is required for the register-name lookup. |
| 7 | host: `.claude/settings.local.json` | `"env": {"PMOVES_NODE_ID": "<n>"}`. This is optional if the hostname is an alias from #1. |
| 8 | host: Python | `.venv-pmoves` (or any `python3`) with `pyyaml`. |
| 9 | host: cipher | Per-agent `CIPHER_API_TOKEN` minted per `CIPHER_AUTH_RUNBOOK.md` §2. This is an operator step; never scrape it from `docker inspect`. Set `CIPHER_BIND` only if the fleet SSE entry must reach this node. |

Simulated in memory, the node's own default resolves all three namespaces:
`identity=claude_st_maarten`, `cipher=st-maarten-claude`, `register_form=ST-MAARTEN-CLAUDE`.

Verification once applied:
```bash
PMOVES_NODE_ID=<n> python pmoves/tools/node_identity.py --harness claude-code --shell
python pmoves/scripts/validate_agent_registry.py          # rc 0, "every declared identity is wired"
python -m pytest pmoves/tests/test_node_identity.py pmoves/tests/test_identity_coupling_gate.py \
  pmoves/tests/test_launcher_wakes_as_identity.py -q
```
The harness is not an identity entry. `claude-acp` (Zed and other ACP clients) comes from
PMOVES-Registry. Only `claude-code`, `crush` and `kimi` are launcher harness keys
(`validate_agent_registry.py` `_LAUNCHER_HARNESSES`).

## 5. PMOVES-registry gitlink

- Pinned `c784e2db` → fork `main` `a1ec4237c4e1a177a0ba85fd635a31b64cb71a62` (2026-10-06).
  `gh api .../compare` reported `status: ahead`, `ahead_by: 6`, `behind_by: 0`, so this is a
  clean fast-forward. `.gitmodules` tracks `branch = main` for this fork, and
  `fork_registry.json` agrees (`"branch": "main"`).
- Promoted with `git update-index --cacheinfo`, following the `fleet-fork-sync` Step 3
  recipe. Before promoting, every open PR was checked for an existing bump of the
  `PMOVES-registry` gitlink; none was found.
- The 6 commits are `17f28c0d` (verifier wall budget), `8ed63a4a`, `35106b27`, `d6e22eb5`
  (CI), `362f6012` (client timed-read), and `a1ec4237` (hyperagint-acp entry). The contents
  of the hyperagint-acp entry were not reviewed or edited here; any labelling issues are
  raise-only.
- **Sibling clone `~/pmoves-node/PMOVES-registry`: NOT fast-forwarded.** It is clean
  (`status --porcelain` = 0 lines) but is on branch `feat/uv-venv-guard`, not main.
  Against `origin/main` it is 1 ahead and 47 behind; its local `main` is 0 ahead and 47
  behind. Its HEAD commit `cd7d226` ("warn and uv-manage the tooling venv when VIRTUAL_ENV
  is unset") **has no upstream and is contained in no remote branch.** It exists only on
  Knuckles' disk, so the owner should push it or drop it.

## 6. Tests

Run with `uv run --no-project --with pytest --with pytest-asyncio --with pyyaml --with jsonschema --with pydantic`
over: `test_node_identity`, `test_crush_node_identity`, `test_identity_coupling_gate`,
`test_identity_lineage`, `test_launcher_wakes_as_identity`,
`test_launcher_prompt_accumulation`, `test_build_allowed_signers`, `test_harness_kind`,
`tests/tools/test_keygen_cards`, `tests/tools/test_chit_forks_cards`,
`tests/tools/test_gh_app_identity_registered`, `test_claim_collision_hook`, and
`tools/tests/test_pmoves_launcher_generator`. `validate_agent_registry.py` was also run.

| When | pytest | validator |
|---|---|---|
| before (origin/main `a477c3a7f`) | rc=0 · 407 passed, 1 skipped | rc=0 · "every declared identity is wired" |
| after (branch @ `d5adb3fce`) | rc=0 · 407 passed, 1 skipped | rc=0 · "every declared identity is wired" |

The before and after numbers are identical, as expected. This lane changed no identity
config. The only changes are this doc, the ledger row, and the gitlink, and none of the
suite reads the gitlink.

**Worn-identity resolver fix (2026-10-08).** Written test-first in
`pmoves/tests/test_node_identity_worn.py`, which has 12 cases.

| When | `test_node_identity_worn.py` | 13-file suite | validator |
|---|---|---|---|
| red (`96f0bdaab`, resolver unchanged) | 4 failed, 8 passed | — | — |
| green (resolver fixed) | rc=0 · 12 passed | rc=0 · 407 passed, 1 skipped | rc=0 |

All four red failures were behavioural, not import errors:
- The declared mirror was still refused with "declared for node 'knuckles', not
  'st-maarten'".
- The two-token refusal did not name either token.
- The worn `claude_b850` got cipher `st-maarten-claude`, which is the node default's card.
- An identity no node declares also got `st-maarten-claude`.

The 8 cases that already passed are regression guards: home node, fold-back, no relation,
relation from a different home node, mirror keyed on home, both override cases, and the
node's own default.

**Aggregate-model rework (2026-10-08, operator correction).** The same file was rewritten
to 20 cases. The node-gated expectations invert:
- A declared identity now binds off-affinity.
- With no relation, the owner string is `<BASE> (<node>)` instead of a refusal.
- Two tokens for one mirror fall back to the node instead of refusing.

| When | worn tests | 13-file suite | validator |
|---|---|---|---|
| red (`6ce87ab64`, resolver as of `f41a923fa`) | 7 failed, 13 passed | — | — |
| green (aggregate model) | rc=0 · 20 passed | rc=0 · 407 passed, 1 skipped | rc=0 |

All 7 red failures were the old refusals, i.e. behavioural:
- Affinity gate: "its own node_affinity ['pmoves-b850'] does not include st-maarten.
  Refusing to bind". This came from the off-affinity bind and both end-to-end worn cases.
- Node gate: "declared for node 'knuckles', not 'st-maarten'. Refusing to name a
  session". This came from no relation, a relation for another home, and the mirror keyed
  on home.
- Two-token refusal: "2 node_relations rows declare knuckles mirrored on st-maarten ...
  declare one".

One of my first-draft red cases failed on a test bug instead: it compared `unclassified`
(a tuple) to `[]`. I fixed it before the red commit, so it now passes as a guard that
`wearing()` already parses the node form.

Live effect on the real files:
- The default bindings on all four claude nodes are unchanged (asserted by
  `test_launcher_wakes_as_identity.py`).
- `PMOVES_NODE_ID=knuckles PMOVES_NODE_IDENTITY=claude_z890` now binds `claude_z890`
  off-affinity, with cipher `z890-claude` and form `Z890-CLAUDE (knuckles)`. Before, it
  refused.

An earlier attempt failed 7 `test_identity_coupling_gate` cases with
`ModuleNotFoundError: pydantic`. That was the ephemeral env missing a dependency of
`validate_agent_registry.py`, not a code failure. Adding `--with pydantic` cleared it.
