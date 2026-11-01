# Carry-Over Closure — Design Specification

**Date:** 2026-11-01
**Branch:** `fix/carry-over-closure`
**Base:** `origin/main` @ `2020a9103a96d1de59858c4d88c8e371710012b9`
**Author of the ask:** DARKXSIDE (operator), post-merge message on PR #3440
**Status:** approved design, written to spec for review

---

## 0. Why this lane exists

PR #3440 merged and closed the runbook-drift queue. Its post-merge message left
four carry-over items, each of which the operator then reaffirmed:

| # | Item | Operator words |
|---|------|----------------|
| 1 | 8 unbuildable image-matrix entries | "we need to address" |
| 2 | 25 Windows-only compose-smoke failures + `validate_service_tools_packaging.py` cp1252 | "we need to address" |
| 3 | GH App installation state on the newly-scoped repos (401 from this host) | "we need to address" |
| 4 | `docker-compose.yt-cookies.yml:46` — latent second claimant of 8115 | "we have a port registry, docker has dynamic ports, there should be no hard coded ports, and we have tooling that gets all the params — lets address this" |

A fifth ask was added mid-lane: set up the **MiniMax CLI** and focus on the
**MiniMax x PMOVES integration**.

### Standing rules this lane obeys

- **No workarounds.** Every fix carries SDK + doc provenance.
- **A number in prose is a claim.** Every count below is produced by an
  instrument committed in this tree. None is hand-written.
- **A measurement whose instrument is not committed is not a measurement.**
- **A gate that cannot read its input fails closed** — at file *and* entry
  granularity.
- **A mutation must revert the WIRING**, and the revert must be *proven* to
  kill a NAMED test.
- **An audit and the thing it audits must measure the same thing.**
- Collateral defects found in scope are fixed in scope, not deferred.

---

## 1. Measured baseline

All figures below are reproducible from the instruments named beside them.
Where a figure was wrong in an earlier draft of this spec, the correction is
recorded rather than quietly overwritten.

### 1.1 The 25 compose-smoke failures — ONE root cause

`pmoves/tests/smoke/test_compose_structure.py` and
`pmoves/tests/smoke/test_port_conflicts.py` fail on this host: **25 failed,
2 passed**.

