# Fleet Memory and Room Portability — B850 findings, 2026-09-08

**Node:** `PMOVES-B850-AI-TOP` (knuckles). **Date:** 2026-09-08.
**Why this exists:** Cipher — the fleet's persistent memory — was unreachable during
this session, so nothing learned had anywhere durable to go, and this node was about
to be powered off for a physical NVMe pull. This file is the durable record.

## How to read the evidence markers

Every claim below carries one of:

- **MEASURED (B850, 2026-09-08)** — reproduced on this node this session; the command
  is given or the repo path is cited.
- **REPORTED** — measured by the session lead, recorded here, not independently
  re-run at write time. Re-verification is cheap; the method is stated.
- **UNVERIFIED** — asserted but not substantiated from the repo or the host.
- **CORRECTION** — a claim carried into this doc that turned out to be wrong, with
  what is actually true.

Distinguishing these is the point of the document. A wrong fact recorded durably is
worse than no fact.

---

## Finding 1 — There is no fleet-reachable Cipher

### What is true on B850

**MEASURED (B850, 2026-09-08).** `pmoves-cipher-api-1` is `running` / `healthy`.
`docker port pmoves-cipher-api-1` returns exactly:

```
8105/tcp -> 127.0.0.1:8105
```

It is bound to loopback. Its data lives in the node-local Docker volume
`pmoves_cipher-data` (`docker inspect` → `.Mounts[].Name`). Both facts together mean
this Cipher is unreachable from any other node **even while B850 is up**, and its
memory does not leave this box. It is not fleet memory; it is one node's notebook.

**REPORTED.** `/mcp/sse` returns HTTP 200 with a valid bearer against this local
instance. Consistent with the long `_note` already in `.claude/mcp.json:5`, which
records the same measurement on 2026-09-02 (200 with the correct token, 401 with an
empty or literal-`${...}` bearer, and `/health` 200 in *both* auth postures — so
`/health` cannot tell you the auth posture).

### The roster is correct; the service is not there

**MEASURED (repo).** `.claude/mcp.json:7` points the canonical `pmoves-cipher` entry
at `http://${TS_Z890}:8105/mcp/sse`. `pmoves/config/profiles/z890-coordinator.yaml:34`
declares `cipher: cipher-api` under `services:`, and line 102 declares
`cipher: 8105` under `external_ports:`. **Z890 is the designated Cipher host by
design.** The roster URL is not a mistake.

**Do not "fix" this by editing `.claude/mcp.json`.** That exact wrong fix was made
once already during the July stale-container incident (see
`project_cipher_stale_build_mcp_path`: the running image served `/api/mcp/sse` while
source, roster and Agent Zero all expected `/mcp/sse`; the remedy was
`make -C pmoves up-cipher`, not a roster edit). The roster points where the
architecture says Cipher lives. The fix is to make Cipher live there.

`.claude/mcp.json:213` already carries a second entry, `pmoves-cipher-local`, whose
own description states the problem plainly: *"cipher is published on loopback, so the
fleet URL is unreachable cross-node."* The gap is known and written down; it has not
been closed.

### CORRECTION — Z890 is unreachable at the tailnet layer, not merely serviceless

The claim carried into this task was: *"`TS_Z890` is populated; that host returns
HTTP 000 on both `/mcp/sse` and `/health`; the service simply is not running there."*

The HTTP result reproduces. **MEASURED (B850, 2026-09-08)**, resolving by tailnet
hostname rather than by the env var so no secret value is handled:

```
$ curl -s -o /dev/null -m 6 -w '%{http_code}' http://pmoves-z890:8105/mcp/sse   -> 000
$ curl -s -o /dev/null -m 6 -w '%{http_code}' http://pmoves-z890:8105/health    -> 000
```

But the *diagnosis* was wrong. **MEASURED (B850, 2026-09-08):**

```
$ tailscale ping --c 2 pmoves-z890
peer's node key has expired
```

`tailscale status` lists `pmoves-z890` (tagged-devices, windows) with no active
connection. **The Z890 node key has expired**, so traffic to that host fails at the
tailnet layer before it reaches any port. HTTP 000 on *every* port is the expected
result of an expired node key and tells you nothing about whether `cipher-api` is
running there.

Practical consequence — the remedy is two steps, in order, and the second is
useless without the first:

1. Re-authenticate `pmoves-z890` on the tailnet (expired node key). Operator action
   on Z890.
2. Then bring Cipher up on Z890 and confirm `/mcp/sse` answers 200 with a bearer.

**This task is documentation only.** Neither step was taken here. Do not bring Cipher
up on Z890 from another node, and do not change any container's port binding.

### What this does and does not explain

**It does explain** the session preflight `exit 1` without needing any other
hypothesis: the canonical roster entry points at a host that is currently
unreachable, so the Cipher MCP server cannot load.

