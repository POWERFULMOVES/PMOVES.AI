# PMOVES-registry — Submission Contract, Read From Source (2026-09-22)

**Read date:** 2026-09-22
**Reader:** PMOVES-SPARK (node identity), operating surface OpenRoom
**Task:** `t-20260922T123842Z-3f9a2c7d41be` — goal `g-20260922T123542Z-cb95b8fe02be7bfa` round 1, criterion **SC-1**
**Purpose:** replace every recollection-sourced description of the `PMOVES-registry` submission contract with quoted source at a recorded commit.

> **Boundary.** Every claim below cites either (a) the registry checkout at the recorded commit, or (b) two in-tree **non-submodule** files: `pmoves/tools/acp_registry_map.py` and `pmoves/mk/infra.mk`. This document asserts nothing about any PMOVES submodule. `make -C pmoves submodule-integrity` was run anyway for the log and exited **0** (`gitlinks mapped (normalized): 81; uninitialized: 0; drifted: 0; conflicts: 0`).
>
> **No credential values appear anywhere in this document.** The auth requirement below is described purely as a *declaration mechanism* (a handshake response field and its permitted type vocabulary).

---

## 0. Checkout provenance

| Item | Value |
|---|---|
| Path | `/home/powerfulmoves/agent-zero/PMOVES-registry` |
| How that path is canonical | `pmoves/mk/infra.mk:682` — `ACP_REGISTRY_PATH ?= ../../PMOVES-registry` (relative to `pmoves/`, i.e. a sibling of the repo root). Independently, `pmoves/tools/acp_registry_map.py:32-33` — `REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]` / `DEFAULT_REGISTRY = REPO_ROOT.parent / "PMOVES-registry"`. Both resolve to the same directory. |
| Clone form | **plain sibling clone**, `git clone https://github.com/POWERFULMOVES/PMOVES-registry.git`. Not a submodule; `.gitmodules` untouched. |
| Origin | `https://github.com/POWERFULMOVES/PMOVES-registry.git` |
| Default branch | `main` (`refs/remotes/origin/HEAD -> refs/remotes/origin/main`) |
| **HEAD commit** | **`a5cc0728099ed744b5261cbfc4a2cdf9be1e07d4`** |
| HEAD subject | `feat(harness): uv-managed tooling venv guard for workflow scripts (#1)` — POWERFULMOVES, 2026-09-18T11:17:55-04:00 |
| Total history | 1807 commits |
| Upstream compared | `agentclientprotocol/registry` @ `f5638936006cb80e116ecaa68cb3a2ebcaf737d6` (fetched 2026-09-22; upstream commit date 2026-09-22T12:28:57Z) |

All `file:line` citations below are relative to that checkout root unless prefixed `pmoves/`.

---

## 1. The manifest schema

**Real path and format:** `agent.schema.json` at the **registry root** — JSON Schema draft-07, JSON format. There is **no** `schemas/` directory and **no** YAML/TOML variant.

`agent.schema.json:1-7`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://cdn.agentclientprotocol.com/registry/v1/latest/agent.schema.json",
  "title": "ACP Agent",
  "description": "Schema for ACP agent registry entries",
  "type": "object",
  "required": ["id", "name", "version", "description", "distribution"],
