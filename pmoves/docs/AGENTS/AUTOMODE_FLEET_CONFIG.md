# Auto Mode — Fleet Configuration

GRAPHITI_MARK: `PHI-4482-AUTOMODE::FLEET-CONFIG`

> **For:** every PMOVES node operator (Z890, 5090, 4090-laptop, B850/PMOVES-Knuckles, DGX-Spark, KVM VPS, Jetson) running Claude Code in **auto mode**.
> **Why this is a committed doc:** the auto-mode classifier reads its config from `~/.claude/settings.json` or **`.claude/settings.local.json`** (gitignored) or managed settings — **never** from checked-in `.claude/settings.json`. So the block below cannot be committed into the repo's shared settings; each node must paste it into its own local settings. This doc is the canonical source to copy from.
> **First configured:** 2026-05-31 (Z890-CLAUDE), after the default classifier repeatedly false-blocked routine cross-submodule and fleet operations.

---

## Why the fleet needs this

Auto mode routes every tool call through a classifier that blocks anything irreversible, destructive, or aimed **outside your environment**. Out of the box it trusts only the working directory and the current repo's configured remotes. PMOVES.AI is:

- **50+ git submodules** across the entire **POWERFULMOVES** GitHub org, and
- a **Tailscale mesh + Hostinger VPS fleet + local GPU nodes + Jetson edge devices**.

None of that is "internal" to the default classifier, so routine work — cross-submodule pushes, gitlink promotion, merged-worktree cleanup, fleet SSH — reads as *potential exfiltration / irreversible destruction* and gets blocked. The `autoMode.environment` block declares this infrastructure trusted; the `allow`/`soft_deny`/`hard_deny` additions tune the specific PMOVES workflows while **keeping every built-in safety boundary** (each array begins with `"$defaults"`).

## How to apply (per node)

1. Open your node's **`.claude/settings.local.json`** (gitignored, per-node). Create it if missing.
2. Add the `autoMode` block below as a **top-level key** (sibling of `env` and `permissions`).
3. Also add `"Bash(git worktree remove:*)"` to `permissions.allow` (the permissions layer runs *before* the classifier).
4. Validate:
   ```bash
   claude auto-mode config     # prints effective rules with "$defaults" expanded
   claude auto-mode critique   # AI review of your custom rules — re-run after any edit
   ```
5. Confirm `environment`/`allow`/`soft_deny`/`hard_deny` counts are non-zero and the POWERFULMOVES/fleet lines appear.

### Do NOT change

