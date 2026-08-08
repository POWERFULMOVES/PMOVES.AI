# `up-*` target inventory

**88 targets** across `pmoves/Makefile` (82) and `pmoves/mk/{egress,infra,yt-cookies}.mk` (6).

WS2 item 5 of the 2026-08-08 coordination plan. **This is an inventory, not a change.** No Makefile is edited by the PR that adds this file. The operator picks what to retire; consolidation is a separate follow-up.

Generated against `origin/main` @ `22c78fbca`.

---

## Read the reference counts correctly

`refs` = files outside `pmoves/Makefile` and `pmoves/mk/` that mention the target — docs, skills, workflows, scripts, the claim register.

**A count of 0 does not mean the target is dead.** It means nothing in the repo writes it down. Targets exist for humans who type them, and shell history is not in the repo. Two of the eleven zero-reference targets below are already known to be load-bearing:

- **`up-cipher-nobuild`** — the gitlink-drift workaround for `cipher-api`. Its recipe is `--no-build --force-recreate`, and `cipher-api` declares only a `build:` stanza with no `image:`, so it reuses an image Compose already built **locally**. Its help text is accurate: "applies env/port changes when the `Pmoves-cipher` submodule build is unavailable (gitlink drift)." It solves a real problem and has no substitute. **Keep regardless of count.**

  (An earlier revision of this file called it a fresh-worktree escape hatch. That was wrong — with no published image to pull, it cannot start Cipher on a node that never built it. Corrected here and in `SUBMODULE_BUILD_AND_MOUNT_GAP.md`.)
- **`up-tokenism`** — landed deliberately as a Known Road in #2326 (`up-tokenism` / `down-tokenism` for the Tokenism Next.js UI), and #2334 later fixed its env sourcing. Recent, intentional, and paired with a `down-` target.

The counts are a starting point for a conversation, not a kill list.

---

## Families

### `up-agents-*` — 8

| Target | refs |
|---|---|
| `up-agents` | 82 |
| `up-agents-ui` | 17 |
| `up-agents-published` | 9 |
| `up-agents-integrations` | 6 |
| `up-agents-hardened` | 4 |
| `up-agents-auto` | 3 |
| `up-agents-stack` | 2 |
| `up-agents-standalone` | 1 |

The widest family. `up-agents` dominates; the seven variants split along two independent axes — image source (`published` / `integrations` / `standalone`) and compose profile (`ui` / `stack` / `hardened` / `auto`). Worth asking whether those should be flags on one target rather than seven targets.

### `up-yt-*` — 7

| Target | refs |
|---|---|
| `up-yt` | 41 |
| `up-yt-cookies` | 2 |
| `up-yt-egress` | 2 |
| `up-yt-hardened` | 2 |
| `up-yt-published` | 2 |
| `up-yt-cookies-recreate` | 1 |
| `up-yt-cookies-rebuild` | **0** |

`up-yt-cookies-rebuild` vs `up-yt-cookies-recreate` is the clearest near-duplicate pair in the whole set — one at 0 refs, one at 1. First thing to look at.

### `up-core-*` — 4

| Target | refs |
|---|---|
| `up-core` | 21 |
| `up-core-capable` | 2 |
| `up-core-gpu` | 1 |
| `up-core-hardened` | **0** |

### `up-workers-*` — 3

| Target | refs |
|---|---|
| `up-workers` | 19 |
| `up-workers-core` | **0** |
| `up-workers-hardened` | **0** |

Two of three orphaned. Alongside `up-core-hardened` and `up-agents-hardened` (4 refs), the `-hardened` suffix looks like an abandoned convention that only partly took — worth a single decision across all of them rather than four separate ones.

### Smaller families

| Family | Targets |
|---|---|
| `up-cipher-*` (3) | `up-cipher` 8 · `up-cipher-full` 2 · `up-cipher-nobuild` **0 — keep** |
| `up-gpu-*` (3) | `up-gpu` 22 · `up-gpu-gateways` 5 · `up-gpu-orchestrator` 2 |
| `up-jellyfin-*` (3) | `up-jellyfin` 20 · `up-jellyfin-ai` 11 · `up-jellyfin-ai-nvenc` 2 |
| `up-voice-*` (3) | `up-voice` 19 · `up-voice-amd` 4 · `up-voice-relay` 6 |
| `up-all-*` (2) | `up-all` 21 · `up-all-new` 5 |
| `up-archon-*` (2) | `up-archon-native` 7 · `up-archon-submodule` 5 |
| `up-juicefs-*` (2) | `up-juicefs` 5 · `up-juicefs-recreate` **0** |
| `up-tensorzero-*` (2) | `up-tensorzero` 26 · `up-tensorzero-full` 1 |

