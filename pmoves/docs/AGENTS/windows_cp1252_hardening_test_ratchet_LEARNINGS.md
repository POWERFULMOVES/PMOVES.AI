# Windows cp1252 hardening test ratchet — LEARNINGS

**PR**: #3358 (Mavis follow-up commit, fold into the next push per operator approval 2026-10-15)
**Branch**: `fix/media-audio-gpu-runtime`
**Test contract**: `pmoves/tests/hardening/test_docker_hardening.py` 14 fail / 239 pass / 49 skip → 16 media-* tests now PASS (was 32/34 ERROR before)
**Source of truth**: `pmoves/tests/hardening/test_docker_hardening.py:120` (the fix) + lines 947-1014 (the ratchet class)

## The defect

`pmoves/tests/hardening/test_docker_hardening.py` has a session-scoped fixture `compose_data` that reads every tracked compose YAML with `open(path, "r")`. On a Linux host the default platform encoding is UTF-8 and the reads succeed. On a Windows host the default is cp1252, which cannot decode:

- `⚠` U+26A0 in the `# ⚠ INTERIM: ...` header comments
- `✅` U+2705 in completion-marker comments
- The MEDIUM-BLOB emoji runs in some agent profile files

The fixture errors on first file load with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 5839`. Because the fixture is session-scoped, every test in the file that uses `compose_data` (which is most of them) errors out, not just media services. On the operator's 5090 worktree, 32/34 `media-*` tests ERROR.

CI runs on Ubuntu, so the ratchet never sees the bug. The only way to surface it is on a Windows host with the bare `open(path, "r")` call.

## The fix (three parts)

### 1. The encoding

```python
with open(path, "r", encoding="utf-8") as f:
    compose = yaml.safe_load(f)