```

The per-entry file is `<id>/agent.json` (`CONTRIBUTING.md:7-15`). A second root schema, `registry.schema.json`, describes the *built index*, not a submission.

### Required keys and their value domains

| Key | Required? | Domain | Citation |
|---|---|---|---|
| `id` | yes | string, `"pattern": "^[a-z][a-z0-9-]*$"` — lowercase, must start with a letter | `agent.schema.json:18-22` |
| `name` | yes | string, `minLength: 1` | `agent.schema.json:23-27` |
| `version` | yes | string, `"pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"` — strict 3-part numeric semver, stable channel | `agent.schema.json:28-32` |
| `description` | yes | string, `minLength: 1` | `agent.schema.json:33-37` |
| `distribution` | yes | object, `minProperties: 1`, `additionalProperties: false`, keys restricted to `binary` / `npx` / `uvx` | `agent.schema.json:68-83` |
| `license_url` | **conditionally required** — see §3 | string, `format: uri` | `agent.schema.json:8-16`, `:59-63` |
| `repository` | no | string, `format: uri` | `agent.schema.json:38-42` |
| `website` | no | string, `format: uri` | `agent.schema.json:43-47` |
| `authors` | no | array of string | `agent.schema.json:48-54` |
| `license` | no | string — "SPDX license identifier or 'proprietary'" | `agent.schema.json:55-58` |
| `icon` | no *in schema* — but an `icon.svg` **file** is mandatory (§7) | string; "set automatically by the build from the required icon.svg file" | `agent.schema.json:64-67` |
| `preview` | no | object, requires `version` + `distribution`; preview distribution accepts **only** `npx`/`uvx`, not `binary` | `agent.schema.json:84-86`, `:89-115` |

**Note on `additionalProperties`.** The top-level object does **not** set `additionalProperties: false`, so unknown top-level keys are not schema-rejected. `distribution` and every nested definition **do** set it, so unknown keys *inside* `distribution` are rejected.

---

## 2. The `distribution` declaration

Exactly three accepted forms, enumerated by `agent.schema.json:71-82`:

```json
      "properties": {
        "binary": { "$ref": "#/definitions/binaryDistribution" },
        "npx":    { "$ref": "#/definitions/packageDistribution" },
        "uvx":    { "$ref": "#/definitions/packageDistribution" }
      },
      "additionalProperties": false
```

At least one must be present (`minProperties: 1`, `agent.schema.json:70`).

### `binary` — what it requires

- Platform keys restricted by `propertyNames.enum` (`agent.schema.json:122-131`): `darwin-aarch64`, `darwin-x86_64`, `linux-aarch64`, `linux-x86_64`, `windows-aarch64`, `windows-x86_64`.
- Per platform, `"required": ["archive", "cmd"]` (`agent.schema.json:135`). `sha256` is **optional** in the schema (`:142-146`, `"pattern": "^[a-fA-F0-9]{64}$"`) though `CONTRIBUTING.md:195` says binaries "should pin" it. `args` (array) and `env` (object) optional; `additionalProperties: false`.
- Archive formats, `agent.schema.json:140`: "`.zip`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, or raw binary. Installer formats (`.dmg`, `.pkg`, `.deb`, `.rpm`) are not supported." `CONTRIBUTING.md:207` adds `.msi` and `.appimage` to the rejected list.
- Missing OS families are a **warning, not a failure** (`CONTRIBUTING.md:101`, `:211-212`).

### `npx` / `uvx` — what they require

`"required": ["package"]` (`agent.schema.json:170`); `package` is a string `minLength: 1` "Package name (with optional version)" (`:172-176`); optional `args`, `env`; `additionalProperties: false`.

### Cross-cutting distribution rules enforced by CI, not by the schema

From `CONTRIBUTING.md:214-234`:
- **Version matching** — distribution versions must match the entry `version`; binary URLs containing `/download/vX.Y.Z/`, npm `@scope/pkg@1.0.0`, and PyPI `pkg==1.0.0` / `pkg@1.0.0` are all checked.
- **No `latest`** — binary URLs must not contain `/latest/`; npm and PyPI must not use `@latest`.
- **URL accessibility** — binary archive URLs must return HTTP 200; npm packages must exist on registry.npmjs.org; PyPI packages on pypi.org. Skippable locally with `SKIP_URL_VALIDATION=1` (`build_registry.py:62`, `:236`).

---

## 3. Is `license_url` genuinely required?

**Yes — for every entry except one hardcoded exemption.** It is not in the flat `required` array; it is enforced by an `if`/`else` block.

`agent.schema.json:8-16`:

```json
  "if": {
    "properties": {
      "id": { "const": "dimcode" }
    },
    "required": ["id"]
  },
  "else": {
    "required": ["license_url"]
  },