**It does not settle** the roster-sweep / OOM-resume hypothesis recorded in
`project_cipher_missing_tools_chain_closed` (servers load at launch; a sweep deletes
the `--mcp-config` file; RESUME re-reads a now-missing path). That hypothesis is
**neither confirmed nor refuted** by this finding. The two failure modes are
independent and can both be true. Testing the resume hypothesis requires a launch
against a *reachable* Cipher, which was not available this session.

Also unresolved and worth stating: **UNVERIFIED** whether `${TS_Z890}` currently
resolves to the same host as the tailnet name `pmoves-z890`. The env var lives in
hook-blocked files and was not read. If it holds a raw Tailscale IP rather than a
hostname, it will also go stale independently of the node key.

---

## Finding 2 — Loopback binding is a fleet-wide pattern, not a Cipher quirk

**MEASURED (B850, 2026-09-08).** Across 61 running containers:

| Binding class | Count |
|---|---|
| Loopback-only (`127.0.0.1:` published) | 12 |
| All-interfaces (`0.0.0.0:` / `[::]:` published) | 16 |
| No published ports (internal to a compose network) | 33 |

The 12 loopback-only containers:

```
pmoves-activepieces-activepieces-app-1   pmoves-archon-1
pmoves-cipher-api-1                      pmoves-evo-controller-1
pmoves-ffmpeg-whisper-1                  pmoves-flute-gateway-1
pmoves-n8n                               pmoves-supabase-kong-1
pmoves-supabase-postgrest-1              pmoves-ultimate-tts-studio-1
pmoves-yt-cookie-refresher-1             portainer
```

Cipher is not special. **A quarter of everything this node publishes is
node-private.** Any of these services referenced by a fleet-wide roster, catalog or
room manifest is unreachable cross-node for exactly the same reason, and would show
exactly the same symptom.

### There is no per-service tailnet identity

**MEASURED (repo).** `pmoves/docker-compose.tailscale.yml` defines exactly **one**
service, `tailscale`, and it is a host-level sidecar: `network_mode: host`, a single
`TS_HOSTNAME`, one `tailscale-state` volume. There is no per-service tailnet
identity, and no Cipher entry.

The operator's framing this session was that services "need their own set of 100" —
i.e. each service holding its own `100.x` tailnet identity, so `cipher` is addressable
as a first-class tailnet peer rather than as a port on whichever host happens to run
it. **That capability does not exist today.** Nothing in the compose tree provisions
it. This is recorded as a gap, not as a plan; designing it is a separate lane.

### Egress and ingress are different problems that sound alike

Two distinct failure families keep getting conflated because both are "networking":

- **EGRESS** — traffic leaving a node. This is what exit nodes address, and it is the
  subject of `project_knuckles_exitnode_docker_egress` (selecting an exit node killed
  all container egress on Knuckles while the host stayed fine).
- **INGRESS / reachability** — another node reaching a service *on* this node. This is
  Finding 1 and Finding 2. **Exit nodes do not help.** A loopback-bound service is
  unreachable no matter what the egress path is.

When triaging "cipher is down", establish which family it is first. The
exit-node hypothesis is not applicable to a loopback binding.

---

## Finding 3 — Room portability is already mandated; the capability mechanism is undocumented

### The mandate exists

**MEASURED (repo).** `pmoves/docs/ROOM_MANIFEST_CONTRACT.md:55` already forbids
node-specific state in a manifest:

> It does **not** own host paths, node names, or absolute filesystem locations. Those
> are per-node runtime concerns; a manifest that hardcodes them stops being portable
> across the fleet.

So portability is not a new idea to argue for. It is already contract law.

### The mechanism that would satisfy it is barely used

**MEASURED (repo).** `hardware_requirements` appears in **2 of 16** room manifests in
`pmoves/config/rooms/`:

- `creator-studio.room.collab.json`
- `pmoves.room.helpdesk.json`

Its shape, per `pmoves/contracts/schemas/room/room.manifest.v1.schema.json:500`:
`{ gpu, min_vram_mb, gpu_arch, node_roles, cpu_arch }`.

It has real consumers:

- `pmoves/tools/creator-collab-evidence/render_dashboard.py:69-71` — reads
  `room.get("hardware_requirements", {})` off the manifest directly.
- `pmoves/services/pinokio_bridge/app.py:453-478` — `GET /v1/gpu/match`, which answers
  `min_vram` + `gpu_arch` queries against the detected GPU and normalizes raw CUDA
  compute capability (`12.0`) to the schema's `sm_XX` form.

  **Precision note:** the bridge is a *conforming counterpart* to the field, not a
  reader of the manifest. It implements the matching service that the field's values
  are meant to be queried against; it never opens a room manifest itself. Do not
  record it as "the manifest consumer" — there is exactly one of those
  (`render_dashboard.py`).

