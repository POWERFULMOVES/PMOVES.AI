# `up-*` target inventory

**88 targets** across `pmoves/Makefile` (82) and `pmoves/mk/{egress,infra,yt-cookies}.mk` (6).

WS2 item 5 of the 2026-08-08 coordination plan. **This is an inventory, not a change.** No Makefile is edited by the PR that adds this file. The operator picks what to retire; consolidation is a separate follow-up.

Generated against `origin/main` @ `22c78fbca`.

---

## Read the reference counts correctly

Two independent counts, and **a target is only a retirement candidate when both are zero**:

- **`refs`** — files *outside* the makefiles that mention the target: docs, skills, workflows, scripts, the claim register.
- **makefile callers** — other targets that invoke it via `$(MAKE)`. Counted separately, excluding the target's own definition line and its `.PHONY` declaration.

**The second count was missing from the first revision of this file, and that made its retire list dangerous.** Excluding the makefiles to avoid counting definitions also excluded every *call site*. Three targets listed as zero-reference are in fact load-bearing links in a live chain:

```text
up-core-capable  ->  up-core-hardened   (Makefile:2542)
                        |-> up-workers-hardened   (Makefile:2506)
                        `-> up-agents-hardened    (Makefile:2507, 2533)
```

Retiring `up-core-hardened` on the strength of its zero external count breaks `up-core-capable`. Caught in review by Codex on #2486; corrected here.

**Even both-zero does not mean dead.** It means nothing in the repo writes it down and no other target calls it. Targets exist for humans who type them, and shell history is not in the repo. Two of the eight both-zero targets are already known to be load-bearing:

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

`up-yt-cookies-rebuild` and `up-yt-cookies-recreate` **look** like a near-duplicate pair and are not — `--build` for code changes vs `--force-recreate` for env changes (`mk/yt-cookies.mk:141-149`). Keep both; see the candidates section.

### `up-core-*` — 4

| Target | refs |
|---|---|
| `up-core` | 21 |
| `up-core-capable` | 2 |
| `up-core-gpu` | 1 |
| `up-core-hardened` | **0 ext** — but called by `up-core-capable` (`Makefile:2542`) |

### `up-workers-*` — 3

| Target | refs |
|---|---|
| `up-workers` | 19 |
| `up-workers-core` | **0** |
| `up-workers-hardened` | **0 ext** — but called by `up-core-hardened` (`Makefile:2506`) |

`up-workers-hardened` shows 0 external refs but is **called by `up-core-hardened`** (`Makefile:2506`). `up-workers-core` is the only genuinely unreferenced one. The `-hardened` suffix is **not** an abandoned convention — it is a live dependency-ordered bring-up chain rooted at `up-core-capable`.

### Smaller families

| Family | Targets |
|---|---|
| `up-cipher-*` (3) | `up-cipher` 8 · `up-cipher-full` 2 · `up-cipher-nobuild` **both-zero — keep** |
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
up-chit-tour  up-cloudflare  up-comfyui  up-creator-collab 
up-darkxside-sidecar  up-data-tier  up-edge  up-evo  up-external
up-ffmpeg-whisper  up-flute-gateway  up-hirag  up-integrations
up-invidious  up-legacy-both  up-media  up-minimal  up-minio
up-model-management  up-monitoring  up-n8n  up-nats-echo
up-notebooklm  up-obs  up-ollama  up-open-notebook  up-openroom
up-p7  up-persona  up-pinokio  up-rustdesk*  up-spark-sidecar
up-supabase  up-tokenism*  up-tracing*  up-tts-studio  up-ui
up-vibevoice  up-vllm  up-voicebox*  up-z890
```

`*` = zero external references (all four also have no makefile caller; `up-creator-collab` does — `Makefile:3846` — so it is not starred). These are one-service bring-ups and are mostly not sprawl — `up-hirag`, `up-minio`, `up-obs` are exactly what a per-service target should look like. `up-legacy-both` is the one name that advertises its own obsolescence.

---

## Retirement candidates — both counts zero (8)

Down from eleven once makefile callers are counted. `up-core-hardened`, `up-workers-hardened`, and `up-creator-collab` are removed from this list: all three are called by other targets.