```

Restated in prose at `CONTRIBUTING.md:137` (required-fields table) and `CONTRIBUTING.md:140`: "DimCode (`id: dimcode`) is exempt from the `license_url` requirement."

**For a PMOVES submission, `license_url` is required.** Domain: string, `format: uri`, "URL to the license text or terms of service" (`agent.schema.json:59-63`).

---

## 4. The auth declaration requirement

This is the contract element most likely to be misread, because **it is not a manifest field at all**. Nothing in `agent.schema.json` mentions auth. The requirement is enforced at runtime, against the agent's own ACP handshake.

### The rule

`AUTHENTICATION.md:7`:

> To be listed in this registry, an agent **must support at least one of the following authentication methods**: **Agent Auth** or **Terminal Auth**. While the [ACP specification](https://agentclientprotocol.com/rfds/auth-methods) defines additional authentication methods (such as Environment Variable Auth), only Agent Auth and Terminal Auth are currently supported by this registry.

`README.md:7-11` restates it as the registry's defining curation rule ("This registry maintains a curated list of **agents that support user authentication** … All agents are verified via CI to ensure they return valid `authMethods` in the ACP handshake").

### The enforcing code

In the registry repo (`PMOVES-registry`, not this repo), `client.py` under its `.github/workflows/`, lines 102-112:

```python
def validate_auth_methods(auth_methods: list[AuthMethod]) -> tuple[bool, str]:
    """Validate that at least one auth method has type 'agent' or 'terminal'."""
    if not auth_methods:
        return False, "No authMethods in response"

    valid_types = {"agent", "terminal"}
    methods_with_valid_type = [m for m in auth_methods if m.type in valid_types]
    ...
        types_found = [m.type for m in auth_methods]
        return False, f"No auth method with type 'agent' or 'terminal'. Found types: {types_found}"
```

Called from `client.py:283-289` against `result.get("authMethods", [])` on the `initialize` response.

### The mechanism vocabulary (no credential values — none exist here)

- The agent returns an `authMethods` array in its **`initialize`** response (`client.py:283`).
- Each element carries `id`, `name`, `description`, and a `type` (`AUTHENTICATION.md:34-41`, `:60-71`).
- Permitted `type` values for registry admission: **`"agent"`** or **`"terminal"`**.
- Type resolution order, `client.py:63-88`: explicit `type` field first; then `_meta` keys (`"terminal-auth"` → `terminal`, `"agent-auth"` → `agent`); otherwise **default to `"agent"`** for backward compatibility (`AUTHENTICATION.md:43`).
- `agent` = "Agent handles OAuth authentication flow" — agent runs a local HTTP callback server and opens the user's browser (`AUTHENTICATION.md:13`, `:22-28`).
- `terminal` = "Interactive terminal-based authentication" — declared with `args` (e.g. `["--setup"]`) and `env`, which **replace** the default args/env for the setup invocation (`AUTHENTICATION.md:14`, `:60-77`).

That is the whole element: a declared capability type, not a secret. A PMOVES submission must make its agent *return* one of these two types from `initialize`; there is nothing to write into `agent.json` for it.

---

## 5. The verifier

**The lead is correct on all three counts, with the path now pinned.**

| Aspect | Value | Citation |
|---|---|---|
| Real path | `.github/workflows/verify_agents.py` (1156 lines) — it lives *inside* `.github/workflows/`, alongside the YAML, not in a `scripts/` or `tools/` directory | filesystem; `CONTRIBUTING.md:251` |
| Flag name | `--auth-check` — `action="store_true"`, "Verify ACP auth support instead of basic launch test" | `verify_agents.py:1028-1032` |
| CI invocation | `python3 .github/workflows/verify_agents.py --auth-check --agent "$AGENT_ID"` | `build-registry.yml:115` |
| Documented CI invocation | `python3 .github/workflows/verify_agents.py --auth-check` | `CONTRIBUTING.md:251` |
| Local single-agent | `python3 .github/workflows/verify_agents.py --auth-check --agent your-agent-id` | `CONTRIBUTING.md:264` |
| Local multi-agent | `python3 .github/workflows/verify_agents.py --auth-check --agent agent1,agent2` | `CONTRIBUTING.md:267` |

Other relevant flags:
- `--list-ids` — "Print non-quarantined agent IDs as a JSON array and exit" (`verify_agents.py:1039-1043`); used by CI to build the auth matrix (`build-registry.yml:73-77`).
- `--auth-timeout` (float, default `DEFAULT_AUTH_TIMEOUT`) (`verify_agents.py:1033-1038`).
- `--agent`/`-a`, `--verbose`/`-v`, `--clean-all` (`verify_agents.py:1004`, `:1026-1027`).

**Prerequisite:** `--auth-check` requires the `agent-client-protocol` package; without it the tool exits with "Error: --auth-check/--auth-only requires 'agent-client-protocol' package" (`verify_agents.py:1050-1051`, import guard at `:33-35`).

**Schema/build validator (separate tool):** `uv run --with jsonschema .github/workflows/build_registry.py` (`CONTRIBUTING.md:273`), with `SKIP_URL_VALIDATION=1` to skip reachability (`CONTRIBUTING.md:279`).

---

## 6. CI gating at PR time

Three workflow files exist. **Only one runs on a pull request.**

### `build-registry.yml` — the PR gate

Trigger block, `build-registry.yml:3-20`:

```yaml
on:
  push:
    branches: [main]
    paths:
      - "*/agent.json"
      - "*/icon.svg"
      - ".github/workflows/**"
      - "*.schema.json"
      - "quarantine.json"
  pull_request:
    branches: [main]
    paths:
      - "*/agent.json"
      - "*/icon.svg"
      - ".github/workflows/**"
      - "*.schema.json"
      - "quarantine.json"
  workflow_dispatch:
```

A submission PR adding `<id>/agent.json` + `<id>/icon.svg` matches the `pull_request` path filter, so all of the following run:

| Job | Runs on PR? | What it asserts | Citation |
|---|---|---|---|
| `lint-and-test` | yes | `ruff check .`, `ruff format --check .`, and `pytest tests/ -v` — all with `working-directory: .github/workflows` | `build-registry.yml:26-48` |
| `build` (Build & Validate) | yes, `needs: lint-and-test` | `uv run --with jsonschema .github/workflows/build_registry.py` — full schema + id + version + distribution + URL + icon validation; then `--list-ids` to emit the auth matrix | `build-registry.yml:50-77` |
| `verify-auth` | **yes** — `needs: build`, gated only by `if: needs.build.outputs.agent_ids != '[]'`, **no event condition** (as of `a5cc072`; see §12 on upstream drift) | one matrix leg per non-quarantined agent id, `timeout-minutes: 5`, `fail-fast: false`, running `verify_agents.py --auth-check --agent "$AGENT_ID"` | `build-registry.yml:89-115` |
| `upload` (S3/R2) | **no** | explicitly `(github.event_name == 'push' \|\| github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'` | `build-registry.yml:117-120` |
| `release` (GitHub Release) | **no** | same event/ref condition | `build-registry.yml:172-175` |

Artifact upload is likewise push/dispatch-only (`build-registry.yml:83`).

**Consequence for a PMOVES submission:** the live `--auth-check` handshake runs **on the PR itself**, not after merge — and it runs for *every* non-quarantined agent in the registry, not only the newly added one. A PMOVES agent must survive a real ACP `initialize` in a clean ubuntu-latest sandbox within 5 minutes.

### `daily-protocol-matrix.yml` — nightly, **not** on PRs

Trigger block, `daily-protocol-matrix.yml:1-7`:

```yaml
name: Nightly Protocol Matrix

on:
  schedule:
    # Run nightly after the hourly version update workflow.
    - cron: "15 5 * * *"
  workflow_dispatch:
```

Schedule + manual dispatch only. No `pull_request`, no `push`. Job `generate` has `timeout-minutes: 60` (`:37-39`). Its output lands in `.protocol-matrix/` (the repo carries `.protocol-matrix/latest.json`).

### `update-versions.yml` — hourly cron, **not** on PRs

`update-versions.yml:3-7`:

```yaml
on:
  schedule:
    # Run hourly at minute 0
    - cron: "0 * * * *"
  workflow_dispatch:
```

This is the machinery behind `CONTRIBUTING.md:153` ("versions are updated automatically every hour") — it checks npm, PyPI, and GitHub Releases and commits to `main`. Practical implication: **once merged, a PMOVES entry's `version` field stops being ours to hand-maintain**; a bot will bump it hourly from whichever distribution channel is declared.

---

## 7. The submission mechanism

**A pull request adding a directory to this repository.** Not an API call, not a form.

`CONTRIBUTING.md:3-54`, condensed:

1. Fork the repository (`:5`).
2. `mkdir <id>/` — "The directory name must match your entry's `id` field" (`:7-13`).
3. Create `<id>/agent.json` (`:15-32`).
4. **Add an icon (required)** — `<agent-id>/icon.svg`, **16×16**, **monochrome using `currentColor`** (`:34-50`). "Icons with hardcoded colors (`fill="#FF0000"`, `fill="red"`, etc.) will fail validation" (`:50`).
5. Submit a Pull Request; "The CI will validate your `agent.json` against the schema" (`:52-54`).

Enforcement of the two directory-coupled rules:

- id↔directory, `build_registry.py:510-511`:
  ```python
        elif agent_id != agent_dir:
            errors.append(f"Field 'id' ({agent_id}) must match directory name ({agent_dir})")
  ```
- icon presence, `build_registry.py:631-633`:
  ```python
        icon_path = entry_dir / "icon.svg"
        if not icon_path.exists():
            return None, [f"{entry_dir.name}/icon.svg is missing (icon is required)"]
  ```
  with content validation in `validate_icon()` (`build_registry.py:342-`) and the built `icon` URL injected from the file (`:782`).

**`icon.svg` is therefore a hard, blocking submission requirement that the JSON schema alone does not reveal.** Any plan derived from `agent.schema.json` in isolation will be missing it.

### Quarantine

`quarantine.json` at the registry root is an id→reason map that suppresses an entry from `--list-ids` / auth verification without deleting it (`registry_utils.py:328-341`, `verify_agents.py:957-984`). At this commit it holds 8 entries: `agoragentic-acp`, `crow-cli`, `deepagents`, `minion-code`, `qoder`, `vtcode`, `fast-agent`, `mistral-vibe`. It is in the `pull_request` path filter (`build-registry.yml:19`), i.e. changing it is itself a gated change.

---

## 8. Measured contents

| Measurement | Value | Method |
|---|---|---|
| Agent directories | **42** | `ls -d */ \| wc -l` at the checkout root |
| Directories carrying `agent.json` | **42** | `find . -maxdepth 2 -name agent.json \| wc -l`; the "dirs without agent.json" check returned empty |
| `agent.json` files repo-wide | **42** | `find . -name agent.json` (excluding `.git`) |
| Quarantined ids | 8 | `quarantine.json`: agoragentic-acp, crow-cli, deepagents, minion-code, qoder, vtcode, fast-agent, mistral-vibe |
| Non-quarantined (auth-matrix) ids | 34 | 42 − 8 |
| PMOVES / POWERFULMOVES entry present? | **No** | `grep -ril 'powerfulmoves\|pmoves' --exclude-dir=.git .` → **zero matches** anywhere in the tree, including README/CONTRIBUTING prose |

Full id list at `a5cc072`: `agoragentic-acp amp-acp antigravity-acp auggie autohand claude-acp cline codebuddy-code codex-acp cortex-code corust-agent crow-cli cursor deepagents devin dimcode dirac factory-droid fast-agent gemini github-copilot github-copilot-cli glm-acp-agent goose grok-build harn junie kilo kimchi kimi minimax-code minion-code mistral-vibe nova opencode pi-acp poolside qoder qwen-code sigit stakpak vtcode`

Non-agent root directories (correctly skipped by every consumer because they lack `agent.json`): `.github/`, `.protocol-matrix/`.

---

## 9. `pmoves/tools/acp_registry_map.py` vs. the real checkout

**The tool's expected layout matches the real checkout exactly. No mismatch found.** `--write` was **not** run; `make -C pmoves acp-registry-map` was **not** run.

| Tool expectation | Citation | Reality at `a5cc072` | Verdict |
|---|---|---|---|
| Registry is a sibling of the repo root named `PMOVES-registry` | `acp_registry_map.py:32-33` | cloned exactly there; agrees with `pmoves/mk/infra.mk:682` | match |
| One `<id>/agent.json` per agent, discovered by iterating the registry's direct children | `acp_registry_map.py:2-6`, `:45-58` (`for child in sorted(registry.iterdir()): agent_json = child / "agent.json"; if not agent_json.is_file(): continue`) | 42 children carry `agent.json`; `.github` and `.protocol-matrix` are silently skipped by the `is_file()` guard, which is the correct behavior | match |
| Directory name is the authoritative ACP id (`data["_acp_id"] = child.name`) | `acp_registry_map.py:56` | the registry enforces id == directory name at `build_registry.py:510-511`, so the tool's assumption is *backed by the registry's own gate* | match |
| Entries expose `name`, `repository`, `version` | `acp_registry_map.py:114-119` | all three present in the schema (`repository` optional — the tool already tolerates absence via `acp.get(...)` and `_repo_basename("")`) | match |
| Upstream is `agentclientprotocol/registry`, fork is `POWERFULMOVES/PMOVES-registry` | `acp_registry_map.py:4-5` | confirmed: `origin` is the fork, and the fork shares history with that upstream | match |

**Read-only run against the real checkout** (`uv run --with pyyaml python pmoves/tools/acp_registry_map.py --registry ../PMOVES-registry`, no `--write`):

```
ACP entries scanned: 42
  linked     1
  forked     0
  available  41
linked: kilo
(read-only; pass --write to update the artifact)
```

The scanned count (42) equals the measured directory count, confirming the parser sees the whole registry.

**One live observation, not a mismatch:** `EXPLICIT_BRIDGES` at `acp_registry_map.py:39-42` maps `"spynel": "PMOVES-spynel"`. There is **no `spynel` directory in the registry** at this commit, so that bridge is currently inert — it is forward-looking, and it would only activate if a `spynel` entry were submitted. Worth knowing before any later round reasons about what the map "should" output.

---

## 10. Adjudication of the ten inherited leads

Leads inherited from B850/Knuckles sessions and from `pmoves/docs/AGENTS/PMOVES-SPYNEL-VS-REGISTRIES-REVIEW-2026-09-21.md` §C.3 (which was written from web fetch + GitHub REST, not a checkout).

| # | Lead | Verdict | Citation / correction |
|---|---|---|---|
| 1 | Unmodified upstream fork | **contradicted** | The fork is **1 ahead, 25 behind** `agentclientprotocol/registry@f5638936` (`git rev-list --left-right --count HEAD...upstream/main` → `1  25`). The one fork-only commit is `a5cc072` "feat(harness): uv-managed tooling venv guard for workflow scripts (#1)", touching `.github/workflows/scripts/ensure-uv-venv.sh` (added), `run-protocol-matrix.sh`, `run-workflows-tests.sh`, `.gitignore`, `AGENTS.md`. **None of those files is a manifest, schema, or submission-gating rule**, so the submission contract read here is upstream's, unmodified — but the fork is *not* pristine and is behind by 25 commits. |
| 2 | ~40 agent directories | **confirmed (sharpened)** | Exactly **42**, each with `agent.json`. 34 are non-quarantined. |
| 3 | No PMOVES entry | **confirmed** | `grep -ril 'powerfulmoves\|pmoves' --exclude-dir=.git .` returns zero matches tree-wide. |
| 4 | PR a directory with a JSON manifest, not a live API | **confirmed** | `CONTRIBUTING.md:3-54`: fork → `mkdir <id>/` → `agent.json` → `icon.svg` → PR. **Correction/addition: `<id>/icon.svg` is an equally mandatory second file** (`CONTRIBUTING.md:34`, enforced `build_registry.py:631-633`), 16×16 and `currentColor`-monochrome. The lead names only the manifest. |
| 5 | Schema-validated `id` | **confirmed** | `agent.schema.json:18-22` — `"pattern": "^[a-z][a-z0-9-]*$"`. Plus CI-level uniqueness and id==directory (`build_registry.py:510-511`, `CONTRIBUTING.md:179-182`). |
| 6 | `distribution` of `binary`/`npx`/`uvx` | **confirmed** | `agent.schema.json:71-82`, `additionalProperties: false`, `minProperties: 1`. Refinement: the optional `preview` channel accepts **only** `npx`/`uvx` — `binary` is excluded there (`agent.schema.json:99-111`). |
| 7 | Required `license_url` | **confirmed, with one exemption** | Enforced via `if`/`else` on `id == "dimcode"` (`agent.schema.json:8-16`), not via the flat `required` array. Required for any PMOVES submission. |
| 8 | Mandatory Agent Auth or Terminal Auth declaration | **confirmed — but not a manifest field** | `AUTHENTICATION.md:7`; enforced at runtime by `client.py:102-112` (`valid_types = {"agent", "terminal"}`) against `authMethods` in the `initialize` response (`client.py:283-289`). Nothing in `agent.schema.json` mentions auth. **A submission cannot satisfy this by editing JSON** — the agent binary/package itself must return a qualifying `authMethods` entry. Undeclared `type` defaults to `"agent"` (`client.py:86-88`, `AUTHENTICATION.md:43`). |
| 9 | `verify_agents.py --auth-check` | **confirmed; path pinned** | Name and flag are exactly right. Full path is `.github/workflows/verify_agents.py` (`verify_agents.py:1028-1032`; CI call `build-registry.yml:115`). Requires the `agent-client-protocol` package (`verify_agents.py:1050-1051`). |
| 10 | Nightly protocol matrix | **confirmed** | `daily-protocol-matrix.yml:3-7` — `schedule: cron "15 5 * * *"` + `workflow_dispatch` only. No `pull_request` trigger. **But do not generalize it:** the *auth* matrix (`verify-auth` in `build-registry.yml:89-115`) **does** run on pull requests, over every non-quarantined agent. Treating "matrix ⇒ nightly only" would badly understate PR-time cost. |

---

## 11. What a PMOVES submission would have to satisfy (derived, not speculative)

Stated for the next round; every item traces to a citation above.

1. A directory named exactly the chosen `id`, matching `^[a-z][a-z0-9-]*$`.
2. `<id>/agent.json` with `id`, `name`, `version` (strict `X.Y.Z`), `description`, `license_url`, and `distribution`.
3. `<id>/icon.svg` — 16×16, square, `fill`/`stroke` limited to `currentColor` / `none` / `inherit`.
4. At least one of `binary` / `npx` / `uvx`, with a **reachable** artifact URL pinned to the declared version and no `latest`.
5. A running agent that answers ACP `initialize` with an `authMethods` entry of type `agent` or `terminal`, inside a clean ubuntu-latest sandbox, within the CI timeout.
6. Tolerance for the hourly version bot taking over the `version` field after merge.

Item 5 is the load-bearing one and is **not** satisfiable by manifest authoring alone.

---

## 12. Residual uncertainty

- `verify_agents.py --auth-check` was **not executed** against anything. This document records the contract that code enforces; it does not demonstrate any agent passing it. That demonstration belongs to a later round and is the stronger downstream check.
- The upstream comparison is a point-in-time fetch (upstream `f5638936`, 2026-09-22T12:28:57Z). The 25-commit gap moves continuously; the contract elements quoted here were not among the fork-only changes, but a future upstream commit could change them.
- `build_registry.py` (~800 lines) and `verify_agents.py` (1156 lines) were read at the points that answer this task's questions, not exhaustively. Additional non-blocking warnings likely exist that are not enumerated here.
- No edit, no `--write`, no PR, no `.gitmodules` change, and no manifest was authored. This document was left **untracked** in the working tree of branch `feat/comfyui-ui-to-api`.