### The gap

**MEASURED (repo).** `grep -c hardware_requirements pmoves/docs/ROOM_MANIFEST_CONTRACT.md`
returns **0**.

The field is defined in the JSON Schema, has a design spec
(`pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md:27,57-61`), has a
matching service, and has a dashboard renderer — and is entirely absent from the
document that room authors actually read. That is the straightforward explanation for
why 14 of 16 rooms omit it: **there is a mechanism for portability and no road to it.**

This is the same shape as `project_cipher_collection_provisioner_no_road` — a
capability that exists but has no Known Road never gets used, and its absence looks
like a design decision rather than an oversight.

> **Ownership:** a sibling agent (`room-portability-delivery-2`) may be documenting
> `hardware_requirements` in `ROOM_MANIFEST_CONTRACT.md` concurrently. This document
> deliberately **does not edit that file** — it only references it. If that lane has
> landed, this section's gap statement is the historical record of why, and should be
> updated with a pointer rather than deleted.

### Design intent, verbatim

Recorded from the operator this session, because the framing is the requirement and
paraphrasing it loses the point:

> rooms are living docs — "portable reproducable and they upgrade with capability
> capacity just like pc games are made to run on all types of hard ware... designed
> for infinite playability not just replay."

Read as a spec, that is: a room declares *what capability it needs*, never *which
machine it runs on*; the runtime scales the experience to whatever capacity the host
offers (the PC-game graphics-settings model); and the room stays replayable on
hardware that did not exist when it was authored. `hardware_requirements` is the
declarative half of that. The scaling half — degrading gracefully rather than
refusing to admit — is **UNVERIFIED** as existing anywhere today; `min_vram_mb` is
currently a hard admission floor, not a quality dial.

---

## Finding 4 — Node role assignments

Recorded from the operator this session. Role assignments are operator intent, not
measurements, and are marked REPORTED unless a repo artifact backs them.

| Node | Role |
|---|---|
| **B850** (Knuckles) | Home of the CHIT deploy bundle — *"the ultimate bootstrap, bootstrap it from CHIT."* |
| **SPARK** (`dgx-spark-grace-blackwell`) | "Node dreamer"; holds the local model store. |
| **Z890** | Coordinator; declared Cipher host (see Finding 1). |
| **KVM2 / KVM4-1 / KVM4-2** | Always-on; offer exit nodes. |

**MEASURED (repo)** for Spark, which the profile independently corroborates —
`pmoves/config/profiles/dgx-spark-grace-blackwell.yaml`: arm64, GB10 Grace-Blackwell,
128 GB unified LPDDR5X, `compute_capability: "12.1"` (SM_121, explicitly annotated
*"unique to GB10, NOT sm_120"*). Its `always_resident` model list at line 86 pins
`qwen3-embedding:8b` (4700 MB) with `reason: "HiRAG, extract-worker, cipher-memory
embeddings"` — i.e. **the profile already assigns Spark the embedding work that Cipher
memory depends on.** Finding 1's unreachable Cipher and Spark's declared embedding
residency are two halves of the same undelivered pipeline.

### DEFECT — Spark's declared tailnet hostname does not match the tailnet

**MEASURED (B850, 2026-09-08), two independent sources:**

- `pmoves/config/profiles/dgx-spark-grace-blackwell.yaml:108` declares
  `hostname_pattern: "pmoves-gb10-spark"`.
- `tailscale status` on this node lists the peer as **`pmoves-spark`**.
- The repo already contradicts itself: `pmoves/config/profiles/laptop-4090.yaml:150,152`
  refers to the node as `pmoves-spark` and sets `tailscale_host: pmoves-spark`.

Anything resolving Spark by the declared `hostname_pattern` will miss. The 4090's
profile is right and Spark's own profile is wrong, which is the worse direction — the
authoritative record for a node is the one that is incorrect. Fixing it is a
one-line change in `dgx-spark-grace-blackwell.yaml`; it is **not** made here (this
task is documentation only) and should be verified against the tailnet from a second
node before landing, in case `pmoves-gb10-spark` is a planned rename rather than a
typo.

---

## Finding 5 — Harness bugs found in our own instruments

Recorded because these recur, and both are cases where the *instrument* was the
defect. This fleet's usual failure is a check that cannot pass
(`project_cipher_preflight_cannot_pass`); these are its neighbours.

### 5a. `.conclusion // .status` does not fall through on a running check

**REPORTED.** GitHub's GraphQL check rollup renders a not-yet-completed check's
`conclusion` as an **empty string**, not `null`. jq's `//` operator falls through only
on `null` and `false` — an empty string is neither. So:

```jq
.conclusion // .status      # WRONG: yields "" for a running check
(.conclusion | select(. != "")) // .status   # correct
```