**`up-all` vs `up-all-new`** deserves its own answer. Both are referenced (21 / 5), and the names give no clue which supersedes which — that ambiguity is itself the cost. Per `project_obs_first_and_per_node_mcp`, `up-all-new` is the obs-first bring-up path, which suggests `up-all` is the legacy one. Confirm before touching either.

**`up-archon-native` vs `up-archon-submodule`** is *not* redundancy — Archon 0.6.0 is TS/SQLite-native with its own compose, so these are two genuinely different deployments. Keep both.

### Singletons — 46

```text
up-a2ui-renderer  up-activepieces  up-both-gateways  up-bots  up-bus
up-chit-tour  up-cloudflare  up-comfyui  up-creator-collab*
up-darkxside-sidecar  up-data-tier  up-edge  up-evo  up-external
up-ffmpeg-whisper  up-flute-gateway  up-hirag  up-integrations
up-invidious  up-legacy-both  up-media  up-minimal  up-minio
up-model-management  up-monitoring  up-n8n  up-nats-echo
up-notebooklm  up-obs  up-ollama  up-open-notebook  up-openroom
up-p7  up-persona  up-pinokio  up-rustdesk*  up-spark-sidecar
up-supabase  up-tokenism*  up-tracing*  up-tts-studio  up-ui
up-vibevoice  up-vllm  up-voicebox*  up-z890
```

`*` = zero references. These are one-service bring-ups and are mostly not sprawl — `up-hirag`, `up-minio`, `up-obs` are exactly what a per-service target should look like. `up-legacy-both` is the one name that advertises its own obsolescence.

---

## Zero-reference targets (11)

| Target | Note |
|---|---|
| `up-cipher-nobuild` | **KEEP** — gitlink-drift workaround, no substitute |
| `up-tokenism` | **KEEP** — deliberate Known Road (#2326, #2334), paired `down-tokenism` |
| `up-yt-cookies-rebuild` | near-duplicate of `up-yt-cookies-recreate` (1 ref) |
| `up-core-hardened` | `-hardened` convention, partly adopted |
| `up-workers-core` | |
| `up-workers-hardened` | `-hardened` convention, partly adopted |
| `up-juicefs-recreate` | |
| `up-creator-collab` | |
| `up-rustdesk` | RustDesk is a live fleet service (`project_rustdesk_relay_fix`) — check before retiring |
| `up-tracing` | |
| `up-voicebox` | |

---

## Suggested order for the follow-up

1. **`up-yt-cookies-rebuild` / `-recreate`** — one pair, one decision, lowest risk.
2. **The `-hardened` suffix** — `up-core-hardened` (0), `up-workers-hardened` (0), `up-agents-hardened` (4), `up-yt-hardened` (2). One convention decision covers four targets. Note that hardening also lives in `docker-compose.hardened.yml` and the `hardening-validation` workflow, so retiring the targets does not retire the concept.
3. **`up-all` vs `up-all-new`** — needs a name decision more than a delete.
4. **`up-agents-*` axes** — the biggest surface, and the one most likely to break someone's habit. Last.

Nothing here should move without the operator naming it. A `make` target costs one line; a removed target someone relies on costs a debugging session.

---

## Reproducing this

```bash
# enumerate
grep -hoE "^up-[a-z0-9-]+:" pmoves/Makefile pmoves/mk/*.mk | sed 's/:$//' | sort -u

# count references outside the makefiles
while read t; do
  n=$(grep -rl "\b$t\b" --include="*.md" --include="*.yml" --include="*.yaml" \
        --include="*.sh" --include="*.py" --include="*.json" . 2>/dev/null \
      | grep -vE "^\./pmoves/(Makefile|mk/)" | grep -v "^\./\.git" | wc -l)
  printf "%s\t%s\n" "$n" "$t"
done < targets.txt | sort -n
```

Word-boundary matching means a prefix target inflates on its own suffixes (`up-yt` matches inside `up-yt-egress`). That biases the *high* counts upward, never the zeros — so the zero list is trustworthy and the ordering among high-count targets is not.
