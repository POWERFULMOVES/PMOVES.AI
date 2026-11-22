# silent_bind_ratchet_LEARNINGS.md

**Lane:** silent-bind ratchet — the static twin of `make -C pmoves net-reality`, plus the smoke-suite wiring that makes a refused HTTP connection distinguishable from a refused *published* port
**Author:** Mavis (mvs_ce8c1e6e34434db1ba42d3b822ecbd15) · **Operator:** DARKXSIDE
**Active:** 2026-11-22 · **Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (branch `fix/silent-bind-declared-host-ports-2026-11-22`)
**Branch:** `fix/silent-bind-declared-host-ports-2026-11-22`

---

## Operator direction (verbatim)

> "hhmm sounds like handrolled without loading the dice first lets get doc provenance on to ensure tools scripts work"

> "I also meant check the tools themselves against the relevant latest source docs"

Those two sentences are the load-bearing inputs to this slice, and they are
the reason the lane's first commit is **instruments, not remediation**. The
operator did not ask for another gate; they asked for the tools to be
*right* — sourced from the house's own instruments and checked against the
upstream source docs — before anything was changed in production compose.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **pattern-conformance** | **The house already owns the instrument.** A hand-rolled compose transform was written first and then deleted in the same session: it edited the generated split overlays by hand and wrote `PMOVES_NETWORKS=` by hand. Both are owned by the house — `scripts/split_compose.py` GENERATES the overlays and the Makefile says "Never hand-edit them (damage-control blocks it)"; `scripts/inject_pmoves_networks.py` MIRRORS each service's `networks:` into `PMOVES_NETWORKS=` and is drift-gated by `make -C pmoves compose-networks-check`. The hand-rolled transform would have been undone by both. | `pmoves/Makefile:6001-6035` (`compose-split` / `compose-split-check` / `compose-networks` / `compose-networks-check`); `pmoves/scripts/inject_pmoves_networks.py` docstring ("The SOURCE file is mutated … both must agree"); `pmoves/scripts/split_compose.py`. The flow that is correct is: edit `networks:` in `pmoves/docker-compose.yml` → `make -C pmoves compose-networks` → commit the regenerated overlays. | Any change to a compose file's `networks:` or `ports:` block in this repo. |
| 2 | **reasoning-gap** | **A "first declaration wins" network map silently degrades to UNKNOWN.** Ten files in the house scope re-declare `pmoves_api` / `pmoves_app` / `pmoves_bus` WITHOUT an `internal:` key, and `pmoves_app`/`pmoves_bus` are declared with a YAML **anchor** (`<<: *network-internal-only`). A global map built by "first file that mentions it wins" therefore resolved `pmoves_app` to UNKNOWN instead of `internal: true`, and the gate went blind to the split overlays. The resolution order must be explicit: the file's own `external: true` → UNKNOWN; the file's own `internal:` → that value; otherwise INHERIT from the canonical declarations in `docker-compose.yml` + `docker-compose.base.yml`; otherwise UNKNOWN. | Measured in this lane: the first-wins map reported `pmoves_app: internal=None` while the canonical file says `internal: true`, and 10 conflicting-flag messages fired across `docker-compose.jellyfin-ai.yml`, `.mcp-gateway.yml`, `.open-notebook.yml`, `.remote.yml`, `.rocm.override.yml`, `.sso.yml`, `.vps.override.yml`. With the canonical-inheritance rule the count is 73 (file, service) pairs across 39 services, and the tool and an INDEPENDENT measurement script agree on that number. | Any tool that resolves a named resource's property across a set of files that redeclare it. |
| 3 | **defense-in-depth** | **`all()` over an EMPTY set is True.** A service with no `networks:` key joins the file's DEFAULT network — a normal bridge — so its published port DOES bind. Scoring the empty set as "every network is internal" reports dozens of phantom gaps. The empty case is only a gap when the file declares its `default:` network with `internal: true`. | `pmoves/tools/silent_bind_ratchet.py::scan_file` (the `default_internal` guard) + mutation **M3** in `pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py`, which removes the guard and MUST kill `test_service_without_networks_key_is_not_a_gap`. The vacuous-truth bug was found by MEASUREMENT, not by reading: the first measurement pass reported `activepieces-app` and `nginx` as gaps with an EMPTY network set. | Any tool that asks "are all of these X?" where the list may be empty. |
| 4 | **reasoning-gap** | **Detection must compare the REQUESTED binding to the ACTIVATED map PER KEY.** A text search for `"HostPort": null` catches only one of the two shapes Docker emits: `Ports["8084/tcp"] == null` (the whole entry null) and `Ports["8084/tcp"][0].HostPort == null` (the slot null). The grep misses the first entirely. This is the same class of measurement error the house's own `audit_network_reality.sh` had. | moby/moby#36174's own `docker container inspect` output — `HostConfig.PortBindings` holds the REQUESTED binding while `NetworkSettings.Ports` is `{}` — which is the authoritative shape for the comparison. Measured on the b850 runner: a text-grep detector reported 0 silent binds where a per-key JSON detector reported 15 containers / 16 ports. | Any Docker port-binding audit. |
| 5 | **contract-correctness** | **Upstream provenance AND house provenance are both required, and they say different things.** The upstream tracker (moby/moby#36174, OPEN) carries the mechanism and the maintainer's position — "As far as I'm aware, this is by design, and `--internal` networks should not be reachable, even with `-p` being used". The house doc carries the TIER and the remedy — `pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md` Rule 5, "There is no 'publish without egress.' Front it with a gateway", and the network table naming `pmoves_public` as the "Host-reachable + egress-capable" bridge. Citing only the tracker leaves the operator with a defect and no remedy; citing only the house doc leaves the claim unverifiable upstream. | `pmoves/tools/silent_bind_ratchet.py` docstring cites both, plus compose-spec `13-merge.md` for the merge semantics (mappings merge, so a service's network set across files is the UNION) and the sibling ratchet's "as deployed" model. | Any claim that a runtime platform behaves in a specific way. |
| 6 | **pattern-conformance** | **The house's own precedent on this class is to fix the AUDITORS first.** PMOVES's history on silent binds is three commits that repaired the DETECTION, not the compose files: `6baaaa1` and `fec0a97` ("the auditor that exists to catch silent binds was reporting…"), `de27bdb` ("three silent binds were passing as 'expected if you haven't run make up'"). The compose remediation was a separate decision. So the lane's first PR lands the instruments + the baseline that records the gaps; the remediation PR retires them and the baseline shrinks. | `git log` on the POWERFULMOVES/PMOVES.AI commits that reference moby/moby#36174 (visible on the upstream issue page itself). | When a lane's remediation changes production posture and the instruments are missing. |
| 7 | **contract-correctness** | **A baseline entry whose reason is a placeholder is not a decision.** The ratchet's generator writes `"REVIEW THIS"` for every measured gap; a baseline of placeholders reads exactly like a baseline of reviewed decisions. The gate therefore fails a recorded gap whose reason is empty or is still the placeholder, and the baseline may only SHRINK — a gap that was fixed but left listed fails as `STALE_GAP`. | `pmoves/tools/silent_bind_ratchet.py::run_check` (`STALE_GAP` + the placeholder rule) + mutations **M5** and **M6**; the house's own precedent is `pmoves/configs/hardening_ratchet/_compose_known_gaps.yaml` ("They are NOT approved, and none of them is 'expected'"). | Any recorded-exceptions list. |
| 8 | **defense-in-depth** | **A gate that cannot read its input must FAIL CLOSED, and "could not measure" must be its own exit code.** Three files in the house scope carry Compose's `!reset` / `!override` tags, which PyYAML rejects outright; and an unreadable compose file must be an `INSTRUMENT_ERROR`, not a skip. The house convention is exit 3 = COULD NOT MEASURE, which is NOT a pass — `make` collapses 1 and 3 to 2, so the tool is called directly when the distinction matters. | `pmoves/tools/silent_bind_ratchet.py::ComposeLoader` (`!reset` / `!override` constructors) + exit code 3 + mutation **M7**; the sibling `pmoves/tools/compose_hardening_ratchet.py` and the Makefile's note "(exit 1 = new/stale finding, exit 3 = COULD NOT MEASURE … call the tool directly when the distinction matters)". | Any gate that parses files it does not control. |
| 9 | **reasoning-gap** | **A URL port parser must not split on the colon INSIDE a substitution.** The smoke suite's URLs carry `"${VAR:-default}"`, and `##*:` cuts at the LAST colon — which is the one inside the substitution — yielding `":-default}"` instead of the port. The parser therefore matches the three authority shapes explicitly (host + substitution / bare substitution / host + digits) instead of splitting. The bug was found by the test, not by reading the code. | `pmoves/scripts/smoke-tests.sh::_http_port` + `pmoves/tools/tests/test_smoke_http_port_parser.py`, which EXTRACTS the function from the house script rather than copying it, so the test cannot drift from the code. 12/12 cases pass, including `${VAR:-default}` with and without the variable set. | Any parser that consumes compose-style substitutions. |
| 10 | **defense-in-depth** | **A gate that cannot detect is indistinguishable from a clean tree.** Every rule the ratchet depends on is pinned by a mutation that must kill a NAMED test, with the three-phase GREEN→RED→GREEN contract and a byte-exact restore in a `finally`. The kill signal is the test NAME in pytest's own short summary — not "pytest exited non-zero", which a collection error or a timeout also satisfies. | `pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py` — 7 mutations, 8/8 pass, measured 38.45s; the crash-safe backup is `pmoves/tests/mutation_backup.py`, and the file is declared slow with its measured basis in `pmoves/configs/pytest_ratchet/_slow_files.yaml`. | Every new ratchet in this repo. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 3 lessons (#2, #4, #9) — the first-wins network map, the per-key requested-vs-activated comparison, and the colon inside a substitution.
- **(2) semantic-naming drift** — 0 lessons.
- **(3) contract-correctness** — 2 lessons (#5, #7) — upstream AND house provenance together, and a recorded exception is not a decision.
- **(4) defense-in-depth** — 3 lessons (#3, #8, #10) — the vacuous-truth empty set, fail-closed on unreadable input, and the mutation-kill net.
- **(5) pattern-conformance** — 2 lessons (#1, #6) — the house already owns the instrument, and the house's precedent is to fix the auditors first.

Pattern: **the lane's centre of gravity is conformance to instruments that already
existed.** Two of the ten lessons are the same lesson seen from opposite ends
(#1 and #6: find the house's instrument, and let the house's precedent set the
order of work), and the two that changed the CODE most (#2 canonical
inheritance, #3 the empty-set guard) were both found by MEASUREMENT rather
than by reading the source — which is the point the operator made about
"loading the dice first".

---

## What is measured, and where

| Instrument | Measures | Scope |
|---|---|---|
| `pmoves/tools/silent_bind_ratchet.py` | STATIC: can a published host port activate? (compose files only — no daemon, so it runs on every PR) | 63 compose files in the house scope; 25 out of scope, printed on every run; 73 (file, service) pairs across 39 services |
| `make -C pmoves net-reality` (`pmoves/scripts/audit_network_reality.sh`) | RUNTIME: what did each container REQUEST vs what the daemon ACTIVATED | needs a running daemon; cannot run on a GitHub-hosted runner |
| `pmoves/scripts/smoke-tests.sh::_silent_bind_owner` | RUNTIME: the same class, from the smoke suite's own probes | was wired into `test_tcp_connectivity()` only; `test_http_endpoint()` collapsed a refusal into a WARNING — a gate that cannot see the class it owns |

The three are one subject seen from three vantage points. The static one is
new; the other two were already in the house, and one of them was already
half-wired.

---

## Reproducing the numbers in this file

```
python pmoves/tools/silent_bind_ratchet.py --check          # the gate
python pmoves/tools/silent_bind_ratchet.py --check --json   # the same, machine-readable
python -m pytest pmoves/tools/tests/test_silent_bind_ratchet.py -v
python -m pytest pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py -v
python -m pytest pmoves/tools/tests/test_smoke_http_port_parser.py -v
```

Run the mutation-kill harness ALONE: a mutation harness holds the tree
MUTATED by design (house lesson 34), so nothing may read or write the tree
while one runs.

---

## Regenerate the baseline

```
python pmoves/tools/silent_bind_ratchet.py --write-baseline --yes
```

Every reason the generator writes is a PLACEHOLDER (`REVIEW THIS`). The
generator cannot write a reason because a reason is a decision, and a
decision is the operator's. The committed baseline's reasons are written by
hand and state what each gap is waiting on.