| Target | Note |
|---|---|
| `up-cipher-nobuild` | **KEEP** — gitlink-drift workaround, no substitute |
| `up-tokenism` | **KEEP** — deliberate Known Road (#2326, #2334), paired `down-tokenism` |
| `up-yt-cookies-rebuild` | **KEEP** — *not* a duplicate of `-recreate`; see below |
| `up-rustdesk` | RustDesk is a live fleet service (`project_rustdesk_relay_fix`) — check before retiring |
| `up-workers-core` | |
| `up-juicefs-recreate` | |
| `up-tracing` | |
| `up-voicebox` | |

### `up-yt-cookies-rebuild` is not a near-duplicate

The first revision of this file called it "the clearest near-duplicate pair in the whole set" and put it first in the retire order. Reading the bodies (`mk/yt-cookies.mk:141-149`) shows two distinct flows:

| Target | Flag | For |
|---|---|---|
| `up-yt-cookies-recreate` | `--force-recreate` | picking up env changes |
| `up-yt-cookies-rebuild` | `--build --force-recreate` | picking up **code** changes |

Consolidating either direction is a real loss: drop `-rebuild` and there is no image-rebuild path; drop `-recreate` and every routine env refresh pays for a rebuild. The suffixes name the difference accurately. Keep both.

---

## Suggested order for the follow-up

The two items the first revision led with are both withdrawn — one was a false duplicate, the other a live dependency chain. What remains is smaller and softer.

1. **`up-all` vs `up-all-new`** — both referenced (21 / 5), and the names give no clue which supersedes which. That ambiguity *is* the cost. Per `project_obs_first_and_per_node_mcp`, `up-all-new` is the obs-first bring-up path, which suggests `up-all` is legacy. This needs a **naming** decision, not a delete.
2. **`up-workers-core`, `up-juicefs-recreate`, `up-tracing`, `up-voicebox`** — the four both-zero targets with no known keeper reason. Ask the operator whether each is still typed; retire only on a yes-it's-dead.
3. **`up-agents-*` axes (8)** — splits along image source (`published`/`integrations`/`standalone`) and profile (`ui`/`stack`/`hardened`/`auto`). Possibly flags on one target rather than seven. Biggest surface, most likely to break a habit, so last — and note `up-agents-hardened` is called from two places, so it is not free to move.

**Withdrawn from this list:**

- ~~`up-yt-cookies-rebuild` / `-recreate`~~ — distinct flows (`--build` vs env-only). See above.
- ~~The `-hardened` suffix as an abandoned convention~~ — `up-core-hardened` is invoked by `up-core-capable`, and itself invokes `up-workers-hardened` and `up-agents-hardened`. The convention is not abandoned; it is a working dependency-ordered bring-up chain.

Nothing here should move without the operator naming it. A `make` target costs one line; a removed target someone relies on costs a debugging session — and a removed target *another target calls* costs a broken bring-up.

---

## Reproducing this

Two scans. Run them against the **parent** of the commit that added this file, or exclude this file — it names every target, so on the committed tree every "zero" becomes a one.

```bash
# enumerate
grep -hoE "^up-[a-z0-9-]+:" pmoves/Makefile pmoves/mk/*.mk | sed 's/:$//' | sort -u > targets.txt

# (1) external references — docs, CI, scripts, register
while read t; do
  n=$(grep -rl "$t" --include="*.md" --include="*.yml" --include="*.yaml"         --include="*.sh" --include="*.py" --include="*.json" . 2>/dev/null       | grep -vE "^\./pmoves/(Makefile|mk/)"       | grep -v "UP_TARGET_INVENTORY.md"       | grep -v "^\./\.git" | wc -l)
  printf "%s	%s
" "$n" "$t"
done < targets.txt | sort -n

# (2) intra-makefile callers — skip the definition line and .PHONY
while read t; do
  n=$(grep -nE "$t" pmoves/Makefile pmoves/mk/*.mk       | grep -vE ":[0-9]+:$t:" | grep -v "\.PHONY" | wc -l)
  printf "%s	%s
" "$n" "$t"
done < targets.txt | sort -n
```

### Known biases

- **Prefix inflation.** Word-boundary matching lets a prefix target match inside its own suffixes (`up-yt` matches in `up-yt-egress`). This inflates **high** counts and never creates a false zero, so ordering among frequently-referenced targets is unreliable while the zero determinations are not.
- **Scan (1) alone is not sufficient**, and treating it as such is what made the first revision of this file wrong. It answers "does anything written down mention this", not "is anything broken if this disappears". Only scan (2) answers the second question.
- **Neither scan sees a human.** A target typed weekly and never written down scores zero on both.
