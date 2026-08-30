# Agent Authorization Model

**Status:** design proposal · **Date:** 2026-08-22 · **Node:** z890
**Prompted by:** a read of Docker's AI Governance docs, mined for its model rather than adopted as a product.

---

## The finding, in one line

**We have authentication everywhere and authorization nowhere.**

Every surface an agent touches can answer *"is this key, token or cookie valid?"*
Not one of them can answer *"which principal is this, and may it do this?"*

That is not a gap in one component. It is the same gap in five components, which
is why it has stayed invisible: each surface looks locally reasonable.

---

## Evidence

Confidence is marked because two systematic blind spots were found while
gathering it — see [Survey integrity](#survey-integrity).

| surface | who acts | what bounds it | confidence |
|---|---|---|---|
| GitHub Actions | 6+ distinct credentials: App (`GH_APP_CLIENT_ID`/`GH_APP_SEC`), `ACTIONS_PAT`, `GH_PAT`, two account PATs, `CI_GIT_CLONE_TOKEN`, plus `github-runner-ctl`'s own PAT | per-workflow `permissions:` blocks; 13 of 56 workflows declare none | **high** — read from workflow YAML |
| Docker / compose | container identity | Docker MCP Gateway flags: `--block-secrets` on, `--block-network` **default off**, `--verify-signatures` not enabled | **high** |
| E2B sandboxes | one flat `E2B_API_KEY` | E2B egress rules — **default allow, allow-wins** | **high** — read from E2B source |
| Cloudflare | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_DNS_API_TOKEN`, tunnel token | tunnel ingress rules, **not committed as data** | **medium** |
| Browser / desktop | a human's browser session | nothing | **high** |

### The three browser surfaces disagree with each other

| surface | authenticates by | blast radius |
|---|---|---|
| `PMOVES-surf` (E2B desktop) | nothing — no cookie/session/profile code exists | contained; the VM dies with the sandbox |
| `PMOVES-space-agent` bridge | one shared static API key | file writes into the running app tree |
| Agent Zero `_browser` (BYOB) | inherits the operator's real browser over CDP | the entire session: cookies, saved data, navigation |

`surf` is safest because it is *incapable* of persistence, not because it was
designed to be constrained. Agent Zero's "Bring Your Own Browser" is the
opposite, and its own documentation says so plainly: it "grants full control of
that browser session, including access to saved data, cookies, site data, and
navigation."

That is the unattributable / unconstrained / unrevocable pattern, shipped.

### Identity as a constant string

The space-agent bridge's entire authorization layer:

```js
if (providedKey !== API_KEY) throw createHttpError("Invalid PMOVES API key", 403);
return { authenticated: true, username: "pmoves-agent" };
```

Every caller holding the key *is* `pmoves-agent`. No attribution, no per-agent
revocation, no scope, no expiry. (It also compares non-constant-time, while
`services/sso-auth/oidc.py` uses `hmac.compare_digest` for the same job — two
files, two standards, nothing reconciling them.)

### The identity anchor we already have, and its limits

`services/sso-auth/` is a real OIDC provider — discovery, JWKS, RS256,
auth-code flow with redirect-URI binding. Three constraints matter here:

1. the client list is **one hardcoded entry** (`_client_ok` compares against a
   single configured client id/secret);
2. `scopes_supported` is `["openid", "profile", "email"]` — identity only, no
   vocabulary for authority;
3. `/oidc/authorize` requires an existing **user session cookie**. There is no
   client-credentials grant, no device flow, no token exchange.

Point 3 is currently a safety property: no agent can self-authorize. It is also
why the only available path is the worst one — an agent riding a human's cookie.

---

## What is worth borrowing

Not the rule syntax, and not the product. **The evaluation contract:**

- **Default deny.** Anything no allow rule matches is refused.
- **Deny wins.** A matching deny beats any allow, including an allow that would
  otherwise require approval.
- **Allows are additive; denies are absolute.** Several policies may grant; any
  one may forbid.
- **Precedence follows the decision, not the source.** A local allow cannot
  widen what the fleet permits; a local deny still narrows it.

That last property is the one that makes a guardrail possible. A fleet-wide
`deny` must be something no node-local config can override.

Two more ideas transfer directly:

- **Two evaluation points.** Registration-time (may this server be registered?)
  and use-time (may this tool be called?). A rule for one does not govern the
  other. Our registry is registration-shaped only; there is no use-time concept.
- **Name the bypass.** Docker's docs state that MCP policy governs only what
  flows through their gateway; a direct outbound connection is network policy's
  problem, so blocking a server needs *both*. Any policy we write must say which
  path it does **not** cover.

---

## The constraint that shapes the implementation

**E2B's egress semantics are the inverse of the contract above.** From
`packages/orchestrator/pkg/tcpfirewall/handlers.go`:

```
// Priority order:
//  1. Allow domain / Allow CIDR (if either matches → allow)
//  2. Deny domain / Deny CIDR (if either matches → deny)
//  3. Default: allow
```

The nftables chain agrees: the predefined *allow* set is evaluated before the
predefined *deny* set, and the chain's default policy is ACCEPT.

So on E2B, **an allow beats a deny, and unmatched traffic is permitted**. A
fleet-wide prohibition cannot be expressed as an E2B deny entry, because a
per-sandbox allow silently wins.

**Rule: a PMOVES `deny` compiles to _absence from the allowlist_, never to an
E2B deny entry.** E2B's deny lists may be used for defence in depth, but nothing
may depend on them. Any control that must hold has to hold by omission.

What E2B does give us is genuine enforcement primitives: nftables sets, and a
TCP proxy that inspects **HTTP Host** and **TLS SNI** — real domain matching, not
IP guessing.

---

## Proposed shape

Extend the mechanism that already works rather than inventing a parallel one.
`services/agent-zero/security/patterns.yaml` is policy-as-data, enforced at
tool-call time, and — importantly — **lists itself as `zero_access`, so the agent
cannot rewrite its own policy.** Docker's model has no equivalent concept. Keep
that property and widen the file's domains:

```yaml
# domains: filesystem (exists today), network, mcp
network:
  rules:
    - name: allow-package-registries
      decision: allow
      actions: [connect:tcp]
      resources: ["**.pypi.org", "registry.npmjs.org:443"]
    - name: never-reach-metadata-service
      decision: deny          # absolute; compiles to omission on E2B
      actions: [connect:tcp]
      resources: ["169.254.0.0/16"]
mcp:
  rules:
    - name: registration-requires-registry-entry
      evaluation_point: registration
      decision: allow
      resources: ["registered:*"]
    - name: approval-for-writes
      evaluation_point: use
      decision: allow
      requires_approval: true
      resources: ["tool:*:write*"]
```

**Principal.** The missing type. Minimum viable: an agent identity that is
(a) distinct per agent, (b) carried in the request, (c) revocable individually,
(d) recorded in the audit line. `agent_registry.yaml` already names every agent —
it is the natural source, and as of the cross-entry check it is now verified
against reality rather than assumed.

**Audit.** We already have more than expected: `security/hooks/audit_log.py`
writes one JSONL line per tool call with secret-scrubbing, distinct from CHIT
`sign-trail`, which is per-checkpoint self-attestation. The gap is that the audit
line records *what* happened, not *under whose authority*.

---

## Enforceable today vs needs building

| capability | today |
|---|---|
| filesystem policy, runtime-enforced, agent cannot self-modify | **works** |
| per-tool-call audit with secret scrubbing | **works** |
| domain-level egress matching (Host/SNI) | **primitive exists** in E2B; no policy drives it |
| default-deny evaluation | **absent** — E2B defaults to allow |
| MCP registration policy | **partial** — registry is descriptive, not enforcing |
| MCP use-time policy / approval gates | **absent** |
| per-agent principal | **absent** — identity is a constant string or a human's cookie |
| fleet-wide deny that a node cannot override | **absent** |

**Smallest real win, if one thing is done first:** set
`PMOVES_MCP_BLOCK_NETWORK=1` on the Docker MCP Gateway. It is already
implemented and off by default, and it closes the documented direct-connection
bypass without any new policy machinery.

---

## Survey integrity

The evidence above was gathered by parallel survey, and two systematic blind
spots were found *during* it. Both produced false negatives that read as
findings:

1. **Uninitialized submodules.** 6 of 58 were empty directories, including three
   MCP servers. A survey concluded "no per-tool MCP allow/deny exists anywhere"
   while three relevant repos were invisible.
2. **A stale parent tree.** The working checkout was 207 commits behind `main`.
   A survey concluded a tool "does not exist in the repository"; it exists on
   `main`.

Load-bearing negatives were re-tested against `origin/main` afterwards. The
central one — *no E2B compose service is defined* — holds: zero e2b services
across all three compose files.

The lesson is the same one this document is about. An instrument that cannot see
its subject reports absence identically to a clean result. Anything below
**high** confidence in the evidence table should be re-verified before it is
used to justify a change.

---

## Out of scope / open

- Whether to adopt Docker Sandboxes as a runtime (this document borrows the
  model only; org governance there is a paid subscription and a different
  runtime surface from our compose fleet).
- `PMOVES-Danger-infra` carries **zero PMOVES commits** — it sits exactly at
  upstream `main`. The one component that would enforce sandbox egress has no
  hardening overlay, unlike every other fork we maintain.
- Cloudflare tunnel ingress rules are not committed, so the public surface of
  the tunnel is not reviewable in-repo.
- Two Cloudflare MCP integrations exist against the same account, both able to
  mutate DNS and tunnels, neither with per-agent scoping.

## Related

- `pmoves/services/agent-zero/security/patterns.yaml` — the working model
- `pmoves/config/agent_registry.yaml` + `make -C pmoves agent-registry-check`
- `pmoves/docs/operations/MCP_TOOLKIT.md` — gateway security flags