**Proof of a single root cause:** re-running the same 27 tests with
`PYTHONUTF8=1` (which makes every `open()`/`read_text()` decode as UTF-8)
gives **27 passed**. The failures are therefore not logic failures — they are
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f` from text-mode
reads that omit `encoding=`. Python's default locale encoding on this host is
cp1252; the compose YAML contains UTF-8.

An earlier draft of this spec claimed a second root cause (compose merge tags
`!reset` / `!override` rejected by `yaml.safe_load`). **Measured and
withdrawn:** `yaml.safe_load` on `pmoves/docker-compose.yml` succeeds. The
merge tags exist in exactly three optional overlays
(`docker-compose.amd.yml`, `docker-compose.amd-voice.yml`,
`docker-compose.hardened.yml`), none of which the failing tests read.

The same defect exists in `pmoves/scripts/validate_service_tools_packaging.py`
line 45 (`COMPOSE_FILE.read_text()` — the file's other three reads already
pass `encoding="utf-8"`) and in `pmoves/scripts/port_allocator.py`
(2 sites).

**Class size** (AST scan of `pmoves/`, excluding `docs/`): **730** text-mode
calls without an explicit `encoding=` across **207** files.

### 1.2 The port landscape

Measured across **59** compose files: **262** published-port stanzas.

| Class | Count |
|---|---|
| Host port parameterised (`${VAR:-default}`) | 191 |
| Host port a **bare literal** | 71 |
| Host port **dynamic** (Docker assigns; container-port-only form) | **0** |

The "docker has dynamic ports" capability is entirely unused in this repo
today.

**The 8115 claimants — 3 stanzas, all with a bare-literal host port:**

| File | Service | Entry |
|---|---|---|
| `pmoves/docker-compose.yml` | `node-registry` | `${NODE_REGISTRY_BIND:-0.0.0.0}:8115:8115` |
| `pmoves/docker-compose.core.yml` | `node-registry` | `${NODE_REGISTRY_BIND:-0.0.0.0}:8115:8115` |
| `pmoves/docker-compose.yt-cookies.yml` | `yt-cookie-refresher` | `${YT_COOKIE_REFRESHER_BIND:-127.0.0.1}:8115:8115` |

Only the *bind address* is a parameter; the *port* is a literal in all three.

**Two competing "port registries" — neither complete:**

| Registry | Services | Notes |
|---|---|---|
| `pmoves/tests/utils/service_catalog.py` | 45 | imported by 11 files |
| `pmoves/scripts/port_allocator.py::DEFAULT_PORTS` | 40 | has the dynamic-port strategy + env-override generator |

Zero value drift on the 32 names they share. But the catalog holds **13** the
allocator lacks (including `node-registry`), and the allocator holds **15** the
catalog lacks. Of the **125** compose services that publish a port, **91**
appear in **neither**.

The house convention for a parameterised host port already exists:
`"${SUPABASE_DB_BIND:-127.0.0.1}:${SUPABASE_DB_PORT:-54322}:5432"` — bind
address and host port are variables; the container port is a literal.

### 1.3 The real repo universe (correction to the operator's own correction)

`pmoves/config/fork_registry.json`:

| Population | Count |
|---|---|
| Registry forks | **86** (35 `sync: true`, 51 `sync: false`) |
| `_first_party` (PMOVES-built, no upstream) | **9** |
| **Universe** (forks + first-party) | **95** |
| `_excluded` | **1** — `Pmoves-cipher`, held **outside** `forks`; excluded from *syncing* (no common ancestor with upstream), not from existence |

The **39** is the *workflow sync scope* — a subset, not the universe. The
`fork-sync.yml` workflow's `FORKS` block and its App `repositories:` scope both
hold **39** entries with **identical membership**.

**New drift found:** 4 of those 39 are marked `sync: false` in the registry —
`PMOVES-Jellyfin`, `PMOVES-crush`, `PMOVES-headscale`, `PMOVES.YT` — while
**0** registry `sync: true` entries are missing from the workflow. The
registry's `sync` flag and the workflow's scope disagree for 4 repos.

`PMOVES.YT` is also one of the eight image-matrix gap entries (item 1).

### 1.4 GH App credentials — absent on this host

`GH_APP_ID`, `GH_APP_CLIENT_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_SEC` are
absent from process, user and machine environment; `~/.pmoves` does not exist.
That is why `gh api repos/OWNER/REPO/installation` returns **401 "A JSON web
token could not be decoded"** — the endpoint requires an App JWT.

The `gh` CLI token *is* org-admin (`admin:org`), but
`GET /orgs/POWERFULMOVES/installations` returns **404**; that endpoint needs
the `user`/`read:org` scope the CLI's OAuth token lacks.

CI already mints an App token (`build-images.yml`, `fork-sync.yml`), so the
installation is introspectable **in CI**, where the key exists.

### 1.5 MiniMax CLI — already installed and authenticated

Verified on this host:

| Step | State |
|---|---|
| `npm install -g mmx-cli` | **Already done** — `mmx 1.0.25` at `C:\Users\russe\AppData\Roaming\npm\mmx.ps1` |
| `mmx auth login` | **Already done** — `mmx auth status` reports `method: api-key`, `source: config.json` |
| `npx skills add MiniMax-AI/cli -y -g` | **Already done** — `C:\Users\russe\.minimax\skills\mmx-cli` |
| `mmx quota` | **Works** — M Plan usage shown |

Quota snapshot (`mmx quota`): the `general` pool reports **99%** of the current
interval remaining and **43%** of the weekly window remaining; a `video` pool
is also reported. The credential itself is masked by the CLI
(`sk-c...bCtM`) and was never read, printed or stored by this lane.

**No login prompt is required.** The operator was asked to run `mmx auth
login` only if this had been missing; it was not.

### 1.6 MiniMax CLI surface — the PMOVES doc has drifted from the CLI

`pmoves/docs/services/MMX_CLI_SURFACE.md` is a claim about the CLI's command
tree. Compared against the installed `mmx` v1.0.25, it is stale:

| Documented | Installed | Status |
|---|---|---|
| `mmx music generate` | no `music` resource | **documented only** |
| `mmx speech clone --sample` | `speech synthesize`, `speech generate`, `speech voices` | **documented only** |
| `mmx speech list-voices` | `speech voices` | **renamed** |
| `mmx search web`, `mmx search news` | `search query`, `search web` | **renamed / partial** |
| `mmx config set, get` | `config show`, `set`, `export-schema` | **partial** |
| `mmx help --command <name>` | `mmx <resource> <command> --help` | **documented only** |
| version `v1.0.19` | `v1.0.25` installed | **stale** |

Undocumented in the PMOVES doc but present in the CLI: `text repl`,
`speech generate`, `config export-schema`, and the whole `agent` resource
(`agent setup`) — which `pmoves/tools/models/provider_catalog.yaml:504`
already references as `mmx agent setup --help`.

The PMOVES side of the integration is otherwise real: `pmoves/tools/mavis_collection_resolve.py`
shells out to `mmx auth status`, `mmx quota show` and `mmx text chat`, and
`~/.mmx/config.json` is the declared single credential source across
`pmoves/tools/models/*.yaml`.

---

## 2. Design

One branch, one PR, five commits, each independently reviewable and
revertible. PR #3440 closed five findings plus two baselines in a single PR;
this is one operator directive and the same shape.

Ordering is load-bearing: commit 1 makes the compose smoke suite green, which
is what commits 2 and 3 are then verified by.

### Commit 1 — Windows compose-smoke + cp1252 *(item 2)*

1. `pmoves/tests/smoke/test_compose_structure.py` — 4 sites get
   `encoding="utf-8"`.
2. `pmoves/tests/smoke/test_port_conflicts.py` — 5 sites.
3. `pmoves/scripts/validate_service_tools_packaging.py:45` — 1 site (the named
   defect).
4. `pmoves/scripts/port_allocator.py` — 2 sites (in scope: it is the ports
   tooling commit 2 touches).
5. **New** `pmoves/tools/windows_encoding_ratchet.py` — AST scan for text-mode
   `open()`/`read_text()`/`write_text()` lacking an explicit `encoding=`.
   - Fails on a **new** gap.
   - Baseline file for the pre-existing population; a **fixed** gap fails until
     it is dropped from the baseline (same contract as
     `pmoves/configs/command_anchors/_known_gaps.yaml`).
   - **Fails closed**: unreadable or unparseable input is an error, never a
     silent skip. Binary-mode calls are excluded by mode, not by guesswork.
6. Tests in `pmoves/tests/tools/test_windows_encoding_ratchet.py`, plus a
   mutation-kill harness proving the revert kills a NAMED test.

**Acceptance:** the 27 smoke tests pass on this host; the ratchet is green
against the baseline; a new gap turns it red.

### Commit 2 — Ports *(item 4)*

1. **New canonical** `pmoves/configs/ports.yaml`:

   ```yaml
   version: 1
   services:
     node-registry:
       container_port: 8115
       host_port: 8115
       bind_var: NODE_REGISTRY_BIND
       port_var: NODE_REGISTRY_PORT
     yt-cookie-refresher:
       container_port: 8115
       host_port: 8126
       bind_var: YT_COOKIE_REFRESHER_BIND
       port_var: YT_COOKIE_REFRESHER_PORT
   ```

   `host_port: null` means **dynamic** — Docker assigns a free host port.

2. `pmoves/tests/utils/service_catalog.py` and
   `pmoves/scripts/port_allocator.py` **read** `ports.yaml` at import time.
   One runtime source; no code generation step to drift.

3. Compose: every published host port becomes
   `"${<PORT_VAR>:-<registry default>}:<container_port>"`. The ratchet proves
   the inline default equals the registry value, so the registry is the
   authority and the compose mirror cannot drift.

4. **The 8115 collision.**
   - `node-registry` keeps **8115** — it is fleet-facing, and PR #3440 just
     moved six consumer defaults onto it.
   - `yt-cookie-refresher` moves to **8126** (measured free) and its
     `port_var` is declared in the registry.
   - The refresher **is** reached from the host:
     `pmoves/mk/yt-cookies.mk:68` curls
     `http://localhost:${YT_COOKIE_REFRESHER_PORT:-8115}/refresh`. That
     variable already existed but was undeclared in the registry — the house
     convention was half-applied.
   - A service moves to the **dynamic** form when **no** PMOVES component
     addresses it by a stable host port: no make target, runbook, monitoring
     scrape, CI step or peer service names it. The criterion is measured
     (grep the tree for the port and the service name), not judged — and the
     ratchet records a dynamic service's container port so the peer-DNS path
     stays discoverable.

5. **New** `pmoves/tools/port_registry_ratchet.py` — fails when:
   - a compose host port is a bare literal;
   - a compose host-port default ≠ the registry value;
   - two services claim the same host port within one effective stack;
   - a registry entry is orphaned (declared but published nowhere);
   - a registry entry has no `port_var` but its compose stanza hard-codes one.
   It uses the **same** compose loader as the smoke tests.

6. Docs updated where the port is quoted:
   `pmoves/docs/services/pmoves-yt/RUNBOOK.md`,
   `pmoves/docs/operations/YT_COOKIES_RUNBOOK.md`.

**Preserved:** `pmoves/tests/tools/test_node_registry_deployment.py` already
asserts the collision-over-default-stack rule and must stay green.

### Commit 3 — Image matrix *(item 1)*

1. **6 path fixes** in `pmoves/images.yaml` — `pmoves-archon`,
   `pmoves-yt`, `pmoves-jellyfin-ai-media-stack`, `pmoves-botz`, `pmoves-dox`,
   `pmoves-remote-view`. Each candidate Dockerfile **already exists at that
   entry's pinned commit**; the pick is made from the candidate set and the
   evidence (which candidate, and why it is the service image) is recorded.
2. **2 new Dockerfiles** authored in `POWERFULMOVES/PMOVES-HiRAG` and
   `POWERFULMOVES/PMOVES-Deep-Serch`, their submodule pins bumped, and the
   matrix updated. This is forced by the build contract: the build context
   **is** the submodule at its pinned gitlink
   (`context: ${{ matrix.repo && format('{0}/{1}', github.workspace, matrix.repo) || matrix.context }}`
   with `submodules: recursive`), so a Dockerfile that does not exist at the
   pinned commit cannot be built from anywhere else.
3. `pmoves/configs/image_staleness/_known_gaps.yaml` — all **8** entries
   removed, leaving **0** known gaps.

### Commit 4 — GH App installation *(item 3)*

**New** `pmoves/tools/gh_app_installation_audit.py`:

- Mints the App JWT with the **existing** `build_app_jwt` in
  `pmoves/tools/gh_app_token.py` (RS256 via PyJWT — no hand-rolled crypto).
- Reads `GET /app/installations/{id}` and
  `GET /app/installations/{id}/repositories`.
- Asserts the installation's repository set against the **real universe**:
  the registry's **86** forks + **9** first-party = **95**. The **39** is the
  workflow's *sync scope* and is asserted separately as a subset that must be
  inside the installation. (`Pmoves-cipher` is held outside the registry in
  `_excluded` because it cannot sync via the merge API; the audit names it as
  a known exclusion rather than silently dropping it.)
- The **4** repos where the registry's `sync` flag and the workflow scope
  disagree (`PMOVES-Jellyfin`, `PMOVES-crush`, `PMOVES-headscale`,
  `PMOVES.YT`) are surfaced by the same audit rather than left implicit.
- The CHIT route is the credential path: `pmoves/tools/chit_sync_workflow_bundle.py`
  decodes the workflow-generated CHIT bundle into `env.shared`
  (`GH_APP_ID` / `GH_APP_SEC` / `GH_APP_INSTALLATION_ID`). The audit reads the
  same params.

Wired into CI, where the App token already exists.

**Honesty clause:** this audit **cannot be verified from this host** (no
`GH_APP_SEC` present). The verdict reported is the CI run's, not a local
claim. The tool must fail closed when the key is absent — never report
"verified" on an unrun check.

### Commit 5 — MiniMax x PMOVES surface parity

1. `pmoves/docs/services/MMX_CLI_SURFACE.md` — correct the command tree to
   the installed CLI: drop `music`, rename `speech list-voices` → `speech
   voices`, replace `search news` with `search query`, fix the `config`
   subcommands, replace `mmx help --command` with the real
   `mmx <resource> <command> --help`, and record the version as
   "as installed" rather than a pinned old number.
2. **New** `pmoves/tools/mmx_surface_ratchet.py` — compares the doc's
   declared command tree against the live `mmx --help` /
   `mmx <resource> --help` output and fails on drift. It is the same
   "a number in prose is a claim" rule applied to a command tree: the doc is
   a claim about a binary, and the binary is the truth.
   - Skips (with a named reason) when `mmx` is not on `PATH` — never silently.
   - Fails closed when `mmx` exists but its help cannot be parsed.
3. The MiniMax CLI setup state is recorded in the spec and in the LEARNINGS
   manifest — already installed, already authenticated, skill present, quota
   confirmed.

---

## 3. Provenance requirements (every commit)

- `pmoves/docs/AGENTS/carry_over_closure_LEARNINGS.md` — house taxonomy:
  4 buckets x 5 classes (reasoning-gap, semantic-naming drift,
  contract-correctness, defense-in-depth, pattern-conformance).
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — one row per commit, filed with
  `pmoves/tools/register_append.py` (clock-read timestamp, never hand-typed),
  single-line rows.
- A **mutation-kill harness** per fix: revert the WIRING, assert a **named**
  test goes red, assert byte-exact restore.
- Every count in prose computed by an instrument **committed in this tree**;
  a test recomputes each cited figure so the prose cannot rot.

## 4. Acceptance criteria

1. `pmoves/tests/smoke/test_compose_structure.py` and
   `test_port_conflicts.py` — **27 passed** on this Windows host.
2. The encoding ratchet is green against its baseline and red on a new gap.
3. The port ratchet is green; no compose host port is a bare literal; no two
   services in one effective stack share a host port; **8115** has exactly
   one claimant in the whole compose set.
4. `pmoves/configs/image_staleness/_known_gaps.yaml` holds **0** entries, and
   `image-staleness-ratchet` reports 0 undecided and 0 drifted.
5. The GH App audit fails closed without a key and reports the real universe
   when run with one.
6. The mmx surface ratchet is green against the corrected doc.
7. Whole-tree test run shows **no new failures** against `origin/main`.
8. Required contexts green: `python-tests`, `hardening-validation`, `verify`,
   `submodule-gitlink-gate` (+ `merge-decision`).

## 5. Out of scope

- Fixing the other **91** compose services that are absent from the registry
  beyond the ratchet baseline — the ratchet surfaces them; migrating every
  overlay's port scheme is a separate lane.
- The `gnu`/`head` tooling gap on this host.
- Regenerating `research/runbook_drift_report.json` (stale before this lane).
