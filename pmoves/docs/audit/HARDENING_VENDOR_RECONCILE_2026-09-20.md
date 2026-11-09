# Hardening tooling vs vendor documentation - the diff

**Lane:** `docs/hardening-vendor-reconcile` - `B850-CLAUDE (Knuckles)` - 2026-09-20
**Scope:** the delta between what PMOVES' hardening tooling, CI and docs do, and
what **Docker's** and **GitHub's** own documentation says. Operator-requested.

## Why this document is not a restatement

A tool audited only against its own repository can confirm its own assumptions
and nothing else. This audit reads the vendors' primary sources first and asks
three questions, because in practice only the first ever gets asked:

1. **Vendor recommends -> we do not implement or check.**
2. **We implement -> the vendor has since changed, deprecated or contradicted it.**
   This is the direction that rots silently: a check written against older
   guidance keeps passing while the guidance moves.
3. **Our doc describes a protection our tooling does not enforce.** This fleet's
   standing defect class.

Every finding cites a vendor page by URL and section. Anything that could not be
anchored is marked **COULD-NOT-VERIFY** and is not asserted.

### Method, and its limits

Vendor pages were fetched directly (`docs.docker.com` serves each page as
Markdown at `<path>.md`; GitHub's docs were read from the `github/docs`
repository's own `content/` tree, which is the source those pages render from).
`WebFetch` is disabled in this session, so `curl` was used; the URLs and
retrieval are otherwise identical.

PMOVES-side claims were measured, not assumed. Specifically:

- Workflows were parsed as YAML, not grepped. A grep for `self-hosted` returns
  15 files; **11** of those matches are comments or unrelated text, and the real
  answer required reading `runs-on` per job. This is the near-miss-grep trap,
  and it fired here on the first attempt.
- Whether a check is **enforced** was decided by reading
  `pmoves/configs/branch_protection/pmoves_standard.json` and naming the job
  whose steps were read. FIRE, BLOCK and BYPASSABLE are treated as three
  separate properties throughout.
- Two properties below are **unenforced but not currently violated**. They are
  reported as exactly that, with the measurement that shows zero violations
  today. An honest latent gap is worth more than an inflated live one.

### The enforcement picture, measured

This matters before any finding, because the names collide:

| What | Where | Fires | Blocks merge | Bypassable |
|---|---|---|---|---|
| `hardening_ratchet.py` | job `hardening-validation` in `.github/workflows/merge-gate.yml:117-130` | yes, every PR (no `if:`, no path filter) | **yes** - listed in `pmoves_standard.json` required_status_checks, pinned to `integration_id: 15368` | yes - `bypass_actors` grants RepositoryRole 5 `bypass_mode: always` |
| `validate-hardening.sh` | job `Validate Hardening Patterns` in `.github/workflows/hardening-validation.yml:38` | only when a compose/Dockerfile path changes (`:6-21`) | **no** - not in required_status_checks | n/a |
| `validate-dockerfiles` | `hardening-validation.yml:95` | same path filter | **no** | n/a |
| `docker-bench` | `hardening-validation.yml:172` | same path filter | **no** - also absent from the `summary` job's `needs` (`:478`) | n/a |
| `validate-compose` (compose drift + split-overlay drift) | `hardening-validation.yml:338` | same path filter | **no** | n/a |
| `secrets_hardening_audit.py` | `pmoves/mk/codex.mk:69` (`make -C pmoves secrets-audit`) | **never in CI** - the script path appears in zero workflows | no | n/a |

The required check named `hardening-validation` is the **merge-gate.yml job**,
which runs `hardening_ratchet.py` and nothing else. The **file** named
`hardening-validation.yml` contributes **no** required check. Four hardening
jobs fire and none of them blocks.

---

## Findings, ranked

### HIGH

#### H1 - A fork PR can execute on the tailnet-connected self-hosted runner, and nothing enforces the guard three sibling workflows implement

| | |
|---|---|
| **Vendor source** | GitHub, *Secure use reference* -> **"Hardening for self-hosted runners"** - https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners |
| **Vendor text** | "self-hosted runners should almost never be used for public repositories on GitHub, because any user can open pull requests against the repository and compromise the environment." Self-hosted runners "can be persistently compromised by untrusted code in a workflow." |
| **PMOVES today** | `POWERFULMOVES/PMOVES.AI` is **public** (`visibility: public`, GitHub API, measured 2026-09-20). `.github/workflows/submodule-smoke.yml:41` - job `smoke-test`, `runs-on: [self-hosted, Linux, X64, ai-lab]`, trigger `pull_request`, gated **only** on `needs.gate-check.outputs.should_run == 'true'`, which is a check for the `upstream-update` **label**. It then checks out with `submodules: recursive` and runs against `github.event.pull_request.head.sha`. There is no fork test. |
| **Delta** | Three sibling workflows *do* guard, each differently: `branch-trail-emit.yml:35` uses `head.repo.fork == false`; `kilocode-review.yml:53` uses `head.repo.full_name == github.repository`; `integrations-ghcr.yml` gates its two self-hosted jobs on `github.event_name != 'pull_request'`. `submodule-smoke.yml` has none. Nothing asserts the invariant, so the fourth case is invisible. |
| **Severity** | **HIGH** |
| **Close it with** | **CI** (add the guard) + **TOOL** (a gate asserting every PR-triggered non-github-hosted job carries a fork guard - the three existing idioms show this will not be caught by convention) |

> A maintainer applies the label, so a human is in the loop. That mitigates but
> does not close it: the gate is "does this PR look like an upstream sync",
> not "is this code trusted", and the runner is on the tailnet.

#### H2 - The job named "Validate Hardening Patterns" cannot fail on anything the doctrine calls a requirement

| | |
|---|---|
| **Vendor source** | Docker, *Docker Engine security* -> **"Linux kernel capabilities"** - https://docs.docker.com/engine/security/#linux-kernel-capabilities |
| **Vendor text** | "The best practice for users would be to remove all capabilities except those explicitly required for their processes." |
| **PMOVES today** | `pmoves/scripts/validate-hardening.sh` increments `warnings` for a missing `user`, missing `read_only`, missing `cap_drop: ALL`, missing `no-new-privileges` and missing resource limits. It increments `errors` only at `:39` - when `user:` matches `^[0-9]+:[0-9]+$` **and** the uid is `0`. `:96` exits non-zero only `if [[ $errors -gt 0 ]]`. Run locally against the current tree: **`Summary: 112 passed, 43 warnings, 0 errors`, exit 0.** |
| **Delta** | Every property the vendor calls best practice is a warning. The only way to fail this gate is to write the literal string `user: "0:0"`. A `user: pmoves` (a name, not `uid:gid`) falls through the regex and is scored as neither pass, fail nor warn - silently. |
| **Severity** | **HIGH** |
| **Close it with** | **TOOL** (ratchet the warnings the way `hardening_ratchet.py` ratchets Dockerfiles: a baseline that may shrink and never grow) |

#### H3 - The hardened overlay covers 28 of 111 services, and the default start path does not apply it

| | |
|---|---|
| **Vendor source** | Docker, *Docker Engine security* -> **"Linux kernel capabilities"** (above); Docker, *Compose file reference* -> `cap_drop` https://docs.docker.com/reference/compose-file/services/#cap_drop and `read_only` https://docs.docker.com/reference/compose-file/services/#read_only |
| **PMOVES today** | `pmoves/docker-compose.yml` declares **111** services. `pmoves/docker-compose.hardened.yml` declares **28**, each carrying `user` + `read_only` + `cap_drop` + `security_opt` + `tmpfs` (28/28 on all five). **83 base services have no hardened override.** In the base file, 90 services declare `cap_drop` but only **4** declare `no-new-privileges`. The overlay is passed with `-f docker-compose.hardened.yml` on **5** Makefile targets (`pmoves/Makefile:3077, 3082, 3098, 3134, 3146`); the default `up` target (`pmoves/Makefile:2545-2550`) uses `$(DC)` without it. |
| **Delta** | `validate-hardening.sh` reads **only** `docker-compose.hardened.yml`, so its scope is those 28 services - 25% of the fleet - and nothing asserts that a service reaching production is inside that 25%, nor that the overlay was applied at all. Resource limits: `deploy:` appears on **0 of 28** hardened services, and the script's "No resource limits" warning fires for every one of them while exiting 0. |
| **Severity** | **HIGH** |
| **Close it with** | **TOOL** (assert coverage: every base service is either in the overlay or recorded as an exception, same ratchet shape) + **DOC** (the hardening docs describe protections that apply to a quarter of the stack on five non-default targets; say so) |

#### H4 - Workflow-level `permissions:` grants write scopes to five jobs, one of which no job uses

| | |
|---|---|
| **Vendor source** | GitHub, *Secure use reference* -> **"Use secrets for sensitive information" / Principle of least privilege** - https://docs.github.com/en/actions/reference/security/secure-use#use-secrets-for-sensitive-information |
| **Vendor text** | "It's good security practice to set the default permission for the `GITHUB_TOKEN` to read access only for repository contents. The permissions can then be increased, as required, for individual jobs within the workflow file." |
| **PMOVES today** | `.github/workflows/hardening-validation.yml:29-32` sets, at **workflow** level: `contents: read`, `security-events: write`, `pull-requests: write`. No job declares its own `permissions:`, so all five inherit. Only `validate-hardening` needs `pull-requests: write` (its PR-comment step, `:77-90`). **No job in the file writes a SARIF or any security event**, so `security-events: write` has no consumer at all. |
| **Delta** | Exactly inverted from the vendor's rule: broad at the top, never narrowed per job. `merge-gate.yml` shows the repo already knows the right shape - every job there sets `permissions: contents: read`, and `merge-decision` sets `permissions: {}`. |
| **Severity** | **HIGH** (privilege breadth on a public repo's PR surface; trivially closable) |
| **Close it with** | **CI** |

### MEDIUM

#### M1 - `validate-dockerfiles` judges the FIRST `USER`, which is the defect `hardening_ratchet.py` was written to catch

| | |
|---|---|
| **Vendor source** | Docker, *Dockerfile reference* -> **`USER`** - https://docs.docker.com/reference/dockerfile/#user |
| **Vendor text** | "The `USER` instruction sets the user name (or UID) ... to use as the default user and group **for the remainder of the current stage**." |
| **PMOVES today** | `.github/workflows/hardening-validation.yml:124-125` - `grep "^USER " "$f" \| head -1`. The **first** directive decides the verdict. `pmoves/tools/hardening_ratchet.py:120-121` takes `users[-1]`, and its module docstring (`:34-39`) explains why: `pmoves/images/jellyfin/Dockerfile` sets a non-root `USER` and then switches back with `USER root`. |
| **Delta** | Two checks in this repo disagree about what "the user" means, and the one that disagrees with the vendor is the one that is *not* a required check. Measured: **2** tracked Dockerfiles carry more than one `USER` (`pmoves/images/firefly-iii/Dockerfile` = root -> www-data; `pmoves/services/gpu-orchestrator/Dockerfile` = root -> pmoves). Both are root-first, so `head -1` would *fail* them - neither is in the 7-file matrix (`:104-110`), so the divergence is **latent today**, not live. |
| **Severity** | **MEDIUM** |
| **Close it with** | **CI** (delete the step; the ratchet already judges all 102 tracked Dockerfiles correctly and blocks) |

#### M2 - The ratchet reads the last `USER` in the FILE, not the last `USER` of the FINAL STAGE

| | |
|---|---|
| **Vendor source** | Docker, *Dockerfile reference* -> **`USER`** (same quote: "for the remainder of the **current stage**") |
| **PMOVES today** | `pmoves/tools/hardening_ratchet.py:120` collects every `USER` line in the file and takes `users[-1]`, with no stage awareness. |
| **Delta** | In a multi-stage Dockerfile where a builder stage sets a non-root `USER` and the final stage sets none, the final image runs as **root** while the ratchet scores it COMPLIANT. **Measured: 0 of 102 tracked Dockerfiles are in that shape today.** The property is unenforced; it is not currently violated. |
| **Severity** | **MEDIUM** (latent, but this is a required, merge-blocking check) |
| **Close it with** | **TOOL** |

#### M3 - Nothing checks for `/var/run/docker.sock` mounts

| | |
|---|---|
| **Vendor source** | Docker, *Docker Engine security* -> **"Docker daemon attack surface"** - https://docs.docker.com/engine/security/#docker-daemon-attack-surface |
| **Vendor text** | "only trusted users should be allowed to control your Docker daemon ... you can start a container where the `/host` directory is the `/` directory on your host; and the container can alter your host filesystem without any restriction." |
| **PMOVES today** | Three base services bind-mount the daemon socket: **`supabase-vector`, `agent-zero`, `gpu-orchestrator`**. No tool, script or CI job in the hardening surface mentions `docker.sock`. `docker-bench` checks for `privileged`, `pid=host` and `net=host` - a socket mount is equivalent in blast radius and is checked by none of them. |
| **Delta** | The most root-equivalent container capability in the stack is the one property the hardening surface does not look at. |
| **Severity** | **MEDIUM** (all three are presumably deliberate; the gap is that nothing records or re-checks that judgement) |
| **Close it with** | **TOOL** (add to the ratchet with the existing `deliberate` / `handled-elsewhere` taxonomy, which is the right home for exactly this) |

#### M4 - `docker-bench` measures the GitHub-hosted runner, not any PMOVES host, and cannot fail

| | |
|---|---|
| **Vendor source** | Docker, *Rootless mode* - https://docs.docker.com/engine/security/rootless/ ; *Docker Engine security* -> "Other kernel security features" (userns-remap) - https://docs.docker.com/engine/security/#other-kernel-security-features |
| **PMOVES today** | `.github/workflows/hardening-validation.yml:172-174` - `runs-on: ubuntu-latest`. Every check in it (`:200-257`) reads `docker info` / `docker ps` on **that ephemeral runner**. Its findings are printed with `echo`; the privileged-container, `pid=host` and `net=host` branches emit a warning glyph and do not exit non-zero. `:333` ends the CIS bench step with `\|\| true`. |
| **Delta** | Rootless/userns is reported for a runner PMOVES does not operate, and a real finding on a real host could not surface here anyway. The job answers a question about the wrong subject, and cannot report a bad answer. It is also absent from the `summary` job's `needs` (`:478`), so even the summary does not read it. |
| **Severity** | **MEDIUM** |
| **Close it with** | **CI** (either point it at a fleet host via the existing `docker_host_policy_check.py` road, or delete it - a control that cannot fail and measures the wrong host is worse than none, because it reads as coverage) |

#### M5 - `validate-hardening.sh` validates three **secret names** as if they were services

| | |
|---|---|
| **Vendor source** | Docker, *Compose file reference* -> `secrets` https://docs.docker.com/reference/compose-file/services/#secrets (top-level `secrets:` entries are not services) |
| **PMOVES today** | Its service discovery is `grep '^  [a-z]' \| grep ':$' \| grep -v 'services\|secrets\|networks\|volumes'` (`:25`) - which removes the top-level **keys** but not their children. Measured: it validates **31** subjects; the file declares **28** services. The extra three are `supabase_service_role_key`, `supabase_jwt_secret`, `p7_control_token`, each producing five warnings about a missing `user`, `read_only`, `cap_drop`, `no-new-privileges` and resource limits. |
| **Delta** | 10% of the subjects are not containers. The aggregate line (`112 passed, 43 warnings`) hides it completely - the per-item reading is the only place it is visible. |
| **Severity** | **MEDIUM** |
| **Close it with** | **TOOL** (parse the YAML; the repo already ships `ruamel.yaml` pinned for the compose gates in the same file, `:359`) |

#### M6 - Base images are pinned by tag, not digest, while our own doc says otherwise

| | |
|---|---|
| **Vendor source** | Docker, *Building best practices* -> **"Pin base image versions"** - https://docs.docker.com/build/building/best-practices/#pin-base-image-versions |
| **Vendor text** | "Image tags are mutable ... To fully secure your supply chain integrity, you can pin the image version to a specific digest. By pinning your images to a digest, you're guaranteed to always use the same image version, even if a publisher replaces the tag with a new image." |
| **PMOVES today** | Measured across 102 tracked Dockerfiles: **43** `FROM` refs are digest-pinned, **77** are tag-only. Seven carry no tag or `:latest`, including `.github/runners/Dockerfile` -> `myoung34/github-runner:latest` - the self-hosted **runner** image itself on a mutable tag. `pmoves/docs/operations/DOCKER_DAEMON_HARDENING.md:14-15` already says "Pin production image references by digest where operationally practical". Nothing checks it. |
| **Delta** | Direction 3: the doc describes a protection no tool enforces. The vendor page also notes the tradeoff (digest pinning opts you out of automated patch pickup), so a blanket rule is wrong - but the *runner* image on `:latest` is the case with the least defensible tradeoff. |
| **Severity** | **MEDIUM** |
| **Close it with** | **TOOL** (a ratchet over `FROM` refs, `not-deployed` / `deliberate` kinds already exist) |

#### M7 - Unpinned executables inside a workflow that pins every action by SHA

| | |
|---|---|
| **Vendor source** | GitHub, *Secure use reference* -> **"Using third-party actions" / Pin actions to a full-length commit SHA** - https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions |
| **Vendor text** | "Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release." |
| **PMOVES today** | Every `uses:` in `hardening-validation.yml` is SHA-pinned, and `merge-gate.yml:138-152` runs `action_pin_audit.py` to prove the pins resolve - PMOVES is **ahead** of baseline here. But `hardening-validation.yml:322` runs `docker-bench-security:latest` (mutable tag) and `:324-325` falls back to `curl -fsSL https://github.com/docker/docker-bench-security/releases/latest/download/docker-bench-security.sh -o /tmp/dbs.sh && chmod +x /tmp/dbs.sh && /tmp/dbs.sh` - fetch-and-execute from a `latest` redirect. |
| **Delta** | The immutability property is enforced for `uses:` and abandoned for the two executables the same file downloads and runs. |
| **Severity** | **MEDIUM** |
| **Close it with** | **CI** (moot if M4 closes by deletion) |

#### M8 - CodeQL runs, but no ruleset rule makes its results block a merge

| | |
|---|---|
| **Vendor source** | GitHub, *Available rules for rulesets* -> **"Require code scanning results"** - https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-code-scanning-results ; and **"Require secret scanning alerts are resolved"** (same page) |
| **PMOVES today** | `.github/workflows/codeql.yml` runs on `pull_request`. `pmoves/configs/branch_protection/pmoves_standard.json` `monorepo` profile declares rule types `deletion`, `non_fast_forward`, `required_signatures`, `required_linear_history`, `copilot_code_review`, `required_status_checks`, `pull_request`. **Neither `code_scanning` nor `secret_scanning` is present.** |
| **Delta** | An analysis that produces severity-ranked alerts has no merge consequence attached, and the repo already carries the evidence that this matters: `merge-gate.yml:161-174` exists because ten `lgtm[]` markers claimed suppressions GitHub ignores, four of them on lines with open HIGH alerts. |
| **Severity** | **MEDIUM** |
| **Close it with** | **CI/governance** (add the rule types to the ruleset spec) |

### LOW

| # | Vendor source + section | PMOVES today | Delta | Close with |
|---|---|---|---|---|
| L1 | Docker, *Building best practices* -> "Exclude with .dockerignore" https://docs.docker.com/build/building/best-practices/#exclude-with-dockerignore | **4** tracked `.dockerignore` files across **42** distinct build contexts. `pmoves/.dockerignore` excludes only two jellyfin data dirs and `**/node_modules` - not `.git`, not the generated tier env files that the secrets funnel writes into that exact directory. | Anything in the context can enter a layer. **Measured: 0 of the 27 services built from the `pmoves/` context COPY the whole context today**, so this is unenforced-but-unviolated. `secrets_hardening_audit.py` - the tool that owns secret hygiene - does not look at build contexts at all. | TOOL |
| L2 | GitHub, *Secure use reference* -> "Use an intermediate environment variable" https://docs.github.com/en/actions/reference/security/secure-use#use-an-intermediate-environment-variable | Parsed all 66 workflows: **13** distinct (workflow, job, expression) interpolations of a `github.event.*` context directly into a `run:` block, across **9** workflows. **11 of the 13** are commit SHAs (`pull_request.head.sha` / `base.sha`), a base ref, or a PR number - none attacker-controllable as text. The two that are neither are `fleet-docker-cleanup.yml` -> `github.event.inputs.aggressive` and `verify-attestation.yml` -> `github.event.inputs.image`. No `github.head_ref` in any `run:`. | Largely compliant. The two `workflow_dispatch` inputs require write access to trigger, but the vendor's rule is unconditional. | CI |
| L3 | Docker, *docker container run* -> `--security-opt="no-new-privileges=true"` https://docs.docker.com/reference/cli/docker/container/run/#security-opt | `no-new-privileges` is declared on **4 of 111** base services and on all 28 hardened-overlay services. | Same root cause as H3; recorded separately because `validate-hardening.sh` names it as a checked property and the coverage number is the one nobody reads. | TOOL |
| L4 | GitHub, *Secure use reference* -> "Use secrets for sensitive information" (above) | `pmoves/tools/secrets_hardening_audit.py` is reachable only via `make -C pmoves secrets-audit` (`pmoves/mk/codex.mk:69`). The script path appears in **zero** workflows. | A 456-line secret-hygiene gate that no automated path ever runs. Its own `#9` findings are referenced by another make target's error text (`codex.mk:360`), so it is treated as authoritative while running only when someone remembers. | CI |
| L5 | Docker, *json-file logging driver* https://docs.docker.com/engine/logging/drivers/json-file/ ; *Live restore* https://docs.docker.com/engine/daemon/live-restore/ | `pmoves/docs/operations/DOCKER_DAEMON_HARDENING.md:57` heads the **Live Restore** section with `**CIS Benchmark:** 2.14 - "Ensure containers are restricted from acquiring new privileges"`. | The cited control is `no-new-privileges`, which is a different subject from live-restore. A reader takes the section as the no-new-privileges runbook. (CIS is not a Docker/GitHub source, so the *numbering* is **COULD-NOT-VERIFY**; the subject mismatch is verifiable from the two Docker pages cited and is the actual defect.) | DOC |
| L6 | GitHub, *Available rules for rulesets* -> "Require status checks to pass before merging" https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-status-checks-to-pass-before-merging | `hardening-validation.yml:475-479` - job `summary`, `if: always()`, `needs: [validate-hardening, validate-dockerfiles, validate-compose]`. It writes "Some validations failed" into an artifact and **always exits 0**. | The only aggregating job in the file reports the outcome and never carries it. It also omits `docker-bench` from `needs`. Harmless while nothing is required from this file - load-bearing the moment something is. | CI |
| L7 | Docker, *Building best practices* -> "ADD or COPY" https://docs.docker.com/build/building/best-practices/#add-or-copy | `hardening-validation.yml:165-167` warns on `ADD`. Two tracked Dockerfiles use it: `pmoves/services/a0-elder-melchor/Dockerfile`, `pmoves/services/agent-zero/Dockerfile`. Neither is in the 7-file matrix, so the warning never prints for them. | Minor. The vendor's position is narrower than "COPY is safer" - it is that `ADD`'s remote-fetch and auto-extract behaviours are what you usually do not want. | CI |

---

## Direction 2 - what we implement that the vendor has changed or contradicted

This direction was checked explicitly. **One finding.**

#### D1 - Our doc states a vendor deprecation the vendor has not made

`pmoves/docs/operations/DOCKER_DAEMON_HARDENING.md:8-10` opens with:

> "Docker Content Trust is no longer the primary recommendation for PMOVES images."

and `:38-42` adds a "Legacy Note" calling DCT "still useful historical context,
but ... not the forward-looking control."

**Vendor state, measured 2026-09-20:** https://docs.docker.com/engine/security/#docker-content-trust-signature-verification is live and
documents DCT signature verification as a current `dockerd` feature - "The
Docker Content Trust signature verification feature is built directly into the
`dockerd` binary." https://docs.docker.com/engine/security/trust/ returns 200 and carries no deprecation
notice.

**The delta is one of voice, and it is the kind that rots.** PMOVES' preference
for digest pinning + cosign over DCT is a defensible local decision, and the
rest of that section (Sigstore, digests, hardened bases) is well-anchored. But
the sentence is written as though it reports the vendor's position. A future
reader diffing our doc against the vendor will find the vendor still shipping
DCT and conclude our doc is stale - when in fact it is a policy they should
either keep deliberately or revisit. **Close with DOC**: say "PMOVES prefers X
over DCT, because Y", not "DCT is no longer the recommendation".

Everything else in the hardening surface was checked against current vendor
pages and **no other deprecation or contradiction was found**. In particular:
`cap_drop`, `read_only`, `security_opt`, `pids_limit`, `privileged` and `user`
are all current keys in the Compose file reference; SHA-pinning of actions is
still GitHub's stated position, not a superseded one; and rootless mode is
current, not replaced.

---

## Vendor areas with NO corresponding PMOVES check

An empty section is a finding. These are vendor-documented controls for which
this repository's hardening surface contains **nothing** - no tool, no CI step,
no assertion. Listed because their absence is invisible from the config.

| Vendor area | Vendor source | State here |
|---|---|---|
| **Build secrets** (`RUN --mount=type=secret`) | https://docs.docker.com/build/building/secrets/ | **Zero** tracked Dockerfiles use secret mounts. Nothing checks whether a credential enters a build via `ARG`/`ENV` instead. Two Dockerfiles declare secret-named `ENV`/`ARG` with empty defaults (`pmoves/services/notebooklm-agent/Dockerfile:24-25`, `pmoves/ui/Dockerfile:22`) - empty is fine; the point is that nothing would notice if they were not. |
| **seccomp profiles** | https://docs.docker.com/engine/security/seccomp/ | No check, no doctrine. `security_opt` is only ever used for `no-new-privileges`; `seccomp=` appears nowhere. |
| **AppArmor / SELinux** | https://docs.docker.com/engine/security/apparmor/ | No check, no doctrine, no mention in either hardening doc. |
| **userns-remap** | https://docs.docker.com/engine/security/userns-remap/ | Detected-and-reported-only on the CI runner (M4). No fleet-host check, no `daemon.json` entry in `deploy/provision/daemon.json`. |
| **Rootless mode** | https://docs.docker.com/engine/security/rootless/ | Same - reported for the wrong host, asserted nowhere. Neither hardening doc takes a position on whether fleet nodes should run rootless. |
| **Daemon socket protection (TLS / SSH)** | https://docs.docker.com/engine/security/protect-access/ | Not covered by either doc. Three services mount the socket directly (M3); nothing addresses remote daemon exposure. |
| **`pids_limit`** | https://docs.docker.com/reference/compose-file/services/#pids_limit | Declared on 0 services. Not mentioned in any hardening doc or check. Fork-bomb containment has no owner. |
| **OIDC for deployment credentials** | https://docs.github.com/en/actions/concepts/security/openid-connect | `integrations-ghcr.yml` requests `id-token: write` for attestations, which is the right shape. But the deploy workflows (`deploy-gateway-agent.yml`, `self-hosted-builds-hardened.yml`) authenticate to hosts by other means; no workflow uses OIDC for a cloud/registry credential exchange, and nothing in the docs recommends it. Not necessarily wrong - just unexamined. |
| **Artifact attestations** | https://docs.github.com/en/actions/concepts/security/artifact-attestations | `integrations-ghcr.yml` holds `attestations: write` and the docs cite cosign. Whether attestations are *generated and verified* was **not measured in this lane** (it is the GHCR publish lane's surface, outside this claim). Flagged so the next lane does not assume it was checked. |

---

## Where PMOVES is ahead of the vendor baseline

Recorded so the negatives above are readable as findings and not as a verdict on
the whole surface.

- **Every `uses:` is SHA-pinned**, and `action_pin_audit.py` (`merge-gate.yml:138-152`) proves the pins resolve - closing a failure mode (`startup_failure` from a dead pin) that GitHub's own guidance does not mention.
- **Required status checks are pinned to `integration_id: 15368`.** The vendor explicitly flags the alternative as a hole: "Any person or integration with write permissions to a repository can set the state of any status check" (*Available rules for rulesets* -> Require status checks to pass before merging). PMOVES already closed it.
- **`merge-decision` requires `success`, not merely not-`failure`** (`merge-gate.yml:298-318`), so `cancelled` and `skipped` fail the gate. This is the fail-open shape most repos ship.
- **`step-security/harden-runner` with `egress-policy: audit`** on all four validation jobs in `hardening-validation.yml` - egress observability GitHub does not provide by default.
- **The ratchet baseline's `debt` / `handled-elsewhere` / `deliberate` / `not-deployed` taxonomy** (`hardening_ratchet.py:176-192`) and its enforced `reason` allowance solve a problem the vendor has no vocabulary for: making a suppression list unable to rot into an allowlist.

---

## COULD-NOT-VERIFY

Stated rather than guessed. Each of these would change a recommendation above if
resolved the other way.

1. **"Require workflows to pass before merging" availability.** This ruleset rule
   (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-workflows-to-pass-before-merging)
   pins a workflow **file in a source repository**, which is immune to the
   job-name collision documented at the top of this audit. It is the correct fix
   for that class. **But** the vendor text says "in your **organization**
   settings, you specify the source repository and the workflow", and
   `POWERFULMOVES` is a user account, not an organization. Whether the rule is
   available to a user-owned repository is not stated on that page and was not
   probed. **Do not adopt it as the fix until availability is confirmed.**
2. **CIS Docker Benchmark control numbering.** `DOCKER_DAEMON_HARDENING.md`
   cites CIS 2.14 (L5). CIS is not a Docker or GitHub source and the benchmark
   is not freely retrievable; the number could not be checked. Only the subject
   mismatch is asserted.
3. **Whether the `bypass_actors` entry is intended.** `pmoves_standard.json`
   grants `RepositoryRole` actor_id 5 `bypass_mode: always`, which by name is
   Admin. GitHub's ruleset docs describe bypass semantics but the numeric role
   IDs are not documented on the pages read. The *effect* - the merge-blocking
   hardening check is bypassable - follows either way, and the `description`
   field does not record why.
4. **Live daemon posture on any fleet node.** No container was run and no fleet
   host was probed, per the lane's boundaries. Every daemon-level statement here
   is about what the repo asserts, never about what a node is currently doing.
   `docker_host_policy_check.py` exists for that and was not invoked.
5. **Artifact attestation generation/verification** in the GHCR lane - see the
   table above. Out of this claim's scope; not measured; not assumed.

---

## What this lane did not do

Per the claim's boundaries: no workflow, Dockerfile, compose file,
`hardening_ratchet.py` or ratchet baseline was modified. `docker-bench` was not
run and no container was started against a live PMOVES service. No Known Road
grant was minted, rotated or extended; no denial was hit.

Remediation is a separate lane, routed from the ranking above. The natural split:
**H1 + H4 + M1 + M7** are CI edits in two files; **H2 + H3 + M2 + M3 + M5 + M6**
all want the same ratchet shape that already exists; **D1 + L5** are two
paragraphs in one doc.
