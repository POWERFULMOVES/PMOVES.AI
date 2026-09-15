#!/usr/bin/env python3
"""Validate-dockerfile-paths ratchet.

No-network scan of every `pmoves/docker-compose*.yml` overlay + every
`Dockerfile*` under `pmoves/`. Closes the third pattern from the
operator's #2358 meta-callout:

> "the file the developer touched ≠ the file the runner builds"

Same shape as the other two ratchets (fork-registry, validate-tac,
validate-composes): static analysis, no GitHub API, no token
privilege, ~100ms on the full fleet. Fails (exit 1) on:

  1. BROKEN_BUILD — a compose `build:` stanza points at a Dockerfile
     that doesn't exist on disk. This is the #2358 shape: a PR
     "fixed" the Dockerfile in the wrong file, compose built a stale
     one, the operator didn't notice until bring-up. The ratchet
     catches it at PR time, before any node executes.

  2. ORPHAN_DOCKERFILE — a Dockerfile exists in `pmoves/` but is not
     referenced by any compose `build:`. Most are intentional
     (alternative variants, legacy, base images, side-channel CI
     paths) and live in the baseline. New orphans are caught
     immediately.

  3. COPY_UNRESOLVED — a `COPY`/`ADD` source inside a Dockerfile does
     not exist under the build context its compose stanza declares.
     This is the inverse of the first two: they check paths TO
     Dockerfiles, this checks paths INSIDE them. Found the expensive
     way in #2468 — `mai-ui-agent` does `COPY requirements.txt .`
     against `context: .` (= `pmoves/`), where no such file exists,
     so the image dies on its first COPY. Baselined separately in
     `pmoves/configs/dockerfiles/_known_copy_gaps.yaml`, with stale
     entries failing the gate the same way new findings do.

  4. DOCKERIGNORE_EXCLUDED — a `COPY` source that exists on disk but is
     excluded by the context's `.dockerignore`, so it never reaches the
     daemon. Same build break, harder to see.

The ratchet only goes DOWN over time. The baseline file is committed
and reviewable in PR diffs. Adding to the baseline requires a clear
reason; removing from the baseline is a one-line win that should ship
in a fixup commit.

Usage:
    python3 pmoves/tools/validate_dockerfile_paths.py
    python3 pmoves/tools/validate_dockerfile_paths.py --json
    python3 pmoves/tools/validate_dockerfile_paths.py --list-orphans
    python3 pmoves/tools/validate_dockerfile_paths.py \
        --compose pmoves/docker-compose.yml
    python3 pmoves/tools/validate_dockerfile_paths.py --list-copy-skips
    python3 pmoves/tools/validate_dockerfile_paths.py --write-copy-baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES_DIR = REPO_ROOT / "pmoves"
COMPOSE_GLOB = "docker-compose*.yml"
DOCKERFILE_GLOB = "Dockerfile*"

# Where the operator-acknowledged orphan set lives. The ratchet
# allows anything listed here without complaint; the operator's
# job is to shrink it over time. Format: { "dockerfile/path: reason"
# } so the same file is human-readable AND machine-parseable.
BASELINE_PATH = (
    REPO_ROOT / "pmoves" / "configs" / "dockerfiles" / "_known_orphans.yaml"
)

# Directories under pmoves/ where we look for Dockerfiles. Anything
# outside this set is ignored (docs/, plans/, .git/, node_modules/,
# submodules, etc.). This is a separate allowlist rather than a
# denylist so the ratchet doesn't scan every byte of pmoves/ — the
# 100ms budget is for the real fleet, not for `pmoves/docs/`.
DOCKERFILE_PARENT_DIRS = (
    "services",
    "images",
    "integrations",
    "docker",
    "compose",
    "ui",
)

# We also pick up a top-level `pmoves/Dockerfile` if one exists.
TOP_LEVEL_DOCKERFILE = PMOVES_DIR / "Dockerfile"

# `.gitmodules` sections are `[submodule "name"]` with a `path = ...`
# line; the same expression `check_bind_sources.py:73` uses.
SUBMODULE_PATH_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$", re.MULTILINE)


@lru_cache(maxsize=1)
def _registered_submodule_paths() -> frozenset[str]:
    """Submodule paths as declared in .gitmodules, repo-root-relative.

    READ, not inferred from a directory name. `pmoves/integrations/archon`
    lives under `integrations/`, which DOCKERFILE_PARENT_DIRS calls
    in-scope, but it is a registered submodule: its Dockerfiles are in
    another repository and are never in this tree.

    Whether one is on disk answers a question about the runner's
    checkout depth, not about whether the compose file is correct.
    `pmoves/docker-compose.archon-ui.submodule.yml` points at
    `archon-ui-main/Dockerfile`, which IS present at the pinned
    submodule commit and absent in CI, where submodules are not
    checked out -- so the ratchet reported a broken build for a build
    that works. `.gitmodules` is in the tree, so it reads identically
    in CI and locally; the filesystem does not.

    A missing .gitmodules yields an empty set: a repo with no
    submodules exempts nothing, which is git's own semantics. If the
    file were somehow lost, every submodule path becomes in-scope and
    the ratchet fails loudly rather than passing quietly.
    """
    gitmodules = REPO_ROOT / ".gitmodules"
    if not gitmodules.is_file():
        return frozenset()
    text = gitmodules.read_text(encoding="utf-8")
    return frozenset(
        m.group(1).replace("\\", "/").strip("/")
        for m in SUBMODULE_PATH_RE.finditer(text)
    )


def _yaml_safe_load_with_compose_tags(text):
    """Compose uses !override / !reset as merge markers. PyYAML's
    SafeLoader doesn't know about them, so we register no-op
    constructors before loading. Without this, every overlay that
    uses `!override` would fail to parse."""
    import yaml

    def _noop(loader, node):
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node)
        return loader.construct_scalar(node)

    for tag in ("!override", "!reset"):
        yaml.SafeLoader.add_constructor(tag, _noop)
    return yaml.safe_load(text)


def _all_compose_files() -> list[Path]:
    if not PMOVES_DIR.exists():
        return []
    return sorted(PMOVES_DIR.glob(COMPOSE_GLOB))


def _all_dockerfile_paths() -> list[Path]:
    """Walk the allowlist dirs + the top-level `pmoves/Dockerfile`.
    Returns paths relative to REPO_ROOT for stable output."""
    out: list[Path] = []
    for parent in DOCKERFILE_PARENT_DIRS:
        d = PMOVES_DIR / parent
        if not d.exists():
            continue
        for p in d.rglob(DOCKERFILE_GLOB):
            if not p.is_file():
                continue
            out.append(p)
    if TOP_LEVEL_DOCKERFILE.exists() and TOP_LEVEL_DOCKERFILE.is_file():
        out.append(TOP_LEVEL_DOCKERFILE)
    return sorted(out)


def _is_in_scope_build_target(abs_path: Path) -> bool:
    """Decide if a compose build target is in-scope for the ratchet.

    IN scope (will be checked + flagged if missing):
      - paths under pmoves/{services,images,integrations,docker,compose,ui}/
      - the top-level pmoves/Dockerfile

    OUT of scope (skipped):
      - paths under pmoves/vendor/  (external repos, brought in
        via `make submodules` or manual clone at bring-up)
      - paths under CATACLYSM_STUDIOS_INC / provisions
        (operator-side workspace, gitignored or sibling clone)
      - paths inside any submodule REGISTERED in .gitmodules, read
        from that file rather than guessed from a directory name —
        their Dockerfiles are in another repository, so whether one is
        on disk depends on the runner's checkout depth. This includes
        submodules nested under an in-scope parent dir, such as
        `pmoves/integrations/archon`
      - paths into sibling checkouts outside `pmoves/` entirely
      - any ${VAR} that resolves to a non-pmoves/ path

    The ratchet only flags in-scope broken builds. Out-of-scope
    paths are the operator's responsibility to keep synced; we just
    don't pretend to know whether they're correct.
    """
    if not abs_path.is_absolute():
        abs_path = (REPO_ROOT / abs_path).resolve()
    try:
        rel = abs_path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    parts = rel.parts
    if not parts or parts[0] != "pmoves":
        return False
    if len(parts) < 2:
        return False
    # pmoves/ subdirs we DON'T scan: vendor/, CATACLYSM_STUDIOS_INC/
    # (under the operator's home), and any other sibling repo
    # referenced as a submodule/provisions workspace.
    if parts[1] in {"vendor"}:
        return False
    if "provisions" in parts:
        return False
    # Registered submodules, wherever they sit. This has to come BEFORE
    # the DOCKERFILE_PARENT_DIRS check: `pmoves/integrations/archon` is
    # a submodule that lives inside an in-scope parent dir, so a
    # name-based allowlist alone would claim it.
    rel_posix = rel.as_posix()
    for sub in _registered_submodule_paths():
        if rel_posix == sub or rel_posix.startswith(sub + "/"):
            return False
    if parts[1] in DOCKERFILE_PARENT_DIRS:
        return True
    if len(parts) == 2 and parts[1] == "Dockerfile":
        return True
    return False


def _load_baseline() -> set[str]:
    """Read the operator-acknowledged orphan set.

    The baseline file is a YAML mapping {path: reason}. The KEYS are
    the orphan paths (relative to repo root); the VALUES are the
    operator's reason for keeping this file orphaned. Anything not
    in the baseline AND not referenced by any compose is a ratchet
    failure.

    If the file is missing or malformed, the ratchet behaves as if
    the baseline is empty (fail-closed) — operators have to commit
    the baseline for the ratchet to know which orphans are
    intentional. This is the same shape as validate_tac.
    """
    if not BASELINE_PATH.exists():
        return set()
    import yaml
    try:
        with BASELINE_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return set()
    if not data:
        return set()
    if isinstance(data, dict):
        return {str(k) for k in data.keys()}
    if isinstance(data, list):
        return {str(x) for x in data if x}
    return set()


def _resolve_build_target(
    compose_file: Path,
    service: str,
    build_field,
) -> tuple[Path, str] | None:
    """Resolve a `build:` stanza into a (path, context) tuple.

    `build:` can be:
      - a string: shorthand for { context: <string> }
      - a mapping: { context: ./foo, dockerfile: Dockerfile.bar }
      - null: skip (use prebuilt `image:` instead)

    Default `dockerfile` is `Dockerfile` (relative to context).
    Default `context` is `.` (relative to the compose file's
    directory, which is `pmoves/` for every overlay in this repo).

    Env-var defaults of the form `${VAR:-default}` are resolved to
    their default value (the ratchet can't actually evaluate the
    env at scan time, but the default is what compose would use
    when the env var is unset, which is the most common case).

    Returns the resolved path (absolute) + the context string for
    diagnostics, or None if the service isn't a `build:` service.
    """
    if build_field is None:
        return None
    if isinstance(build_field, str):
        context = _resolve_env_default(build_field)
        dockerfile = "Dockerfile"
    elif isinstance(build_field, dict):
        context = _resolve_env_default(build_field.get("context", "."))
        dockerfile = _resolve_env_default(build_field.get("dockerfile", "Dockerfile"))
    else:
        return None

    # `context` is relative to the compose file's directory, which is
    # always `pmoves/` in this repo. If someone ever adds a compose
    # at a different depth we'll need to walk up; today every overlay
    # sits directly in `pmoves/`.
    compose_dir = compose_file.parent
    context_path = (compose_dir / context).resolve()
    dockerfile_path = (context_path / dockerfile).resolve()
    return dockerfile_path, context


# Env-var default pattern: ${VAR} or ${VAR:-default}. The ratchet
# substitutes the default (or the literal `default` for ${VAR:-default}
# form). Patterns that are more exotic (${VAR-default} with no colon,
# nested expansions) are out of scope — the ratchet keeps the literal
# string and the path check will fall through, but most real PMOVES
# compose uses the canonical ${VAR:-default} form.
_ENV_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-)?([^}]*)\}")


def _resolve_env_default(value: str) -> str:
    """Substitute `${VAR:-default}` (and `${VAR}`) with the default
    value. If the variable has no default, the literal `${VAR}` is
    preserved so the ratchet can still surface a finding (the
    dockerfile path won't exist on disk)."""
    def _sub(m: re.Match) -> str:
        var_name = m.group(1)
        default = m.group(2)
        # ${VAR} with no default: keep the literal so the ratchet
        # can surface the unresolved reference.
        if default is None:
            return m.group(0)
        return default
    return _ENV_DEFAULT_RE.sub(_sub, value)


def _scan_compose_for_builds(compose_file: Path) -> list[dict]:
    """Return the list of (service, dockerfile_path) for every
    service with a `build:` stanza. Path is absolute; the caller's
    job to make it repo-relative for output."""
    try:
        with compose_file.open(encoding="utf-8") as fh:
            data = _yaml_safe_load_with_compose_tags(fh)
    except Exception as e:
        return [{
            "kind": "parse-error",
            "file": str(compose_file.relative_to(REPO_ROOT)),
            "service": "<root>",
            "detail": f"could not parse YAML: {e}",
        }]
    if not isinstance(data, dict):
        return []
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return []
    out: list[dict] = []
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        build = svc.get("build")
        if build is None:
            # prebuilt `image:` service; no build target to validate
            continue
        resolved = _resolve_build_target(compose_file, svc_name, build)
        if resolved is None:
            continue
        dockerfile_abs, context = resolved
        out.append({
            "compose_file": str(compose_file.relative_to(REPO_ROOT)),
            "service": str(svc_name),
            "dockerfile_abs": dockerfile_abs,
            "dockerfile_rel": _try_relative(dockerfile_abs),
            "context": context,
        })
    return out


def _try_relative(path: Path) -> str:
    """Best-effort conversion to repo-relative path. Falls back to
    the absolute path if the file is outside the repo (shouldn't
    happen, but defensive against hand-crafted compose contexts).
    Always uses forward slashes so the path matches the baseline
    YAML keys (which also use forward slashes per YAML convention)."""
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return str(path).replace("\\", "/")
    # pathlib returns PosixPath on Linux (forward slashes) and
    # WindowsPath on Windows (backslashes); as_posix() normalizes
    # both cases to forward slashes.
    return rel.as_posix()


def _scan_one_compose(path: Path) -> list[dict]:
    """Scan a single compose file, returning build-target findings
    as a list of (compose_file, service, dockerfile_rel) tuples +
    any parse errors."""
    return _scan_compose_for_builds(path)


# -- COPY_UNRESOLVED --------------------------------------------------
#
# The name of this file reads like it validates paths INSIDE Dockerfiles.
# Until now it did the opposite: it validated paths TO Dockerfiles
# (BROKEN_BUILD) and Dockerfiles nobody points at (ORPHAN_DOCKERFILE).
# The gap was found the expensive way in #2468:
#
#     pmoves/services/mai-ui-agent/Dockerfile:  COPY requirements.txt .
#     compose stanza:                           context: .     # = pmoves/
#
# There is no `pmoves/requirements.txt`, so the image dies on its first
# COPY. Sibling `evo-controller` gets it right from the same root context
# -- `COPY services/evo-controller/requirements.txt .` -- which is what
# makes this a drift class rather than a one-off typo: the correct form
# and the broken form look equally plausible in review.
#
# `_resolve_build_target` already hands back the context for every
# compose-referenced Dockerfile. This finding class is what that context
# was always for.
#
# Keyed by (dockerfile:line, context, source) rather than by compose
# file, because the defect lives in the Dockerfile/context pair. A new
# overlay referencing an already-baselined build does not churn the
# baseline.

COPY_BASELINE = (
    REPO_ROOT / "pmoves" / "configs" / "dockerfiles" / "_known_copy_gaps.yaml"
)

# Flags docker accepts on COPY/ADD. `--from` is the load-bearing one: it
# resolves against a build stage or an external image, NOT the context, so
# there is nothing on disk for a static scan to check.
_COPY_FLAG_RE = re.compile(
    r"^--(from|chown|chmod|link|parents|exclude|checksum|keep-git-dir)(=.*)?$"
)

# Remote sources. ADD accepts URLs and git refs; COPY does not, but we
# skip them uniformly rather than pretending to fetch anything.
_REMOTE_SRC_RE = re.compile(r"^(https?://|ftp://|git@|git://|github\.com/)", re.I)

# Any shell-expansion shape. Docker interpolates ARG/ENV into COPY
# operands and the value is only known at build time, so guessing a
# default here would invent findings. These are recorded as skips with a
# reason instead of being resolved or silently dropped.
_INTERP_RE = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")

_GLOB_CHARS = set("*?[")

_ESCAPE_DIRECTIVE_RE = re.compile(r"^\s*#\s*escape\s*=\s*(\S)", re.I)

_COPY_INSTR_RE = re.compile(r"^(COPY|ADD)\s+(.*)$", re.I)


def _escape_char(text: str) -> str:
    """Honour a `# escape=` parser directive. Directives are only valid
    before the first non-comment line; anything later is a plain comment."""
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if not s.startswith("#"):
            break
        m = _ESCAPE_DIRECTIVE_RE.match(s)
        if m:
            return m.group(1)
    return "\\"


def _logical_lines(text: str, escape_char: str = "\\") -> list:
    """Join Dockerfile continuation lines into logical instructions.

    Returns (line_number_of_first_physical_line, logical_line) pairs.
    Comment-only lines are dropped, including ones interleaved inside a
    continuation -- docker strips those before parsing, and a scanner that
    does not will mis-join the next instruction onto the previous one.

    `#` mid-line is NOT a comment in a Dockerfile; only a line whose first
    non-space character is `#` is.
    """
    out = []
    buf = []
    start_no = 0
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if not buf:
            if not stripped:
                continue
            start_no = i
        if stripped.endswith(escape_char):
            buf.append(stripped[: -len(escape_char)])
            continue
        buf.append(stripped)
        out.append((start_no, " ".join(p for p in buf if p).strip()))
        buf = []
    if buf:
        out.append((start_no, " ".join(p for p in buf if p).strip()))
    return out


def _split_operands(rest: str):
    """Split the operand portion of a COPY/ADD into tokens.

    Handles the JSON-array form (`COPY ["src", "dest"]`) and the shell
    form with single/double quotes. Returns None when the form is not
    parseable, so the caller can skip rather than guess.
    """
    rest = rest.strip()
    if rest.startswith("["):
        try:
            parsed = json.loads(rest)
        except Exception:
            return None
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            return None
        return parsed
    toks = []
    cur = []
    quote = None
    i = 0
    while i < len(rest):
        ch = rest[i]
        if quote:
            if ch == "\\" and i + 1 < len(rest):
                cur.append(rest[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            else:
                cur.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        toks.append("".join(cur))
    if quote is not None:
        return None
    return toks


def parse_copy_instructions(dockerfile: Path) -> list:
    """Every COPY/ADD in a Dockerfile, parsed to the point where only the
    build context is missing.

    Each entry: {line, instruction, flags, sources, dest, skip}. `skip` is
    set (and `sources` left empty) when the instruction cannot be checked
    statically -- a `--from=` stage, a heredoc, or an unterminated quote.
    """
    try:
        text = dockerfile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    esc = _escape_char(text)
    out = []
    for line_no, logical in _logical_lines(text, esc):
        m = _COPY_INSTR_RE.match(logical)
        if not m:
            continue
        instr = m.group(1).upper()
        rest = m.group(2)

        flags = []
        tokens = rest.split(None, 1)
        while tokens and tokens[0].startswith("--"):
            if not _COPY_FLAG_RE.match(tokens[0]):
                break
            flags.append(tokens[0])
            rest = tokens[1] if len(tokens) > 1 else ""
            tokens = rest.split(None, 1)

        entry = {
            "line": line_no,
            "instruction": instr,
            "flags": flags,
            "sources": [],
            "dest": None,
            "skip": None,
        }

        if any(f.startswith("--from") for f in flags):
            entry["skip"] = "--from= (resolves against a build stage, not the context)"
            out.append(entry)
            continue

        if "<<" in rest:
            entry["skip"] = "heredoc form (content is inline, not a context path)"
            out.append(entry)
            continue

        operands = _split_operands(rest)
        if operands is None:
            entry["skip"] = "unparseable operands (unterminated quote or malformed JSON form)"
            out.append(entry)
            continue
        if len(operands) < 2:
            entry["skip"] = "fewer than two operands (malformed instruction)"
            out.append(entry)
            continue

        entry["dest"] = operands[-1]
        entry["sources"] = operands[:-1]
        out.append(entry)
    return out


def _load_dockerignore(context_path: Path) -> list:
    """Parse `<context>/.dockerignore` into (is_negation, pattern) pairs.

    Only ever used to ADD a finding, never to suppress one: a source
    excluded by dockerignore fails the build the same way a missing source
    does, so treating dockerignore as a reason to stay quiet would hide
    the exact defect this class exists to catch.
    """
    di = context_path / ".dockerignore"
    if not di.is_file():
        return []
    pats = []
    try:
        lines = di.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        neg = s.startswith("!")
        if neg:
            s = s[1:].strip()
        s = s.strip("/")
        if s:
            pats.append((neg, s))
    return pats


def _dockerignore_regex(pat: str):
    """Compile one `.dockerignore` pattern to a regex.

    Docker patterns are NOT gitignore patterns, and the difference matters
    here: they are anchored at the build-context root, and `*` does not
    cross a `/`. So `*.md` excludes `README.md` but NOT `docs/guide.md`,
    and `__pycache__` excludes a top-level `__pycache__/` but not
    `app/__pycache__/`. Matching those the gitignore way would invent
    DOCKERIGNORE_EXCLUDED findings for files docker actually ships, which
    on a hard gate means a spurious red build.
    """
    out = ["^"]
    i = 0
    n = len(pat)
    while i < n:
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pat.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        c = pat[i]
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pat.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
            else:
                out.append(pat[i:j + 1])
                i = j + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    out.append("$")
    try:
        return re.compile("".join(out))
    except re.error:
        return None


def _dockerignored(rel_source: str, patterns: list):
    """Return the matching pattern if `rel_source` is excluded, else None.

    Excluding a directory excludes everything under it, so each ancestor
    of the source is tested too. Last matching pattern wins, which is how
    a `!keep` line after a broad exclude un-excludes.
    """
    rel = rel_source.strip("/").replace("\\", "/")
    candidates = [rel]
    parts = rel.split("/")
    for k in range(1, len(parts)):
        candidates.append("/".join(parts[:k]))

    hit = None
    for neg, pat in patterns:
        rx = _dockerignore_regex(pat.strip("/"))
        if rx is None:
            continue
        if any(rx.match(c) for c in candidates):
            hit = None if neg else pat
    return hit


def _copy_key(f: dict) -> str:
    return f"{f['kind']}|{f['dockerfile']}:{f['line']}|{f['context']}|{f['source']}"


def scan_copy_sources(compose_findings: list):
    """Resolve every COPY/ADD source against its stanza's build context.

    Returns (findings, skips). A (dockerfile, context) pair is scanned once
    even when several overlays build it, so the baseline is keyed to the
    defect rather than to how many compose files happen to reference it.
    """
    findings = []
    skips = []
    seen_pairs = set()
    seen_keys = set()

    for f in compose_findings:
        if f.get("kind") == "parse-error":
            continue
        df_abs = f.get("dockerfile_abs")
        if not df_abs or not Path(df_abs).is_file():
            # BROKEN_BUILD already covers a missing Dockerfile; a second
            # finding for the same defect would just be noise.
            continue
        df_abs = Path(df_abs)
        df_rel = f.get("dockerfile_rel", "")
        if not _is_in_scope_build_target(df_abs):
            continue

        compose_dir = (REPO_ROOT / f["compose_file"]).parent
        context_path = (compose_dir / f["context"]).resolve()
        ctx_rel = _try_relative(context_path)
        pair = (df_rel, ctx_rel)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        if not context_path.is_dir():
            # A context that is not a directory is a build break too, but
            # it belongs to the compose stanza, not to the Dockerfile.
            continue

        di_patterns = _load_dockerignore(context_path)

        for entry in parse_copy_instructions(df_abs):
            if entry["skip"]:
                skips.append({
                    "dockerfile": df_rel,
                    "line": entry["line"],
                    "context": ctx_rel,
                    "reason": entry["skip"],
                })
                continue
            for src in entry["sources"]:
                if _REMOTE_SRC_RE.match(src):
                    skips.append({
                        "dockerfile": df_rel,
                        "line": entry["line"],
                        "context": ctx_rel,
                        "reason": f"remote source {src!r} (fetched at build time)",
                    })
                    continue
                if _INTERP_RE.search(src):
                    skips.append({
                        "dockerfile": df_rel,
                        "line": entry["line"],
                        "context": ctx_rel,
                        "reason": (
                            f"ARG/ENV interpolation in {src!r} "
                            f"(value known only at build time)"
                        ),
                    })
                    continue

                # A leading `/` in a COPY source is relative to the context
                # root, not to the filesystem root.
                cleaned = src.lstrip("/")
                if cleaned in ("", "."):
                    continue

                kind = "COPY_UNRESOLVED"
                detail = None
                if set(cleaned) & _GLOB_CHARS:
                    import glob as _glob

                    matches = _glob.glob(str(context_path / cleaned), recursive=True)
                    if not matches:
                        detail = (
                            f"glob {src!r} matches nothing under context "
                            f"{ctx_rel}/ -- docker fails the build with "
                            f"'no source files were specified'"
                        )
                else:
                    target = (context_path / cleaned).resolve()
                    try:
                        target.relative_to(context_path)
                    except ValueError:
                        detail = (
                            f"{src!r} resolves outside the build context "
                            f"{ctx_rel}/ -- docker refuses paths outside the context"
                        )
                    else:
                        if not target.exists():
                            detail = (
                                f"{src!r} does not exist under context {ctx_rel}/ "
                                f"(looked for {_try_relative(target)})"
                            )
                        else:
                            ignored = _dockerignored(cleaned, di_patterns)
                            if ignored:
                                kind = "DOCKERIGNORE_EXCLUDED"
                                detail = (
                                    f"{src!r} exists but is excluded by "
                                    f"{ctx_rel}/.dockerignore pattern {ignored!r}, so "
                                    f"it is not in the context sent to the daemon"
                                )

                if detail is None:
                    continue
                fin = {
                    "kind": kind,
                    "dockerfile": df_rel,
                    "line": entry["line"],
                    "context": ctx_rel,
                    "source": src,
                    "detail": detail,
                }
                k = _copy_key(fin)
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                findings.append(fin)

    return findings, skips


def load_copy_baseline() -> set:
    """Same list-of-strings shape as the command-anchors baseline, so the
    two ratchets read alike in a PR diff."""
    if not COPY_BASELINE.is_file():
        return set()
    keys = set()
    for line in COPY_BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- "):
            keys.add(line[2:].strip().strip('"'))
    return keys


def write_copy_baseline(findings: list) -> None:
    COPY_BASELINE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Baselined COPY/ADD source gaps -- validate_dockerfile_paths.py",
        "#",
        "# Each entry is a COPY or ADD whose source does not resolve against the",
        "# build context its compose stanza declares. They are recorded so the",
        "# gate can be enforced today; they are NOT approved. Every one of them",
        "# is an image that dies on that instruction, or a file silently absent",
        "# from the image. The list may shrink. Adding to it should require",
        "# saying why.",
        "#",
        "# Key: KIND|<dockerfile>:<line>|<build context>|<source operand>",
        "known_copy_gaps:",
    ]
    for k in sorted({_copy_key(f) for f in findings}):
        lines.append(f'  - "{k}"')
    # newline="" so the file is byte-identical whether it was regenerated
    # on Windows or in CI. write_text() emits CRLF on Windows, and the next
    # Linux re-baseline would then rewrite every line as a spurious diff.
    with COPY_BASELINE.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines) + "\n")