```

One file, one line, plus a comment that points at the ratchet. UTF-8 is the canonical Python default for portability; the BOM-stripping variant `encoding="utf-8-sig"` is also accepted by the ratchet (it checks that an `encoding=` keyword is present, not its value).

### 2. The static ratchet

`TestWindowsHostCompat::test_compose_reads_use_utf8` (in the same test file, class `TestWindowsHostCompat`). It parses the test file's own source with `ast` and visits every `open(...)` / `<obj>.open(...)` call, with or without a mode argument. Any non-binary call without an `encoding=` keyword is a regression. (The first cut was a regex keyed on a quoted mode argument; review of #3358 showed it let the modeless `open(path)` through -- the commonest bare shape -- so it was replaced by the AST walk, which also ignores docstrings and comments for free.)

Why a static ratchet instead of a runtime test? Per the cross-cutting comment in CLAUDE.md: "static ratchets over runtime tests when the runtime test would never reach the bug (e.g. ... )." The runtime test (the compose_data fixture loading) only reaches the bug on a Windows host. A future contributor editing the file on any OS would only see the failure on Windows. A static source ratchet is platform-agnostic and runs in 0.01s.

### 3. The runtime smoke test

`TestWindowsHostCompat::test_docker_hardening_runs_on_windows` accepts `compose_data` as a pytest fixture parameter and asserts the dict is non-empty. This is the runtime counterpart to the static ratchet — the static one pins the source, this one pins the load.

On Linux it always passes (no UTF-8 issue to trip on). On Windows it is the canary that the encoding fix at line 120 is still in place.

## Why not fix the wider 100+ read_text() calls?

A separate grep identified ~100+ `Path.read_text()` calls in the test suite without `encoding=`. The same cp1252 trap would hit some of them on Windows if their target files contain UTF-8 multi-byte sequences. The operator's directive was "Windows cp1252 hardening test fix" — specifically the docker_hardening test that was actively blocking the ratchet on this host.

The wider audit is a separate lane:
- Sweep `pmoves/tests/` for `Path.read_text()` and `open(path, "r")` calls without `encoding=`.
- File-by-file decision: is the target file UTF-8 (compose, JSON, AGENTS.md) or pure ASCII (workflow yaml, sample fixtures)?
- Add `encoding="utf-8"` to the UTF-8 cases; leave the ASCII cases alone (cp1252 is a superset of ASCII).

That lane is NOT in this PR's scope. The ratchet class `TestWindowsHostCompat` could grow a second test (`test_read_text_calls_use_utf8`) when the sweep happens; for now, the ratchet is scoped to `open(...)` calls in `test_docker_hardening.py` only.

## 4-bucket × 5-class taxonomy

### 1. Defects

| # | Class | What | Where | Why it hurt |
|---|-------|------|-------|-------------|
| 1.1 | encoding-on-read | `open(path, "r")` uses the platform default encoding. | `pmoves/tests/hardening/test_docker_hardening.py:120` (pre-fix) | 32/34 `media-*` tests ERROR on the operator's 5090 worktree (Windows, cp1252 default) |
| 1.2 | pre-existing-not-introduced | Same defect in `test_amd_overlay_reachable.py`'s `_TolerantLoader` does NOT exist — that file's read uses `path.read_text(encoding="utf-8")` explicitly. | `pmoves/tests/make/test_amd_overlay_reachable.py` | (n/a — already correct) |

### 2. Decisions

| # | Class | What | Why | Alternative considered | Cost of alternative |
|---|-------|------|-----|------------------------|---------------------|
| 2.1 | fix-the-source-not-skip-the-test | The operator had worked around the bug by `pytest.skip`-ing media services on Windows (no record in repo, but discussed in the lane handoff). I fixed the source. | Skipping a test on a host class erodes the gate; the test is the contract. | Skip media tests on Windows | Silent blindness on a real production host class |
| 2.2 | static-ratchet | The ratchet is an AST walk over the test file's source, not a runtime test. | The runtime test only fails on Windows; a future contributor on Linux would not see the bug. The static ratchet pins the source. | Runtime test on Windows only | Test would not run on CI (Linux) |
| 2.3 | fold-into-#3358-vs-separate-PR | The fix is a single-line change in a test file, not a runtime compose change. Operator said "separate lane (or fold into this PR's next push)". I folded it in. | One PR per logical change is the rule, but the encoding fix is part of "make the test suite pass on the 5090 worktree" which is the same goal as #3358. | Separate PR | Two PRs, two reviews, same effect |
| 2.4 | scope-to-docker_hardening-only | The same `read_text()`-without-encoding pattern exists in ~100+ test files. The fix is scoped to `test_docker_hardening.py` only. | The operator's directive was the hardening test specifically. The wider audit is a follow-up. | Sweep the whole test suite | Out of scope for this PR; the wider sweep's failures may surface other host-class bugs that need their own ratchets |

### 3. Operations

| # | Class | What | Measured | Repeatability |
|---|-------|------|----------|---------------|
| 3.1 | ratchet-self-reference-defence | The ratchet's own docstring contains the literal `open(path, "r")` as documentation. Without scrubbing, the ratchet trips on its own example. | The `test_compose_reads_use_utf8` first implementation failed with "5 false positives, all from the ratchet's own docstring". The fix is `re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', ...)` before matching. | A future contributor who adds a new `open(...)` call with `encoding=` in the test will not trigger the ratchet. A new call without `encoding=` will. |
| 3.2 | comment-stripping-false-positives | Same as 3.1 but for `# ...` comments. A second `re.sub(r'#[^\n]*', ...)` is needed because comments can also contain the literal `open(path, "r")`. | Without this, the ratchet tripped on the inline comment at line 980 (`# triple-quoted blocks (including the literal `open(path, "r")`)`. | Same as 3.1. |
| 3.2a | regex-missed-modeless-open | The regex ratchet (3.1/3.2) required a quoted mode argument, so a modeless `open(path)` -- which uses the platform default encoding, the exact trap -- passed. Replaced by an `ast` walk: no docstring/comment scrubbing needed, nested parentheses handled, binary modes exempt. | Positive control: rewriting the fixture's read to `open(path)` in a scratch copy fails the AST ratchet with `line 125: open(path)`; the old regex passed it. | Prefer AST over regex for any source-shape ratchet in Python. |
| 3.3 | host-class-ratchet-is-rare | Most ratchets in the project are cross-platform (compose syntax, dependency pins, file-mode). This ratchet is one of the few that gates a host class. | The CI matrix runs Ubuntu only; the operator's 5090 is one of three known Windows hosts. The ratchet is a guard, not a gate. | n/a |

### 4. Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.1 | same-shape-as-claude_backend-cp1252 | The `pmoves/tools/claude_backend.py:1` module-level fix to add `PMOVES_CLAUDE_HOME` env override for `_home_settings_path()` is the same shape: a Windows-specific default that needs an explicit override. | `pmoves/tools/claude_backend.py:_home_settings_path()` | When the operator does the next sweep, that module is the next file. Same fix recipe. |
| 4.2 | same-shape-as-bash_resolver | `pmoves/tools/bash_resolver.py:67` (`find_bash`) was the pattern for "make host-specific defaults work everywhere": a function that probes 3 known locations and returns the right one, instead of `shutil.which()` returning the wrong one. | `pmoves/tools/bash_resolver.py:67` | The Windows-host compat pattern across the project is "explicit override" (encoding, HOME, bash) — never "platform default" |
| 4.3 | lane-AGInT-cross-link | This fix lands in the same PR (#3358) as the media-audio GPU runtime fix. Operator approval 2026-10-15. | PR #3358 branch `fix/media-audio-gpu-runtime` | Two related ratchets in one PR — both make the test suite work on the 5090 worktree |
| 4.4 | ci-misses-windows | The CI matrix does not run on Windows. The only host running this test is the operator's worktrees. | `.github/workflows/python-tests.yml` (`runs-on: ubuntu-latest`) | A future lane could add a `windows-latest` runner to the matrix; the ratchet would then gate on every PR. For now, the 5090 worktree is the canary. |

## Ratchet pin (the thing that catches the next person)

The new class `TestWindowsHostCompat` in `pmoves/tests/hardening/test_docker_hardening.py`:

```python
class TestWindowsHostCompat:
    def test_compose_reads_use_utf8(self):
        """AST walk over the test file's own source: every non-binary
        `open(...)` / `<obj>.open(...)` call, modeless or not, must pass encoding=."""

    def test_docker_hardening_runs_on_windows(self, compose_data):
        """Runtime smoke: the fixture loads on this host. Linux passes always;
        Windows is the canary."""
```

A future contributor who adds a `with open(some_path, "r") as f:` to this file (forgetting `encoding=`) gets a 1-line, 0.01s test failure on the next Windows run. The error message lists the bare call so the fix is obvious.

## Provenance (DARKXSIDE 2026-09-16: no workarounds; SDK + doc provenance required)

- **SDK file:line** — `pmoves/tests/hardening/test_docker_hardening.py:120` (the fix); `pmoves/tests/hardening/test_docker_hardening.py:947-1014` (the ratchet class).
- **Test contract** — `pmoves/tests/hardening/test_docker_hardening.py` 239 pass / 14 fail / 49 skip on this Windows host (was 32/34 ERROR pre-fix on media services); the 14 remaining failures are pre-existing (network secrets, GitHub runner checks, validation script integration) and not related to encoding.
- **AGNOTE** — RELEASE row appended at `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:3398` (next to the existing media-audio row at 3397).
- **LEARNINGS** — this file.
- **PR + branch** — #3358 on `fix/media-audio-gpu-runtime` (this agent, mvs_5d5493b128b640e9aff8d45adcc77a66).
- **Incident** — `pmoves/tests/hardening/test_docker_hardening.py` 32/34 media services ERROR on PMOVES-5090 2026-10-15; reproducer = `pytest pmoves/tests/hardening/test_docker_hardening.py -k media-audio`.