- **Never drop `"$defaults"`** from any array — omitting it *replaces* the entire built-in list for that section (you'd lose force-push, `curl|bash`, prod-deploy, exfil, and self-modification blocks).
- **Keep the agent-infra self-modification gate** (`.claude/hooks/`, `.claude/agents/`, `.claude/settings*.json`). It's a valued safety boundary — auto mode intentionally blocks the agent widening its own permissions. Adding a permission rule the user didn't ask for stays blocked by design.
- **No literal LAN/Tailscale IPs** in the block — hostnames only (topology-leakage rule).

## The block (copy verbatim, then tweak per node)

The fleet hostnames below are shared; only your **own** node's `env.PMOVES_NODE_ID` differs. The block is node-agnostic — every node uses the same `autoMode` block.

```json
{
  "autoMode": {
    "environment": [
      "$defaults",
      "Organization: POWERFULMOVES (PMOVES.AI) — a Metal-Organic-Framework multi-agent orchestration platform. Primary use: software development, infrastructure automation, and multi-node fleet operations across 50+ git submodules.",
      "Source control: GitHub org github.com/POWERFULMOVES and ALL repositories under it are trusted internal source control. This SUPERSEDES the default 'trusted repo and its remotes only / no additional orgs configured / no trusted internal domains' lines — POWERFULMOVES is a configured trusted org and *.pmoves.ai is a configured trusted domain. The parent repo (POWERFULMOVES/PMOVES.AI) plus every PMOVES-*/Pmoves-* submodule (e.g. PMOVES-DoX, PMOVES-BoTZ, PMOVES-Agent-Zero, PMOVES-Archon, PMOVES-tensorzero, PMOVES-supabase) are part of this same project. Pushing to, creating branches on, and opening/merging PRs across any POWERFULMOVES repo is a routine internal operation, NOT exfiltration. These repos are private unless explicitly made public by the user. (Creating a brand-new remote and bulk-syncing all refs to it still warrants scrutiny.)",
      "Submodule model: this is a submodule-heavy monorepo-of-forks. Cross-submodule git operations (fetch, checkout, branch, push, merge-forward, gitlink promotion) against POWERFULMOVES repos are core daily workflow. Submodules track a 'PMOVES.AI-Edition-Hardened' branch that the parent gitlink deploys.",
      "Fleet: a private Tailscale mesh tailnet plus a Hostinger VPS fleet (hostnames like KVM2, KVM4) and local nodes (Z890, 5090, 4090-laptop, B850/PMOVES-Knuckles) and Jetson Orin edge devices. Fleet hosts are addressed by Tailscale hostname, never raw IP. SSH/RustDesk to these own fleet hosts is internal administration.",
      "Trusted internal domains: *.pmoves.ai (including headscale.pmoves.ai for the Headscale control plane).",
      "Key internal services: NATS message bus, Supabase/PostgREST, TensorZero gateway, Hi-RAG, Cipher Memory, Agent Zero, Archon — all self-hosted within the project. The local Docker daemon and project compose stacks are project-scoped infrastructure.",
      "Additional context: CHIT secrets flow through a canonical env pipeline (env.shared regenerated from example/manifest via secrets-funnel); production CHIT signing is voice-activated and must never be auto-generated. Committed docs use hostnames or placeholders, never literal LAN IPs."
    ],
    "allow": [
      "$defaults",
      "Worktree cleanup: removing a git worktree (git worktree remove, including --force) ONLY when BOTH are established by commands visible earlier in the same transcript: (1) the worktree's working tree is clean — a `git status` / `git status -s` on that worktree showing no changes; and (2) its branch is merged — a `git branch --merged`, a `gh pr ... merged` confirmation, or a PR state query showing MERGED. PMOVES uses many short-lived worktrees; pruning merged+clean ones is routine hygiene. An agent self-asserting 'this is merged/clean' without a visible confirming command does NOT qualify. Does NOT cover worktrees with uncommitted/untracked changes or unmerged branches.",
      "Submodule gitlink promotion: staging a submodule pointer bump via `git update-index --cacheinfo 160000,<sha>,<path>` where <sha> matches the tip of the `PMOVES.AI-Edition-Hardened` branch as shown by a `git ls-remote`/`git rev-parse`/`gh api .../branches/...` query visible in the transcript. An agent-asserted SHA not backed by a visible branch-tip query does NOT qualify. This is the standard parent-gitlink promotion flow, not arbitrary index manipulation.",
      "Fleet administration: SSH or RustDesk to the project's own fleet hosts addressed by Tailscale hostname (KVM2, KVM4, Z890, 5090, 4090-laptop, B850 a.k.a. PMOVES-Knuckles, Jetson Orin nodes) for routine NON-DESTRUCTIVE internal administration — reading logs, checking service/health status, restarting a project-owned service, deploying the project's own compose stack. These are single-owner dev/infra fleet hosts, NOT multi-tenant production in the Production Reads sense, so non-destructive admin reads/writes are cleared without a separate prod-target approval. Does NOT clear destructive remote operations: deleting/stopping SHARED services, blind --force/--yes applies, disabling security mitigations, or dumping/scanning secrets on a fleet host still require explicit user intent naming the target host and action."
    ],
    "soft_deny": [
      "$defaults",
      "Hardened branch rewrite: force-pushing, deleting, or rewriting history on any `PMOVES.AI-Edition-Hardened` branch across POWERFULMOVES repos. These branches are load-bearing — the parent gitlink deploys their tips — so history rewrites are destructive even though cross-submodule pushes are otherwise routine. Normal merge-forward and fast-forward pushes are fine."
    ],
    "hard_deny": [
      "$defaults",
      "CHIT/secrets exfiltration: committing, uploading, logging, or otherwise persisting real CHIT signing keys or a populated `env.shared` (with real secret values) to any destination including trusted POWERFULMOVES repos. The org-wide trust grant in environment does NOT exempt secrets — production CHIT signing is voice-activated and must never be auto-generated or copied. CARVE-OUT (allowed, NOT blocked): regenerating `env.shared` locally from the non-secret example/manifest/brand_defaults sources via the canonical secrets-funnel (`make -C pmoves secrets-funnel` and similar) — env.shared is a generated local artifact and writing it locally is the intended pipeline; only persisting real signing keys or a real-valued env.shared to a commit/upload/log/remote destination is blocked."
    ]
  }
}
```

## Per-node notes

| Node | `PMOVES_NODE_ID` | Notes |
|------|------------------|-------|
| Z890 | `z890` | Windows-native; PowerShell quirks (use forward-slash paths in bash, one repo per call). First node to configure this (2026-05-31). |
| 5090 | `pmoves-5090` | Primary MAX-plan workhorse. |
| 4090 laptop | `pmoves-4090` | Mobile node. |
| B850 / PMOVES-Knuckles | `pmoves-b850` | Designated Linux container host. |
| DGX-Spark | `spark` | GB10 model host; see `AGNOTE-dgx-spark.md`. |
| KVM VPS | `kvm4-1` etc. | Hostinger fleet; exit-node/VPN product hosts. |

The `autoMode` block is identical on every node. Only `env.PMOVES_NODE_ID` / `env.PMOVES_NODE_ROLE` differ (those live in the same `settings.local.json` but are unrelated to auto mode).

## Maintenance

- After any edit to the block, re-run `claude auto-mode critique` — it catches gaps like "an `environment` note alone can't clear a `soft_deny`" (why fleet SSH needs an explicit `allow`, not just an environment line).
- When the fleet changes (new node, new trusted domain, new org), update `environment` here first, then have each node sync.
- Org-wide rollout alternative: push this via **managed settings** (`autoMode` in server-managed settings) so the classifier distributes it to all nodes without per-node editing. Local entries are additive to managed ones.

## See also

- `.claude/PATTERNS.md` § Known Roads — the *other* gate (damage-control hooks) that runs **before** the classifier.
- `pmoves/docs/audit/HARDENED_BRANCH_FLEET_AUDIT_2026-05-31.md` — the hardened-branch reconciliation this config supports.
- Anthropic docs: `code.claude.com/docs/s/claude-code-auto-mode` (configuration reference).
