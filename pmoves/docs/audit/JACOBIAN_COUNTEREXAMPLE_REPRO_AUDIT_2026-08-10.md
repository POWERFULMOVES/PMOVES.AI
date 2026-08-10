# Reproducibility audit — `Pmoves-3bmalpoge-fable-jacobian-counterexample`

**Date:** 2026-08-10
**Auditor:** CLAUDE-OPUS-5 (4090 node)
**Subject:** [`POWERFULMOVES/Pmoves-3bmalpoge-fable-jacobian-counterexample`](https://github.com/POWERFULMOVES/Pmoves-3bmalpoge-fable-jacobian-counterexample) @ `645eb48b0adbede1545c5e8818a6629fd47595b4`
**Upstream:** `MMVFIRM/alpoge-fable-jacobian-counterexample` — same SHA, **zero fork divergence**
**Access:** read-only. Clones and API reads only; nothing pushed to the fork, no issues opened upstream.

---

## What this audit does and does not establish

**Read this before anything else in this document.**

This audit establishes **reproducibility**: that the six checks execute, that they exit 0, that they are deterministic, and that the files present hash to the values the authors published.

This audit says **nothing whatsoever about whether the counterexample is mathematically correct.**

The Jacobian Conjecture is a famous open problem. A counterexample in dimension 3 would be a significant result, and settling it is expert mathematical review — peer review by algebraic geometers — not a CI run. Nothing below should be read as evidence for or against the claim. A package can be perfectly reproducible and mathematically wrong: `assert d == -2` passing proves SymPy expanded a determinant to `-2`, not that the surrounding argument establishes what the paper says it establishes.

**On the hashes specifically.** The three manifests are **unkeyed SHA-256**. They prove you are holding the same bytes the author published *if* you obtained the manifest through a trusted path. They are not signatures. They carry no author identity, and anyone who can modify a file can recompute its digest and modify the manifest in the same commit. What they give you is **tamper-evidence against accidental drift and against modification-in-transit relative to a manifest you trust** — not authenticity, and not proof the author endorsed these bytes.

This distinction is stated up front deliberately: it is the same overstatement Codex caught on #2518 regarding `content_hash`. A content hash names *which bytes*; only a signature names *whose*.

---

## Question 1 — Does it reproduce?

### Summary

| Step | Result |
|---|---|
| `sha256sum -c MANIFEST.sha256` | **FAIL** — exit 1, 34/35 OK, `./README.md` mismatched |
| `sha256sum -c frozen/referee_package-2026-07-20.sha256` | **PASS** — exit 0 |
| `sha256sum -c REPOSITORY_MANIFEST.sha256` | **FAIL** — exit 1, 51/52 OK, `./README.md` mismatched |
| `scripts/run_all_checks.py` (six checks) | **PASS** — exit 0, all six, ~10–18 s |

So: **the checks reproduce; the integrity manifests do not.** The failure is a single stale entry, and it is not in a check.

### The manifest failure is real, is upstream's, and is three weeks old

`README.md` was edited in commit `e33ba19 "Update README.md"` *after* `MANIFEST.sha256` and `REPOSITORY_MANIFEST.sha256` were generated in `04d0115`, and neither manifest was regenerated.

```
manifest says: 4811f93d0c30f5e2b16b2238d1ed0af1570f3231ef28d4fdef65e9da68d44a7b  ./README.md
actual:        b118818823a7ab48c4897801492e815fe04a7a708083edd62cfe7f6047d66d8b  ./README.md
```

This is not a fork artifact — fork HEAD and upstream HEAD are the same commit. The authors' own CI corroborates it exactly:

| upstream run | commit | conclusion |
|---|---|---|
| `29765617720` | `04aa29c3` (before the README edit) | **success** |
| `29765792559` | `e33ba199` ("Update README.md") | **failure** |
| `30308296638` | `645eb48b` (HEAD) | **failure** |

The failing step is #5, `Verify original frozen files`. Because it fails, steps 6 and 7 are **skipped** — which means:

> **Upstream CI has not executed the six checks since 2026-07-20.** The six checks have been unexercised in the authors' own pipeline for three weeks, masked by a stale hash of a README.

That is the most consequential finding here, and it is a process finding, not a mathematical one. The run recorded in this document may be the most recent successful execution of the six checks anywhere.

**Severity: low for correctness, high for the "frozen verification package" claim.** A package whose selling point is that it is frozen and hash-verified currently fails its own hash verification on `git clone` + its own integrity targets. A referee following `REPRODUCIBILITY.md` hits a red gate before running any mathematics.

### The six checks

All six pass, deterministically. Verbatim, from the offline containerised run:

```
=== checks/check_1_determinant.py ===
det J_F = -2
PASS: det J_F = -2 identically (F is a Keller map).

=== checks/check_2_collision.py ===
PASS: three distinct points map to (-1/4, 0, 0); F is not injective.

=== checks/check_3_degree.py ===
PASS (a): M(x; F(x,y,z)) == 0 identically.
PASS (b): M irreducible over C(A,B,C); degree of x over the base is 3.
PASS (c): generic degree = 3 (= field-extension degree, char 0).

=== checks/check_4_jelonek_surface.py ===
PASS (a): Res_v = 3*St.
PASS (b): S_F rationally parametrized (uniruled).
PASS (c): 27C^2*St|_{B=4/(3C)} = (27AC^2-4)^2.
PASS (d): St|_{A=0} = B^2(BC-1).
PASS (e): the collision point is off S_F (its fiber is a generic one).

=== checks/check_5_stratification.py ===
PASS (a): (I_Gamma : C^infty) = (1) -- fibers over Gamma are empty.
PASS (b): explicit section verifies on all of the chart minus Gamma.
PASS (c): fiber over (1,4,0) is exactly {(0,4,-63)}.
PASS: stratification 3 / 1 / 0 on C^3\S_F, S_F\Gamma, Gamma certified.

=== checks/check_6_galois.py ===
PASS (a): Res_U(P1,P2) = A * x^3 * M.
PASS (b): disc_x(M) = -4 H^2 St, not a square: Galois group = S_3.
PASS (c): H ∩ S_F = Gamma; disc order 1 across S_F: meridian = transposition.
PASS (d): 3 distinct preimages at an H-point, two sharing x: no branching off S_F.

Completed 6 checks in 10.27s.
ALL FROZEN CHECKS PASSED
```

Exit code **0**.

### Determinism

Three consecutive runs produced **byte-identical stdout**, the only variation being the wall-clock line the runner prints (`Completed 6 checks in 18.38s / 23.00s / 17.87s`).

Static support for that result: the six checks import **`sympy` and nothing else**. No `random`, no `time`, no `datetime`, no `os.environ`, no file I/O, no `subprocess`, no network. Everything is exact symbolic arithmetic — no floating point, so no platform FPU variance.

`random` and `time` *do* appear in the repo, but only in `legacy/` and in `scripts/ledger.py` / `scripts/run_bench2.py`, none of which `run_all_checks.py` invokes. Where seeded, they are seeded to 42.

### Network access

**None during verification.** Proven, not inferred: the full run succeeds under `docker run --network none`.

Network is required exactly twice, both before verification: pulling the base image, and `pip install -r requirements.txt`.

### Dependency pinning

`requirements.txt` pins one line — `sympy==1.14.0`. **The transitive dependency `mpmath` is not pinned.** A clean install today resolves:

```
mpmath==1.3.0
sympy==1.14.0
```

SymPy carries `mpmath>=1.1.0,<1.4`, so a future `mpmath` 1.3.x release enters a rerun silently. For exact symbolic work over ℚ this is very unlikely to change a verdict — mpmath is arbitrary-precision *floating point*, and these checks never leave exact arithmetic — but "unlikely to matter" is not the same as pinned, and a package sold as frozen should pin its whole closure. There is no hash-pinned lockfile (no `requirements.lock`, no `--require-hashes`), so the dependency install is the one step of this pipeline with no integrity check at all.

### Two portability defects found

**1. Windows console encoding — verification fails on Windows.**

`check_6_galois.py:39` prints `∩` (U+2229). On a Windows console defaulting to cp1252 this raises `UnicodeEncodeError` **after** the check's assertions have already passed, so the runner reports a failure that is not one:

```
PASS (a): Res_U(P1,P2) = A * x^3 * M.
PASS (b): disc_x(M) = -4 H^2 St, not a square: Galois group = S_3.
UnicodeEncodeError: 'charmap' codec can't encode character '∩' ...
FAILED:
  - checks\check_6_galois.py
```

Exit 1. Setting `PYTHONIOENCODING=utf-8` makes the identical run exit 0. Linux is unaffected (UTF-8 default), which is why upstream CI — Ubuntu-only — would never have seen it.

**2. No `.gitattributes`, so Windows checkouts fail integrity spuriously.**

With git's default `core.autocrlf=true` on Windows, every text file is converted to CRLF at checkout, which changes its SHA-256. The manifests then fail on *every* text entry rather than the one real mismatch — 35/35 and 52/52 failures instead of 1. My first clone showed exactly this; a second clone with `core.autocrlf=false` isolated the single genuine failure.

The repo ships no `.gitattributes`. A one-line `* -text` (or `*.sha256 -text` plus the hashed text types) would make integrity checkable on Windows.

Neither defect affects the mathematics. Both affect whether a reviewer on a Windows box concludes the package is broken.

### Environment used

| | |
|---|---|
| Host | 4090 node, Windows 11, Docker 29.6.2 |
| Primary run | `python:3.13-slim` container, linux/amd64, `--network none` |
| Secondary run | Windows host, CPython 3.13.2, isolated venv |
| Dependency | `sympy==1.14.0`, `mpmath==1.3.0` |
| Wall time | 10.27 s (container) / 17.9–23.0 s (Windows host) |
| Peak memory | runs to completion under `--memory=256m` |
| GPU | none required |

Reference environment per `REPRODUCIBILITY.md` is Python 3.11 + Linux; I ran 3.13, which upstream CI also covers in its matrix.

### Verified artifact identities

Recorded so a later reader can tell whether they hold the same bytes this audit examined:

```
repo HEAD                              645eb48b0adbede1545c5e8818a6629fd47595b4
frozen/referee_package-2026-07-20.zip  9797f8b77ee6b862bef6cf4f62fc36d1e8159add056f660813ee99b9c61ddc53
checks/check_1_determinant.py          bf7cf3ea2aa9aef614f041506a3cef6315bcfb8584fc42855dd8942e5713be33
checks/check_2_collision.py            4f555b8edaae7c673c4f6b8570fa54a1709d507af32f949ec7c266d4ed91e1a5
checks/check_3_degree.py               5db93ce0a4ec74f71c8694f189db70cf75513d0a704d8df31b36d21040488bd8
checks/check_4_jelonek_surface.py      002b3d09bbbf5f80c59b7d1b45e0e13d65f96a1100a2cf751551c52017e5ab64
checks/check_5_stratification.py       24f467fae195f48cff8ba5a73af6d73c206fbd8a41de188579ea22ad65dbf747
checks/check_6_galois.py               51f0c3ae83f0108492e52ad901f4e71c2fd29a361c4aaa90d7c6d210f654c69c
```

The six checks inside `referee_package-2026-07-20.zip` are **byte-identical** to the six in the working tree — the archive and the repo have not drifted from each other. Only `README.md`, which is not a check, has.

License: MIT (`LICENSE`). `LICENSE_NOTICE.md` explains the repo previously carried only a notice and read as NOASSERTION. Clean for PMOVES use.

---

## Question 2 — Is it a good Danger Room fixture?

Assessed against `pmoves/docs/handoffs/SKILL_DANGER_ROOM_VERIFICATION_SPARK_2026-08-08.md`.

### Against the artifact contract (§4)

| Criterion | Verdict | Evidence |
|---|---|---|
| **deterministic** | **yes** | three runs, byte-identical stdout; sympy-only imports; no RNG, clock, env, or I/O |
| **bounded wall time** | **yes** | 10.27 s containerised. Fits a `budget.wall_s: 120` with 10× headroom |
| **offline** | **yes** | full run under `--network none` |
| **no GPU** | **yes** | pure CPU symbolic algebra; completes under `--memory=256m` |
| **self-describing / content-hashed** | **partly** | 92 hashed artifacts across three manifests — unusually good. But unkeyed |
| **signed** | **no** | SHA-256 manifests are not signatures. Would need a CHIT wrapper |
| **addressable** | **yes** | public repo + a single 743 KB self-contained archive |

### The content-hashing is the genuinely unusual part

Most candidate fixtures give a pass/fail. This one lets a `skill.verified.v1` receipt name **which bytes** were verified:

```
skill.verified.v1
  fixture:     jacobian-counterexample@645eb48b
  artifacts:   [ check_1..check_6 sha256, referee_package.zip sha256 ]
  verdict:     pass
  wall_s:      10.27
```

A downstream 1B model reading that receipt can tell whether the fixture it is trusting is the fixture that was run. That is exactly the T3 property the handoff describes, available here without building anything.

The honest caveat, which must travel with any such receipt: those hashes say *which bytes*, and the CHIT signature would say *which node vouched* — **neither says the mathematics is right**, and a receipt that reads `jacobian-counterexample: pass` will be misread as saying so unless the fixture id or the receipt schema carries the scope explicitly. Recommend `fixture: jacobian-counterexample-repro` — the word `repro` doing load-bearing work.

### Where it fails the spec, and it is the criterion that matters most

Handoff §3: *"A fixture is a planted failure, not a happy path... A fixture that plants nothing verifies nothing."* Acceptance criterion (5), the one the author says he would cut last: *"A deliberately broken skill fails."*

**As shipped, this package is pure happy path.** All six checks assert and pass. It plants nothing. Used as-is it would verify that the harness can run Python and report success — the exact "harness that only ever passes" the spec warns about.

**But it is trivially convertible, and I tested that rather than asserting it.** Perturbing one coefficient in check 1's map — `F3`'s leading `2*x` → `3*x` — makes the check fail loudly and correctly:

```
det J_F = 3*x**6*y**4*z + 9*x**5*y**5 + ... - 3*x*y - 3
AssertionError: FAIL: determinant is not the constant -2
exit 1
```

The same mutation is caught independently by the content hashes:

```
./checks/check_1_determinant.py: FAILED
sha256sum: WARNING: 2 computed checksums did NOT match
```

So the package supports **two independent negative controls** — a semantic one (the assertion fires) and a structural one (the manifest notices the file changed). Few fixtures offer either; almost none offer both.

### Recommendation

**Adopt as a Danger Room fixture, with a planted-mutant variant, scoped and named as reproducibility-only.**

Concretely:

1. **`jacobian-counterexample-repro`** — clean tree, expect exit 0 and the seven artifact hashes above. Verifies the harness can execute and content-address a real workload.
2. **`jacobian-counterexample-mutant`** — the one-coefficient perturbation, **expect exit 1** and expect the manifest to report the tampered file. This is the acceptance-(5) half; without it the pair verifies nothing.
3. Pin the fixture to `645eb48b` rather than tracking upstream `main`, so an upstream edit cannot silently change a fixture's verdict. Note that if the fixture ever runs those integrity targets, it must expect the **known README failure** at this SHA, or record the fix if upstream regenerates the manifests.
4. Set `PYTHONIOENCODING=utf-8`, or run it in a Linux sandbox, so defect #1 above does not read as a fixture failure.
5. `nodes: [any]` — this needs no GPU and would be wasted as a SPARK-only fixture. It is a good **CPU-floor** fixture precisely because it is heavy enough to be real (~10 s of Gröbner bases and resultants) and light enough to run anywhere.

**Do not** use it as an *inference* fixture. It exercises no model, no TensorZero route, no NATS path. Its value is as a deterministic, content-addressed, offline workload for proving the harness itself — not for proving anything about a skill that reasons.

---

## Findings, collected

| # | Finding | Severity | Owner |
|---|---|---|---|
| 1 | the repo's integrity targets fail at HEAD — `README.md` edited after the manifests were generated | **high** for the "frozen package" claim; none for correctness | upstream |
| 2 | Upstream CI red since 2026-07-20; the six checks **skipped** for three weeks behind finding 1 | **high** | upstream |
| 3 | `mpmath` transitively unpinned; no hash-pinned lockfile | medium | upstream |
| 4 | `check_6_galois.py` prints U+2229 → verification fails on Windows consoles | medium | upstream |
| 5 | No `.gitattributes`; Windows checkouts fail integrity on every text file | medium | upstream |
| 6 | Manifests are unkeyed hashes and are described in `REPRODUCIBILITY.md` under "Integrity" without that qualification | low | upstream / us, when citing them |

Findings 1–5 are upstream's and were **not** reported there, per the read-only boundary on this task. If we want them fixed, opening them upstream is a separate decision for the operator; findings 1 and 2 are the ones worth telling the authors about, since their own pipeline has been silently not running their own checks.

## Method

Two clones (one default, one `core.autocrlf=false` after the first showed CRLF-induced false failures), isolated venv on the host, and a `python:3.13-slim` container for the offline and resource-bounded runs. Upstream comparison and CI history read through the GitHub API. Nothing was pushed; no issues were opened. The mutation test was performed on a local copy only.

The exit codes, hashes, and check output quoted above are verbatim from those runs.
