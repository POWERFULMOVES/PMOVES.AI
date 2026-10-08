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
   - **registry identity:** `<node>.default_identity.claude-code`. It must be a key in
     `agent_registry.yaml` whose `topology.node_affinity` resolves to that node.
   - **cipher agentId:** `<node>.cipher_agent_id.claude-code` when the bound identity is
     this node's default. For a worn identity it is the `cipher_agent_id` declared beside
     that identity on its home node. Declared, never derived.
   - **register name:** the `identity_vocabulary.yaml` entry whose canonical or alias
     matches the registry key, with a `register_form`. On its home node this is the
     `register_form`. On another node it is `<BASE> (<token>)`, but only when a
     `node_relations` row declares the mirror.
4. then `pm-cipher-identity.sh` checks the cipher id against a signing card and the
   `CIPHER_API_TOKEN` visible to the process.

**A.12 multiplicity (operator ruling 2026-10-08): do BOTH.** A new node gets its own
default identity (the table below), AND an existing identity can be worn there. These
used to be written up as "Option A vs Option B". That was a false choice, and the
"2 of 3 namespaces" result was a resolver defect, which is now fixed in
`node_identity.py`.

### Wearing an existing identity on node X (e.g. B850-CLAUDE on a St Maarten host)

To wear B850-CLAUDE on node X:
1. Add node X to `node-vocabulary.yaml`, with its own default as in the table below.
2. Add a `node_relations` row to `identity_vocabulary.yaml`:
   `{token: KNUCKLES-mirror-on-X, node: X, mirrored_from: knuckles}`.
   - The token is used verbatim in the owner string.
   - `node` and `mirrored_from` may use any alias, because both are normalised.
   - Declare exactly one row per mirror; two rows for the same mirror are refused.
3. Extend `claude_b850.topology.node_affinity` in `agent_registry.yaml` with X.
   `resolve_identity` still refuses an identity whose affinity does not claim the node.
   A.12 names the affinity entry as part of portability, so the resolver keeps requiring
   it rather than inferring it from the relation.
4. Launch with `PMOVES_NODE_IDENTITY=claude_b850`. This selects the worn identity over the
   node's own default.

No `cipher_agent_id` entry on X is needed for the worn identity.

Result, from fixtures in `pmoves/tests/test_node_identity_worn.py`:
`identity=claude_b850`, `cipher=b850-claude` (knuckles' declared card, not X's), and
`register_form=B850-CLAUDE (KNUCKLES-mirror-on-X)`. The form folds back to `b850-claude`
under `identity_lineage.canonical_identity`. It is the same shape as the one real row
(`Z890-mirror-on-5090`), and against the real files that row now names
`Z890-CLAUDE (Z890-mirror-on-5090)`.

**Not reachable through `PMOVES_REGISTER_IDENTITY`.** That second-session override still
requires an identity declared for THIS node. If it could reach through a mirror, a second
session could borrow another identity's BASE.

**Open hazard (raise-only).** A worn session and the home session fold to the SAME
identity in the collision gate, because the parenthetical is stripped. That is the
cross-node form of the 2026-09-26 B850-CLAUDE-FUNNEL incident: one gate identity, and a
bare RELEASE by either session closes both sessions' lanes. If both run at the same time,
the second needs a distinct BASE. The rule exists in identity_vocabulary, but nothing
enforces it across nodes.

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

An earlier attempt failed 7 `test_identity_coupling_gate` cases with
`ModuleNotFoundError: pydantic`. That was the ephemeral env missing a dependency of
`validate_agent_registry.py`, not a code failure. Adding `--with pydantic` cleared it.