**The lesson is the severity, not the bug.** In the harness where this was found, the
decision predicate was a *separate* expression that counted `!= "SUCCESS"`. An empty
string is not `"SUCCESS"`, so a running check was still counted as not-passing. The
bug was **cosmetic — it mis-displayed a state, it did not open a gate.** Record it
that way. Reporting a display bug as a fail-open defect is its own kind of wrong fact,
and it inflates the apparent danger of the tool.

**UNVERIFIED at write time.** No in-flight check existed on any open PR when this was
written; every `CheckRun` entry sampled on PR #3002 was `COMPLETED` with a non-empty
string conclusion. Re-verification is one command against any PR with a running job:

```sh
gh pr view <N> --json statusCheckRollup \
  -q '.statusCheckRollup[] | select(.__typename=="CheckRun") | [.name,.status,(.conclusion|type),(.conclusion|tostring)] | @tsv'
```

### 5b. A superseded (concurrency-cancelled) run and the check-name discriminator

**REPORTED (the observation).** On PR #3000, `claude-review` was **cancelled at
15:07:59** and then **succeeded at 15:09:34 on the identical head SHA** — the first
run was killed by workflow concurrency when the second superseded it. A tool that
takes the *worst* conclusion across same-named runs would treat that check name as
permanently poisoned.

**CORRECTION — this behaviour is not in `pr_closeout.py`.** The claim carried into
this task was that `pmoves/tools/pr_closeout.py` takes the worst conclusion across
same-named checks. **MEASURED (repo):** it does not.

- **Primary path.** `_fetch_required_checks` (`pr_closeout.py:341`) shells out to
  `gh pr checks <N> --required --json name,state,bucket,link,workflow`. Whatever
  same-name dedup happens, happens inside `gh` / the GraphQL rollup — not in our code.
- **REST fallback path.** `_required_checks_from_rest` (`pr_closeout.py:233`) builds
  `by_name[str(run["name"])] = run` — a plain **last-wins overwrite** in iteration
  order, not a worst-wins aggregation. It also passes **no `filter=` parameter** to
  `GET /repos/{repo}/commits/{sha}/check-runs`, so GitHub's default `filter=latest`
  applies and the endpoint returns only the most recent run per name.
- **Corroborating measurement.** `gh pr view 3000 --json statusCheckRollup` today
  returns exactly **one** `claude-review` entry, `COMPLETED` / `SUCCESS`. The rollup
  itself collapses same-named runs.

So: **do not "fix" `pr_closeout.py` for this.** There is nothing there to fix, and a
speculative patch would add a dedup rule to code that currently defers correctly to
GitHub's own latest-per-name semantics.

The original 15:07:59 / 15:09:34 pair could **not be reproduced** at write time —
#3000 has since acquired a newer `claude-review` run (started 19:03:18Z, completed
19:12:31Z, SUCCESS) and the rollup surfaces only that one. The observation is recorded
as REPORTED and the code claim is marked **NOT SUBSTANTIATED**.

**The discriminator is still worth having**, wherever same-name collapsing does turn
out to matter (a custom aggregator, a cached rollup, a log scrape): a superseded run
is identifiable by **matching `head_sha` plus earlier start time** against a later run
of the same name. Same SHA + earlier start + `CANCELLED` = superseded, not failed.
Encode that as the test, not "ignore cancellations", which would also swallow a real
manual cancel.

---

## Open items (documentation only — none actioned here)

| # | Item | Owner |
|---|---|---|
| 1 | Re-authenticate `pmoves-z890` (expired tailnet node key) | Operator, on Z890 |
| 2 | Bring Cipher up on Z890 after (1); verify `/mcp/sse` 200 with bearer | Z890 |
| 3 | Decide the reachability model for node-private services (per-service tailnet identity vs a reverse proxy vs binding change) | Fleet design lane |
| 4 | Document `hardware_requirements` in `ROOM_MANIFEST_CONTRACT.md` | `room-portability-delivery-2` (in flight) |
| 5 | Fix `hostname_pattern` in `dgx-spark-grace-blackwell.yaml` (`pmoves-gb10-spark` → `pmoves-spark`), after confirming it is a typo not a planned rename | Spark or fleet-config lane |
| 6 | Re-test the roster-sweep / OOM-resume hypothesis once a reachable Cipher exists | Whoever holds the Cipher lane |

## Cross-references

- `.claude/mcp.json:5` — the `pmoves-cipher` `_note`; the fullest existing record of
  Cipher's auth posture and the reason the bearer is bare.
- `pmoves/docs/operations/CIPHER_AUTH_RUNBOOK.md` — Cipher auth runbook.
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — room manifest contract (portability
  mandate at line 55). **Not edited by this document.**
- `pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md` — the
  `hardware_requirements` design spec.
- `pmoves/config/profiles/` — per-node hardware and service declarations.