def _summary(by_kind: dict[str, int]) -> str:
    if not by_kind:
        return "no findings"
    parts = ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items()))
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-orphans",
        action="store_true",
        help="only list orphan Dockerfiles (Dockerfiles not referenced by any compose, not in baseline); don't fail",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    parser.add_argument(
        "--compose",
        type=Path,
        help="scan a single compose file (test-only path; for CI use the default glob)",
    )
    parser.add_argument(
        "--write-copy-baseline",
        action="store_true",
        help=(
            "record today's COPY_UNRESOLVED / DOCKERIGNORE_EXCLUDED findings "
            "as the accepted baseline. Only for the initial seed or a "
            "deliberate acceptance — every entry is a real build break."
        ),
    )
    parser.add_argument(
        "--list-copy-skips",
        action="store_true",
        help=(
            "diagnostic: list COPY/ADD sources the scan deliberately did not "
            "check (--from= stages, remote URLs, ARG/ENV interpolation) with "
            "the reason for each; always exits 0"
        ),
    )
    parser.add_argument(
        "--baseline-add",
        type=str,
        default=None,
        help=(
            "add a single dockerfile path (relative to repo root) to "
            "the baseline file with a default reason; creates the "
            "baseline dir if missing. This is a convenience for "
            "the initial seed; once the baseline exists, edit it "
            "by hand so the reason is meaningful."
        ),
    )
    args = parser.parse_args()

    # Windows consoles default to cp1252 and raise on the em dashes below.
    # Same guard validate_command_anchors.py carries.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # baseline-add convenience path: write a single key then exit
    if args.baseline_add:
        return _baseline_add(args.baseline_add)

    compose_files = [args.compose] if args.compose else _all_compose_files()
    dockerfiles = _all_dockerfile_paths()
    baseline = _load_baseline()

    # Build a (compose_file, service) -> dockerfile_rel map and a
    # set of referenced dockerfile paths (repo-relative).
    compose_findings: list[dict] = []
    referenced: set[str] = set()
    for cf in compose_files:
        if not cf.exists():
            continue
        compose_findings.extend(_scan_one_compose(cf))
    for f in compose_findings:
        if "dockerfile_rel" in f:
            referenced.add(f["dockerfile_rel"])

    # COPY_UNRESOLVED / DOCKERIGNORE_EXCLUDED: paths INSIDE each
    # compose-referenced Dockerfile, resolved against that stanza's
    # declared build context.
    copy_findings, copy_skips = scan_copy_sources(compose_findings)
    copy_baseline = load_copy_baseline()
    copy_live = {_copy_key(f) for f in copy_findings}
    copy_new = [f for f in copy_findings if _copy_key(f) not in copy_baseline]
    # A baselined key that no longer occurs was FIXED. Leaving it in the
    # file would re-accept the same defect if it came back, which
    # contradicts the count-only-down claim the ratchet makes.
    copy_stale = sorted(copy_baseline - copy_live)

    if args.write_copy_baseline:
        write_copy_baseline(copy_findings)
        print(
            f"COPY baseline written: {len(copy_live)} entries -> "
            f"{COPY_BASELINE.relative_to(REPO_ROOT).as_posix()}"
        )
        return 0

    if args.list_copy_skips:
        if args.json:
            print(json.dumps({"copy_skips": copy_skips}, indent=2))
        else:
            print(f"# COPY/ADD sources not statically checkable: {len(copy_skips)}")
            for sk in copy_skips:
                print(f"  {sk['dockerfile']}:{sk['line']}  ({sk['context']})")
                print(f"      {sk['reason']}")
        return 0

    # BROKEN_BUILD: a compose build target that doesn't exist on disk
    # AND is in-scope for the ratchet (not a sibling submodule / vendor /
    # provisions path — those are external repos the ratchet can't
    # statically check).
    broken: list[dict] = []
    for f in compose_findings:
        if f.get("kind") == "parse-error":
            broken.append(f)
            continue
        rel = f.get("dockerfile_rel", "")
        if not rel:
            continue
        abs_p = REPO_ROOT / rel
        if abs_p.is_file():
            continue
        if not _is_in_scope_build_target(abs_p):
            # Sibling submodule / vendor / provisions — out of scope.
            # The ratchet is not the right place to fail on those;
            # the operator keeps them synced via `make submodules`.
            continue
        broken.append({
            "kind": "broken-build",
            "file": f["compose_file"],
            "service": f["service"],
            "dockerfile": rel,
            "context": f["context"],
            "detail": (
                f"compose build points at {rel} but no such file exists. "
                f"Check the service's `build.context` and `build.dockerfile` "
                f"in {f['compose_file']} — a stale or renamed Dockerfile "
                f"will silently build the wrong image."
            ),
        })

    # ORPHAN_DOCKERFILE: a Dockerfile in the repo that no compose
    # references AND isn't in the baseline
    orphan_set: set[str] = set()
    for d in dockerfiles:
        rel = _try_relative(d)
        if rel in referenced:
            continue
        if rel in baseline:
            continue
        orphan_set.add(rel)

    orphan_list = sorted(orphan_set)
    if args.list_orphans:
        # listing path: emit orphans + baseline + always exit 0 so
        # operators can grep / pipe the result.
        out = {
            "orphans_not_in_baseline": orphan_list,
            "baseline_count": len(baseline),
            "referenced_count": len(referenced),
            "total_dockerfiles": len(dockerfiles),
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"# orphans not in baseline: {len(orphan_list)}")
            for o in orphan_list:
                print(f"  {o}")
            print(f"# baseline size: {len(baseline)}")
            print(f"# referenced by compose: {len(referenced)}")
            print(f"# total dockerfiles: {len(dockerfiles)}")
        return 0

    problems: list[dict] = list(broken)
    for o in orphan_list:
        problems.append({
            "kind": "orphan-dockerfile",
            "file": o,
            "service": None,
            "dockerfile": o,
            "context": None,
            "detail": (
                f"{o} is not referenced by any compose build target. "
                f"Either wire it into a compose service's `build.dockerfile`, "
                f"or add it to pmoves/configs/dockerfiles/_known_orphans.yaml "
                f"with a reason for keeping it orphaned."
            ),
        })

    for f in copy_new:
        problems.append({
            "kind": f["kind"].lower().replace("_", "-"),
            "file": f["dockerfile"],
            "service": None,
            "dockerfile": f"{f['dockerfile']}:{f['line']}",
            "context": f["context"],
            "detail": f["detail"],
        })

    by_kind: dict[str, int] = {}
    for p in problems:
        by_kind[p["kind"]] = by_kind.get(p["kind"], 0) + 1

    if args.json:
        print(json.dumps({
            "ok": not problems and not copy_stale,
            "problems": problems,
            "summary": by_kind,
            "baseline_count": len(baseline),
            "referenced_count": len(referenced),
            "total_dockerfiles": len(dockerfiles),
            "copy_total": len(copy_findings),
            "copy_baselined": len(copy_findings) - len(copy_new),
            "copy_new": copy_new,
            "copy_stale_baseline": copy_stale,
            "copy_skipped": len(copy_skips),
        }, indent=2))
    else:
        print(
            f"COPY sources: {len(copy_findings)} findings, "
            f"{len(copy_findings) - len(copy_new)} baselined, {len(copy_new)} new "
            f"({len(copy_skips)} not statically checkable)"
        )
        if copy_stale:
            print(
                f"\nSTALE COPY BASELINE — {len(copy_stale)} "
                f"entr{'y' if len(copy_stale) == 1 else 'ies'} no longer occur:"
            )
            for k in copy_stale[:20]:
                print(f"  {k}")
            if len(copy_stale) > 20:
                print(f"  ... and {len(copy_stale) - 20} more")
            print("\nThese were fixed. Drop them so the same defect cannot return silently:")
            print("  make -C pmoves validate-dockerfile-paths-copy-baseline")
        if not problems and not copy_stale:
            print(f"validate-dockerfile-paths: OK ({len(dockerfiles)} dockerfiles, {len(referenced)} referenced, {len(baseline)} baseline)")
            return 0
        if not problems:
            return 1
        print(f"validate-dockerfile-paths: FAIL ({_summary(by_kind)})", file=sys.stderr)
        for p in problems:
            where = p.get("file", "?")
            svc = p.get("service") or "-"
            df = p.get("dockerfile", "?")
            print(f"  - [{p['kind']}] {where} (service={svc}) {df}", file=sys.stderr)
            if p.get("detail"):
                print(f"      {p['detail']}", file=sys.stderr)

    # JSON mode also returns the right exit code so the test
    # suite (and CI) can assert on it. (Non-JSON mode returns
    # from inside the `else` branch above; this return is for
    # the JSON path.)
    return 0 if (not problems and not copy_stale) else 1


def _baseline_add(rel_path: str) -> int:
    """Convenience path: add a single key to the baseline file. Only
    used during the initial seed; once the baseline is shaped, edit
    it by hand so the reason is meaningful."""
    if not rel_path.startswith("pmoves/"):
        print(f"--baseline-add expects a path relative to repo root starting with pmoves/; got {rel_path!r}", file=sys.stderr)
        return 2
    if not (REPO_ROOT / rel_path).exists():
        print(f"path {rel_path!r} does not exist in repo", file=sys.stderr)
        return 2
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    if BASELINE_PATH.exists():
        with BASELINE_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = {}
    if not isinstance(data, dict):
        print(f"baseline file is malformed (not a mapping); fix by hand: {BASELINE_PATH}", file=sys.stderr)
        return 2
    if rel_path in data:
        print(f"{rel_path} already in baseline", file=sys.stderr)
        return 0
    data[rel_path] = "seed: orphan at initial baseline creation; replace reason when wired up or removed"
    with BASELINE_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data,
            fh,
            sort_keys=True,
            default_flow_style=False,
            allow_unicode=True,
        )
    print(f"added {rel_path} to {BASELINE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
