#!/usr/bin/env python3
"""Image-staleness ratchet gate.

Reads `pmoves/images.yaml` (the build matrix for
`.github/workflows/build-images.yml`) and enforces, per image:

  1. build_inputs  -- the matrix entry names the files the builder actually
     consumes, and those files are present in the tree. An entry whose
     dockerfile cannot be found cannot be rebuilt, so it is stale by
     construction.
  2. build_path    -- the workflow that builds the matrix has a trigger other
     than `workflow_dispatch`. A matrix whose only workflow is manual-only
     is a fleet that CANNOT stay fresh: flute-gateway sat 65 days stale
     because nothing rebuilt it automatically.
  3. matrix_fields -- the entry declares every field THIS RATCHET requires
     (`name`, `dockerfile`). This is the tool's POLICY, not a list of the
     builder's reads: the build never reads `image` (the tag comes from
     `${{ matrix.name }}`) and treats `context` as a fallback, so requiring
     either would make law of a dead field.
  4. dead_context -- a repo-backed entry does not declare a `context` the
     build ignores. The workflow resolves
     `${{ matrix.repo && format('{0}/{1}', github.workspace, matrix.repo) || matrix.context }}`,
     so `context` is DEAD for a repo-backed entry: a non-`.` value there is
     a declaration the build never honours, hiding in plain sight.
  5. copy_sources -- every `COPY`/`ADD` source in the resolved Dockerfile
     resolves against the resolved BUILD CONTEXT. A Dockerfile is only
     buildable from a context that actually contains the files it copies:
     `COPY requirements.txt ./` inside `backend/Dockerfile` fails with
     "not found" unless the context IS `backend`. The `build_inputs` probe
     only asks whether the Dockerfile FILE exists; without this probe the
     gate reports VERIFIED for an image whose build cannot succeed.

Verdicts per claim: VERIFIED / DRIFTED / UNDECIDED, mirroring
`scripts/runbook_drift.py` (fail-closed: a probe that cannot answer says
UNDECIDED, never VERIFIED). A submodule that is declared in `.gitmodules`
but not checked out in this working tree is UNDECIDED -- "I could not check"
and "it is broken" are different answers.

TWO FAIL-CLOSED RULES ON TOP OF THAT:

  * The reader REFUSES TO GUESS. A matrix shape it does not recognise
    raises `MatrixParseError` instead of returning an empty list: an empty
    matrix means zero claims, zero problems and a GREEN hard gate -- a gate
    that verifies nothing, on exactly the tree it exists to police.
  * The gate's OWN probe gagging is INSTRUMENT-ERROR, not UNDECIDED. The
    rebuild path is UNMEASURED, not clean, so the gate fails on it.

The known-gaps baseline (`pmoves/configs/image_staleness/_known_gaps.yaml`)
is checked in BOTH directions: a gap that gets FIXED is STALE, and a gap
whose image is no longer in the matrix at all is ORPHANED. A baseline may
not outlive the matrix entry it describes.

Zero network. Read-only against the repo tree. Standard library only (no
PyYAML): the matrix is parsed with a small, purpose-built reader for the
`images:` list, so the gate runs on any runner with a bare python.

Usage:
    python3 pmoves/tools/image_staleness_ratchet.py
    python3 pmoves/tools/image_staleness_ratchet.py --json   # machine-readable
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGES_PATH = REPO_ROOT / "pmoves" / "images.yaml"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "build-images.yml"
GITMODULES_PATH = REPO_ROOT / ".gitmodules"
KNOWN_GAPS_PATH = (
    REPO_ROOT / "pmoves" / "configs" / "image_staleness" / "_known_gaps.yaml"
)

VERIFIED = "VERIFIED"
DRIFTED = "DRIFTED"
UNDECIDED = "UNDECIDED"
# A gap that is KNOWN, recorded, and tracked: the image's declared build
# input is absent, the absence is baselined with a reason, and the ratchet
# keeps reporting it. It is not DRIFTED (that would fail the gate for a
# defect the fleet has already accepted and recorded) and it is not VERIFIED
# (the image still cannot be rebuilt). The house pattern for this is
# `pmoves/configs/command_anchors/_known_gaps.yaml`.
KNOWN_GAP = "KNOWN-GAP"
# The gate's OWN probe could not measure. This is neither DRIFTED (nothing
# is proven broken) nor UNDECIDED (which the house rules reserve for "I
# could not check because a SUBMODULE is not checked out"): it is the
# INSTRUMENT failing. The gate fails CLOSED on it -- the check whose origin
# story is "the trigger silently disappeared and nobody noticed" must not
# go green because the probe that reads the trigger broke.
INSTRUMENT_ERROR = "INSTRUMENT-ERROR"

# The fields this ratchet REQUIRES every entry to declare. This is the
# TOOL'S POLICY, not a description of the builder's reads:
#
#   name        the build tags the image from it (${{ matrix.name }}), so an
#               entry without one publishes an untagged image.
#   dockerfile  the build opens it (`file: ${{ matrix.dockerfile || 'Dockerfile' }}`).
#               The workflow would fall back to `Dockerfile`, but the ratchet
#               demands the path be EXPLICIT so the build input can be
#               checked at all.
#
# `context` is NOT required: the builder treats it as a fallback, and for a
# repo-backed entry it is DEAD (see probe_dead_context, which states that rule
# directly). `image` is NOT required because the build NEVER reads it -- the
# tag comes from `name`. Both are DEAD FIELDS, and a dead field should not be
# law: requiring one would make the gate assert something the build does not
# do, and the thing it would actually catch (a dead `context` on a repo-backed
# entry) has its own probe.
REQUIRED_FIELDS = ("name", "dockerfile")

# Triggers that rebuild the fleet without a human clicking. `workflow_dispatch`
# is explicitly NOT one of them -- a manual-only workflow is the 65-day bug.
NON_MANUAL_TRIGGERS = ("push", "schedule", "repository_dispatch")


# --------------------------------------------------------------------------
# matrix parsing (stdlib only -- no PyYAML)
# --------------------------------------------------------------------------
def _strip_inline_comment(raw: str) -> str:
    """Drop a trailing `# comment`, respecting quoted scalars."""
    out: list[str] = []
    quote: str | None = None
    for i, ch in enumerate(raw):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


class MatrixParseError(Exception):
    """The matrix file is not in the shape this reader understands.

    The reader refuses to guess, and refusing means RAISING, not returning
    an empty list. An empty matrix means zero claims, zero problems and a
    GREEN hard gate -- a gate that verifies nothing while looking exactly
    like a gate that verified everything. That is the failure mode this
    ratchet exists to prevent, so it fails closed instead.
    """


def parse_images_matrix(text: str) -> list[dict]:
    """Parse the `images:` sequence out of pmoves/images.yaml.

    The file is a flat list of flat mappings of scalars; this reader handles
    exactly that shape (and refuses to guess at anything else).

    REFUSING IS A HARD FAILURE. A shape this reader does not recognise --
    flow-style `- {name: ...}` entries, a renamed or re-indented `images:`
    key, an entry with no `key: value` body, a nested block -- used to yield
    `[]` (or garbage entries), and the gate then tallied zero problems and
    exited 0: a green hard gate that verifies nothing, on exactly the tree
    it exists to police. So the reader raises `MatrixParseError`, naming the
    shape mismatch, and the gate fails closed.
    """
    images: list[dict] = []
    current: dict | None = None
    in_images = False
    saw_images_key = False
    entry_index = 0
    field_indent: int | None = None

    for raw in text.splitlines():
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        stripped = line.strip()

        if indent == 0:
            in_images = stripped.split(":", 1)[0].strip() == "images"
            saw_images_key = saw_images_key or in_images
            current = None
            field_indent = None
            continue
        if not in_images:
            continue

        if stripped.startswith("- "):
            current = {}
            images.append(current)
            entry_index += 1
            field_indent = None
            body = stripped[2:].strip()
        elif stripped == "-":
            current = {}
            images.append(current)
            entry_index += 1
            field_indent = None
            body = ""
        else:
            if current is None:
                continue
            if field_indent is None:
                field_indent = indent
            elif indent > field_indent:
                raise MatrixParseError(
                    f"images entry #{entry_index} has a nested block at indent "
                    f"{indent} -- this reader only understands flat mappings "
                    f"of scalars and refuses to guess at the shape"
                )
            body = stripped

        if body.startswith("{"):
            raise MatrixParseError(
                f"images entry #{entry_index} is a flow-style mapping "
                f"('{body}') -- this reader only understands block-style "
                f"`- key: value` entries and refuses to guess at the shape"
            )
        if not body:
            # A bare `-`: the fields, if any, are on the following lines.
            continue
        if ":" not in body:
            raise MatrixParseError(
                f"images entry #{entry_index} has no `key: value` field "
                f"('{body}') -- this reader only understands flat mappings of "
                f"scalars and refuses to guess at the shape"
            )
        key, _, value = body.partition(":")
        current[key.strip()] = _scalar(value)

    if not saw_images_key:
        raise MatrixParseError(
            "no top-level `images:` key found -- this reader only understands "
            "a matrix whose entries live under `images:`, and refuses to "
            "guess at a renamed or re-indented key"
        )
    if not images:
        raise MatrixParseError(
            "the `images:` list is empty -- there is nothing to check, and an "
            "empty matrix would make this gate green while verifying nothing"
        )
    for index, entry in enumerate(images, start=1):
        if not entry:
            raise MatrixParseError(
                f"images entry #{index} has no `key: value` field -- this "
                f"reader only understands flat mappings of scalars and "
                f"refuses to guess at the shape"
            )
    return images


def parse_submodule_paths(text: str) -> set[str]:
    """Return the submodule paths declared in a .gitmodules file."""
    paths: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("path"):
            continue
        key, sep, value = line.partition("=")
        if sep and key.strip() == "path":
            paths.add(value.strip())
    return paths


def parse_known_gaps(text: str) -> dict[str, str]:
    """Return {image name: reason} from the known-gaps baseline.

    The baseline is a flat `known_gaps:` mapping of image name to the reason
    the gap is accepted. Read with the same stdlib-only approach as the rest
    of this tool: the file is a flat mapping of scalars, and a reason may
    itself contain a colon, so the split is on the FIRST colon.
    """
    gaps: dict[str, str] = {}
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            in_section = line.rstrip(":") == "known_gaps"
            continue
        if not in_section or ":" not in line:
            continue
        name, _, reason = line.partition(":")
        name = name.strip().strip('"').strip("'")
        reason = reason.strip().strip('"').strip("'")
        if name:
            gaps[name] = reason
    return gaps


def parse_workflow_triggers(text: str) -> tuple[set[str], str | None]:
    """Return (trigger names, error) for a workflow's top-level `on:` block.

    Only the DIRECT children of `on:` are triggers. This matters: the
    `push: true` inside the build-push-action `with:` block is the buildx
    `--push` flag, not a workflow trigger, and reading the whole file for
    "push:" would report a manual-only workflow as automated.
    """
    lines = text.splitlines()
    start = None
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if len(raw) - len(raw.lstrip(" \t")) != 0:
            continue
        if stripped.split(":", 1)[0].strip() in ("on", '"on"', "'on'"):
            start = idx
            inline = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if inline:
                if inline.startswith("[") and inline.endswith("]"):
                    names = {
                        n.strip().strip("'\"")
                        for n in inline[1:-1].split(",")
                        if n.strip()
                    }
                    return names, None
                if inline.startswith("{") and inline.endswith("}"):
                    names = set()
                    depth = 0
                    key = ""
                    for ch in inline[1:-1]:
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        if depth == 0 and ch == ":":
                            names.add(key.strip().strip("'\""))
                            key = ""
                        else:
                            key += ch
                    return names, None
                return set(), f"cannot parse inline `on: {inline}`"
            break
    if start is None:
        return set(), "no top-level `on:` block found in the workflow"

    block: list[tuple[int, str]] = []
    for raw in lines[start + 1 :]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" \t"))
        if indent == 0:
            break
        block.append((indent, stripped))

    if not block:
        return set(), "the `on:` block is empty"

    child_indent = min(indent for indent, _ in block)
    triggers = {
        stripped.split(":", 1)[0].strip()
        for indent, stripped in block
        if indent == child_indent
    }
    triggers.discard("")
    return triggers, None


# --------------------------------------------------------------------------
# probes
# --------------------------------------------------------------------------
class _Context:
    """Everything the probes read, resolved once."""

    def __init__(
        self,
        repo_root: Path,
        submodule_paths: set[str],
        triggers: set[str],
        trigger_error: str | None,
    ) -> None:
        self.repo_root = repo_root
        self.submodule_paths = submodule_paths
        self.triggers = triggers
        self.trigger_error = trigger_error


def _is_submodule(repo: str, submodule_paths: set[str]) -> bool:
    if repo in submodule_paths:
        return True
    folded = repo.casefold()
    return any(p.casefold() == folded for p in submodule_paths)


def _submodule_checked_out(path: Path) -> bool:
    """A checked-out submodule directory has content; an uninitialised one
    is present but empty."""
    if not path.is_dir():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return False


def resolve_build_paths(image: dict, ctx: _Context) -> tuple[Path, Path, Path]:
    """Return (base_dir, context_dir, dockerfile_path) for a matrix entry.

    Mirrors `.github/workflows/build-images.yml` LITERALLY:
      context: ${{ matrix.repo && format('{0}/{1}{2}', github.workspace, matrix.repo, matrix.build_context && format('/{0}', matrix.build_context) || '') || matrix.context }}
      file:    ${{ matrix.dockerfile || 'Dockerfile' }}

    `repo:` is the DISCRIMINATOR and `context` is the fallback. This mirror
    used to have it the other way round -- `matrix.context || format(...)` --
    and because every repo-backed entry sets `context: .`, and a dot is
    TRUTHY in a GitHub Actions expression, the old mirror resolved those
    entries against the SUBMODULE while the real build resolved them against
    the WORKSPACE ROOT. The ratchet would then verify a submodule
    Dockerfile that the build never used, and the file the build actually
    asked for was never checked at all. The workflow has been corrected to
    match the intent; this mirror now follows the workflow exactly.

    `build_context` is RELATIVE TO THE REPO ROOT and applies ONLY to a
    repo-backed entry -- the workflow's expression reads it inside the
    `matrix.repo &&` branch, so for an in-tree entry it is dead input and
    this mirror ignores it too (a mirror that honoured it where the build
    does not would be a mirror that lies).

    `file` is RELATIVE in the workflow, so the build action resolves it
    against the CONTEXT. The mirror does the same, which is why there is
    exactly ONE candidate path here: a ratchet that tries several readings
    and accepts whichever matches is a ratchet that can verify a file the
    build would never open.
    """
    repo = str(image.get("repo", "") or "").strip()
    context_rel = str(image.get("context", "") or "").strip()
    build_context_rel = str(image.get("build_context", "") or "").strip()
    dockerfile_rel = str(image.get("dockerfile", "") or "").strip() or "Dockerfile"

    if repo:
        base = ctx.repo_root / repo
        context_dir = base / build_context_rel if build_context_rel else base
    else:
        base = ctx.repo_root
        context_dir = base / context_rel if context_rel else base

    dockerfile = context_dir / dockerfile_rel
    return base, context_dir, dockerfile


def probe_matrix_fields(image: dict, ctx: _Context) -> tuple[str, str]:
    """The entry declares every field this ratchet requires.

    POLICY, not a description of the builder's reads. The builder never
    reads `image` (the tag comes from `${{ matrix.name }}`) and treats
    `context` as a fallback, so requiring either would make law of a DEAD
    FIELD. The thing a dead `context` actually breaks has its own probe
    (`dead_context`), which states the rule precisely instead of being
    smuggled in as a required field.
    """
    missing = [
        field
        for field in REQUIRED_FIELDS
        if not str(image.get(field, "") or "").strip()
    ]
    if missing:
        return DRIFTED, (
            f"entry is missing required field(s): {', '.join(missing)} "
            f"(required by this ratchet: {', '.join(REQUIRED_FIELDS)})"
        )
    return VERIFIED, (
        f"entry declares every required field: {', '.join(REQUIRED_FIELDS)}"
    )


def probe_build_inputs(image: dict, ctx: _Context) -> tuple[str, str]:
    """The build context and dockerfile the matrix names exist in the tree."""
    name = str(image.get("name", "<unnamed>"))
    repo = str(image.get("repo", "") or "").strip()
    dockerfile_rel = str(image.get("dockerfile", "") or "").strip()
    if not dockerfile_rel:
        return DRIFTED, "no `dockerfile` path to resolve"

    base, context_dir, dockerfile = resolve_build_paths(image, ctx)

    # ONE candidate: the path the build action will actually open. The old
    # version also tried the "build root" reading and accepted whichever
    # matched, which is how a repo-backed entry could be VERIFIED against a
    # file the build never reads.
    candidates = [dockerfile]

    for candidate in candidates:
        if candidate.is_file():
            try:
                shown = candidate.relative_to(ctx.repo_root).as_posix()
            except ValueError:
                shown = candidate.as_posix()
            return VERIFIED, f"build input present: {shown} (relative to the build context)"

    if repo:
        sub_path = ctx.repo_root / repo
        if _is_submodule(repo, ctx.submodule_paths) and not _submodule_checked_out(sub_path):
            return UNDECIDED, (
                f"submodule '{repo}' is declared in .gitmodules but not checked out "
                f"in this tree -- cannot resolve dockerfile '{dockerfile_rel}' "
                f"(not a broken image; init the submodule to decide it)"
            )

    tried = ", ".join(
        c.as_posix() for c in candidates
    )
    return DRIFTED, (
        f"build input missing for '{name}': tried {tried} "
        f"(context '{context_dir.as_posix()}')"
    )


def probe_build_path(image: dict, ctx: _Context) -> tuple[str, str]:
    """The image's builder has a trigger that does not need a human."""
    if ctx.trigger_error:
        # NOT UNDECIDED. UNDECIDED is the house answer for an uninitialised
        # SUBMODULE -- a question this tree cannot answer. This is the
        # gate's OWN probe gagging, which is not submodule-dependent: the
        # trigger is right there in the workflow file. The rebuild path is
        # UNMEASURED, not clean, so the claim gets its own failing class and
        # the gate fails closed on it.
        return INSTRUMENT_ERROR, (
            f"the gate's own probe could not read the build workflow's "
            f"triggers: {ctx.trigger_error} -- the rebuild path is UNMEASURED, "
            f"not clean, so this fails the gate"
        )
    non_manual = sorted(t for t in ctx.triggers if t in NON_MANUAL_TRIGGERS)
    if non_manual:
        return VERIFIED, (
            f"build workflow declares non-manual trigger(s): {', '.join(non_manual)} "
            f"(all triggers: {', '.join(sorted(ctx.triggers))})"
        )
    all_triggers = ", ".join(sorted(ctx.triggers)) or "none"
    return DRIFTED, (
        f"build workflow triggers = {all_triggers} -- no push/schedule/"
        f"repository_dispatch, so the fleet only rebuilds when a human clicks"
    )


def probe_dead_context(image: dict, ctx: _Context) -> tuple[str, str]:
    """A repo-backed entry must not declare a `context` the build IGNORES.

    The workflow resolves the build context as
      ${{ matrix.repo && format('{0}/{1}', github.workspace, matrix.repo) || matrix.context }}
    so `repo:` is the DISCRIMINATOR and `context` is only the fallback. For
    a repo-backed entry the build ALWAYS uses the repo root, which means a
    declared `context` is DEAD build input -- and dead build input is where
    a silently changed behaviour hides (the matrix says one thing, the build
    does another). The lane's own matrix had exactly one such entry:
    `pmoves-tokenism-ui` used to declare `context: pmoves-nextjs` on top of
    `repo: PMOVES-ToKenism-Multi`, and that declaration was ignored. The dead
    declaration was DROPPED in the same lane, so the matrix this gate
    polices today has ZERO such entries -- and this probe fails any entry
    that declares one again.

    The verdict is DRIFTED only where the tool can MEASURE the mismatch: it
    has to be able to look inside the repo the build actually uses. Where
    that repo is a submodule that is not checked out here, the tool cannot
    look, so the claim is UNDECIDED -- "could not check" -- never VERIFIED,
    and never a false DRIFTED on a tree that simply has no submodules.
    """
    name = str(image.get("name", "<unnamed>"))
    repo = str(image.get("repo", "") or "").strip()
    context_rel = str(image.get("context", "") or "").strip()
    build_context_rel = str(image.get("build_context", "") or "").strip()

    if not repo:
        if build_context_rel:
            # `build_context` is read INSIDE the workflow's `matrix.repo &&`
            # branch, so for an entry with no `repo:` it is never read.
            return DRIFTED, (
                f"entry '{name}' declares build_context '{build_context_rel}', "
                f"but the build reads `build_context` only for a repo-backed "
                f"entry: this entry has no `repo:`, so the declaration is dead "
                f"build input"
            )
        return VERIFIED, (
            "entry declares no `repo:`, so the build resolves the declared "
            "`context` and the declaration is honoured"
        )
    if not context_rel or context_rel == ".":
        return VERIFIED, (
            f"repo-backed entry declares context '{context_rel or '.'}', which "
            f"is what the build resolves for a repo-backed entry"
        )

    # A non-`.` context on a repo-backed entry is dead build input.
    ignored = (
        f"repo-backed entry '{name}' declares context '{context_rel}', but the "
        f"build IGNORES `context` for a repo-backed entry: it resolves "
        f"'{repo}' (the repo root). The declared context is dead build input"
    )
    if _submodule_checked_out(ctx.repo_root / repo):
        return DRIFTED, ignored
    return UNDECIDED, (
        f"{ignored}, and the effective path inside '{repo}' cannot be measured "
        f"here (that repo is not checked out in this tree)"
    )


_COPY_RE = re.compile(r"^\s*(COPY|ADD)\s+(.*)$", re.IGNORECASE)

# A REMOTE source: docker FETCHES it over the network.
_URL_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*://|git@)", re.IGNORECASE)

# `ADD <url> <sha256:...> <dest>` carries a CHECKSUM between the URL and the
# destination. The checksum is not a path either.
_CHECKSUM_RE = re.compile(r"^(?:sha256:[0-9a-f]{64}|[0-9a-f]{64})$", re.IGNORECASE)


def _logical_instructions(text: str) -> list[str]:
    """Return the LOGICAL instructions of a Dockerfile, continuations joined.

    A Dockerfile instruction may be continued with a trailing backslash -- the
    standard form for a multi-source copy:

        COPY requirements.txt \\
             package.json ./

    A reader that iterates PHYSICAL lines sees only ``COPY requirements.txt \\``:
    the trailing backslash becomes a token and the SECOND source is dropped.
    That is a FALSE NEGATIVE in the dangerous direction -- the build needs
    ``package.json`` and the probe never checks it.

    MEASURED 2026-11-01: the probe iterated physical lines. Docker strips
    COMMENT lines before it parses instructions, so a comment inside a
    continuation is dropped here too.
    """
    instructions: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        if raw.strip().startswith("#"):
            # Docker strips comments before parsing; a comment line inside a
            # continuation neither ends it nor contributes to it.
            continue
        body = raw.rstrip()
        if body.endswith("\\"):
            buffer += body[:-1] + " "
            continue
        buffer += raw
        instructions.append(buffer)
        buffer = ""
    if buffer:
        instructions.append(buffer)
    return instructions


def _dockerfile_context_sources(text: str) -> list[list[str]]:
    """Return the BUILD-CONTEXT sources of every COPY/ADD line.

    Three kinds of COPY are NOT build-context sources and are skipped:

      * `COPY --from=build /app/build /out` copies from another stage's
        filesystem, not from the context.
      * `COPY <<EOF /dest` has no path source at all -- the body is a
        heredoc.
      * `ADD https://example.com/x.tar.gz /tmp/` FETCHES the URL over the
        network. Docker's `ADD` supports remote URLs precisely because it
        can download them; the build context does not have to contain
        them. (`COPY` does NOT support remote URLs -- docker rejects them
        outright -- so a URL in a `COPY` is still reported, because that
        build really does fail.)

    MEASURED 2026-11-01: the third rule was missing, and it produced a
    FALSE POSITIVE on `pmoves-remote-view`, whose authored Dockerfile adds
    the s6-overlay tarballs by URL. The probe reported DRIFTED for a
    Dockerfile that builds. A probe that cries wolf on a valid Dockerfile
    teaches the fleet to ignore it.

    The LAST word of the line is the destination, so every word before it
    is a source. Flags (`--chown=`, `--chmod=`, `--link=`) are not words.
    """
    groups: list[list[str]] = []
    for raw in _logical_instructions(text):
        stripped = raw.strip()
        if not stripped:
            continue
        match = _COPY_RE.match(raw)
        if not match:
            continue
        verb = match.group(1).upper()
        try:
            tokens = shlex.split(match.group(2), posix=True)
        except ValueError:
            tokens = match.group(2).split()
        flags = [t for t in tokens if t.startswith("--")]
        words = [t for t in tokens if not t.startswith("--")]
        if any(flag.startswith("--from=") for flag in flags):
            continue
        if any(word.startswith("<<") for word in words):
            continue
        if len(words) < 2:
            continue
        sources = words[:-1]
        if verb == "ADD":
            sources = [
                word
                for word in sources
                if not _URL_RE.match(word) and not _CHECKSUM_RE.match(word)
            ]
        groups.append(sources)
    return groups


def _source_resolves(source: str, context_dir: Path) -> bool:
    """Does `source` name something the build context actually contains?"""
    if source in (".", "./", ".."):
        # The whole context. Always present.
        return True
    if source.startswith("/"):
        # An absolute source is not a context path (docker resolves
        # context sources against the context root, never the host root).
        return True
    if any(ch in source for ch in "*?["):
        return _glob_resolves(source, context_dir)
    return (context_dir / source).exists()


def _glob_resolves(source: str, context_dir: Path) -> bool:
    """Does a WILDCARD source resolve to at least one file under the context?

    Docker expands a wildcard against the context, and the wildcard can be in
    ANY segment -- ``services/*/requirements.txt`` is the common form. The
    earlier implementation matched only the FINAL segment against the child
    NAMES of the directory above it, so a mid-path wildcard asked whether the
    literal path ``services/*`` was a directory (it is not) and reported a
    FALSE DRIFTED for a Dockerfile that builds.

    Resolution is per SEGMENT: descend through the fixed segments, expand each
    wildcard segment against the children of the directory reached so far, and
    require the final segment to match something. A wildcard that matches
    NOTHING is still a build that cannot succeed, so it is reported.
    """
    segments = [s for s in source.replace("\\", "/").split("/") if s not in ("", ".")]
    if not segments:
        return True
    current = [context_dir]
    for segment in segments[:-1]:
        expanded: list[Path] = []
        for base in current:
            if any(ch in segment for ch in "*?["):
                try:
                    children = list(base.iterdir())
                except OSError:
                    continue
                for child in children:
                    if fnmatch.fnmatch(child.name, segment) and child.is_dir():
                        expanded.append(child)
            else:
                candidate = base / segment
                if candidate.is_dir():
                    expanded.append(candidate)
        current = expanded
        if not current:
            return False
    leaf = segments[-1]
    for base in current:
        if any(ch in leaf for ch in "*?["):
            try:
                children = list(base.iterdir())
            except OSError:
                continue
            for child in children:
                if fnmatch.fnmatch(child.name, leaf):
                    return True
        elif (base / leaf).exists():
            return True
    return False


def probe_copy_sources(image: dict, ctx: _Context) -> tuple[str, str]:
    """Every COPY/ADD source in the resolved Dockerfile resolves.

    The `build_inputs` probe asks whether the Dockerfile FILE is there.
    This probe asks the NEXT question: whether that Dockerfile can actually
    be built from the context the workflow will hand the builder. A
    Dockerfile that says `COPY requirements.txt ./` is buildable only from a
    context that CONTAINS `requirements.txt`, and the build context is
    resolved from the matrix -- so the matrix has to say the same thing the
    Dockerfile assumes.
    """
    name = str(image.get("name", "<unnamed>"))
    repo = str(image.get("repo", "") or "").strip()
    dockerfile_rel = str(image.get("dockerfile", "") or "").strip() or "Dockerfile"
    base, context_dir, dockerfile = resolve_build_paths(image, ctx)

    if not dockerfile.is_file():
        if repo and _is_submodule(repo, ctx.submodule_paths) and not _submodule_checked_out(ctx.repo_root / repo):
            return UNDECIDED, (
                f"cannot resolve the COPY set for '{name}': submodule '{repo}' "
                f"is not checked out in this tree, so the Dockerfile "
                f"'{dockerfile_rel}' cannot be read"
            )
        # The Dockerfile is ABSENT. That absence is the `build_inputs`
        # probe's claim, and it is reported there with the full evidence.
        # Re-reporting it here as UNDECIDED would add a second, vaguer
        # claim about the same defect.
        return VERIFIED, (
            f"no COPY set to resolve for '{name}': the build input "
            f"'{dockerfile_rel}' is absent (reported by the `build_inputs` "
            f"probe), so there is no Dockerfile whose sources could fail to "
            f"resolve"
        )

    try:
        text = dockerfile.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return INSTRUMENT_ERROR, (
            f"could not read the Dockerfile for '{name}' at "
            f"'{dockerfile.as_posix()}': {exc} -- the COPY set is UNMEASURED, "
            f"not clean"
        )

    groups = _dockerfile_context_sources(text)
    if not groups:
        return VERIFIED, (
            f"the Dockerfile for '{name}' declares no COPY/ADD source that "
            f"comes from the build context"
        )

    unresolved: list[str] = []
    for sources in groups:
        for source in sources:
            if not _source_resolves(source, context_dir):
                unresolved.append(source)

    if unresolved:
        shown = ", ".join(f"'{s}'" for s in sorted(set(unresolved)))
        return DRIFTED, (
            f"the COPY set of '{name}' does not resolve against its build "
            f"context '{context_dir.as_posix()}': {shown}. The build would "
            f"fail with 'not found' -- the Dockerfile exists, but the "
            f"context the matrix declares does not contain what it copies"
        )
    return VERIFIED, (
        f"every COPY/ADD source of '{name}' resolves against the build "
        f"context '{context_dir.as_posix()}'"
    )


PROBES = {
    "matrix_fields": probe_matrix_fields,
    "build_inputs": probe_build_inputs,
    "build_path": probe_build_path,
    "dead_context": probe_dead_context,
    "copy_sources": probe_copy_sources,
}


def _worst(verdicts: list[str]) -> str:
    if DRIFTED in verdicts:
        return DRIFTED
    if KNOWN_GAP in verdicts:
        return KNOWN_GAP
    if UNDECIDED in verdicts or INSTRUMENT_ERROR in verdicts:
        # An INSTRUMENT_ERROR is UNMEASURED, not broken: the image is not
        # proven bad, so the row is UNDECIDED. The gate still FAILS on it --
        # see the `errors` list in the payload.
        return UNDECIDED
    return VERIFIED


def audit(
    repo_root: Path,
    images_path: Path,
    workflow_path: Path,
    gitmodules_path: Path,
    known_gaps: dict[str, str] | None = None,
) -> dict:
    """Run every probe over every matrix entry and return the payload."""
    known_gaps = known_gaps or {}
    images = parse_images_matrix(images_path.read_text(encoding="utf-8"))
    triggers, trigger_error = parse_workflow_triggers(
        workflow_path.read_text(encoding="utf-8")
    )
    submodule_paths: set[str] = set()
    if gitmodules_path.is_file():
        submodule_paths = parse_submodule_paths(
            gitmodules_path.read_text(encoding="utf-8")
        )

    ctx = _Context(repo_root, submodule_paths, triggers, trigger_error)

    claims: list[dict] = []
    rows: list[dict] = []
    for image in images:
        name = str(image.get("name", "<unnamed>"))
        verdicts: list[str] = []
        for probe_name, probe in PROBES.items():
            verdict, evidence = probe(image, ctx)
            # The baseline covers ONE probe: the build input that is absent.
            # A gap in any other probe (a missing builder field, a
            # manual-only rebuild path) is a live defect and stays DRIFTED.
            if (
                verdict == DRIFTED
                and probe_name == "build_inputs"
                and name in known_gaps
            ):
                verdict = KNOWN_GAP
                evidence = (
                    f"{evidence} -- KNOWN GAP, baselined: {known_gaps[name]}"
                )
            verdicts.append(verdict)
            claims.append(
                {
                    "image": name,
                    "probe": probe_name,
                    "verdict": verdict,
                    "evidence": evidence,
                }
            )
        rows.append({"name": name, "verdict": _worst(verdicts)})

    counts = {VERIFIED: 0, DRIFTED: 0, UNDECIDED: 0, KNOWN_GAP: 0}
    for row in rows:
        counts[row["verdict"]] += 1

    problems = [
        f"{claim['image']}: {claim['probe']}: {claim['evidence']}"
        for claim in claims
        if claim["verdict"] == DRIFTED
    ]
    # UNDECIDED and INSTRUMENT_ERROR are both "not VERIFIED", so both land
    # here; the claim's own verdict says WHICH. An instrument error is not
    # a submodule question -- it is the gate's own probe failing -- and it
    # fails the gate (see `errors`), it is not quietly tolerated.
    undecided = [
        {"image": claim["image"], "probe": claim["probe"], "evidence": claim["evidence"]}
        for claim in claims
        if claim["verdict"] in (UNDECIDED, INSTRUMENT_ERROR)
    ]
    errors = [
        {
            "image": claim["image"],
            "probe": claim["probe"],
            "evidence": claim["evidence"],
            "verdict": INSTRUMENT_ERROR,
        }
        for claim in claims
        if claim["verdict"] == INSTRUMENT_ERROR
    ]
    known_gaps_found = [
        {
            "image": claim["image"],
            "probe": claim["probe"],
            "evidence": claim["evidence"],
            "reason": known_gaps.get(claim["image"], ""),
        }
        for claim in claims
        if claim["verdict"] == KNOWN_GAP
    ]
    # A baselined gap that no longer occurs is STALE: the defect was fixed
    # and the baseline still says it is there. The house's
    # `validate_command_anchors.py` gate fails for exactly this reason --
    # "drop them so the same defect cannot return silently".
    #
    # The staleness is judged on the BUILD INPUTS probe specifically. Every
    # image has a VERIFIED `matrix_fields` claim, so "any VERIFIED claim"
    # would mark every baselined entry stale the moment it was looked at.
    stale_gaps = [
        name
        for name in known_gaps
        if any(
            claim["image"] == name
            and claim["probe"] == "build_inputs"
            and claim["verdict"] == VERIFIED
            for claim in claims
        )
    ]
    # The stale check is ONE-DIRECTIONAL: it catches a gap that got FIXED.
    # A baseline name whose image was REMOVED or RENAMED in the matrix
    # produces no claims at all -- not DRIFTED, not VERIFIED, not even
    # UNDECIDED, ABSENT -- so it matches nothing, fails nothing and reports
    # nothing, and haunts the baseline forever. That is the other half of
    # the same contract: a baseline may not outlive the matrix entry it
    # describes, so an orphaned entry is reported AND fails the gate.
    measured_images = {
        claim["image"] for claim in claims if claim["probe"] == "build_inputs"
    }
    orphan_gaps = [name for name in known_gaps if name not in measured_images]

    return {
        "images_matrix": images_path.as_posix(),
        "workflow": workflow_path.as_posix(),
        "gitmodules": gitmodules_path.as_posix(),
        "repo_root": repo_root.as_posix(),
        "total": len(images),
        "counts": counts,
        "triggers": sorted(triggers),
        "problems": problems,
        "undecided": undecided,
        "known_gaps": known_gaps_found,
        "stale_gaps": stale_gaps,
        "orphan_gaps": orphan_gaps,
        "errors": errors,
        "claims": claims,
        "images": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        default=IMAGES_PATH,
        help=f"Path to the image build matrix (default: {IMAGES_PATH})",
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=WORKFLOW_PATH,
        help=f"Path to the image build workflow (default: {WORKFLOW_PATH})",
    )
    parser.add_argument(
        "--gitmodules",
        type=Path,
        default=GITMODULES_PATH,
        help=f"Path to .gitmodules for the submodule cross-check (default: {GITMODULES_PATH})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=f"Root the matrix paths resolve against (default: {REPO_ROOT})",
    )
    parser.add_argument(
        "--known-gaps",
        type=Path,
        default=KNOWN_GAPS_PATH,
        help=(
            "Baseline of images whose declared build input is absent "
            f"(default: {KNOWN_GAPS_PATH})"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    args = parser.parse_args()

    for label, path in (
        ("image matrix", args.images),
        ("build workflow", args.workflow),
    ):
        if not path.is_file():
            print(f"{label} not found: {path}", file=sys.stderr)
            return 2

    known_gaps: dict[str, str] = {}
    if args.known_gaps.is_file():
        known_gaps = parse_known_gaps(args.known_gaps.read_text(encoding="utf-8"))

    try:
        payload = audit(
            args.repo_root, args.images, args.workflow, args.gitmodules, known_gaps
        )
    except MatrixParseError as exc:
        # FAIL CLOSED. The reader could not understand the matrix, so there
        # is nothing to verify -- and a gate that verifies nothing must not
        # report success. Exit 2 (an instrument/setup failure, like a missing
        # file), never 0.
        message = f"image-staleness ratchet: cannot read the image matrix: {exc}"
        if args.json:
            # Keep the payload contract intact for the CI consumer: the same
            # keys, the same shapes, with the failure in `problems`.
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "total": 0,
                        "counts": {VERIFIED: 0, DRIFTED: 0, UNDECIDED: 0, KNOWN_GAP: 0},
                        "triggers": [],
                        "problems": [str(exc)],
                        "undecided": [],
                        "known_gaps": [],
                        "stale_gaps": [],
                        "orphan_gaps": [],
                        "errors": [
                            {
                                "image": "<matrix>",
                                "probe": "matrix_parse",
                                "evidence": str(exc),
                                "verdict": INSTRUMENT_ERROR,
                            }
                        ],
                        "claims": [],
                        "images": [],
                    },
                    indent=2,
                )
            )
        print(message, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        counts = payload["counts"]
        print(
            f"image-staleness ratchet: {payload['total']} image(s) - "
            f"{counts[VERIFIED]} verified, {counts[DRIFTED]} drifted, "
            f"{counts[UNDECIDED]} undecided, {counts[KNOWN_GAP]} known-gap"
        )
        print(
            f"  build path: triggers = {', '.join(payload['triggers']) or 'none'}"
        )
        for row in payload["images"]:
            print(f"  {row['name']:<38} {row['verdict']}")
        if payload["problems"]:
            print(f"  {len(payload['problems'])} problem(s):")
            for problem in payload["problems"]:
                print(f"    - {problem}")
        else:
            print("  (every image declares its build fields, resolves its build")
            print("   inputs, and has a non-manual rebuild trigger)")
        if payload["known_gaps"]:
            print(
                f"  {len(payload['known_gaps'])} KNOWN GAP(s) -- the build input "
                f"is absent and the gap is baselined:"
            )
            for item in payload["known_gaps"]:
                print(f"    - {item['image']}: {item['reason']}")
        if payload["undecided"]:
            print(
                f"  {len(payload['undecided'])} undecided (not failed on their own):"
            )
            for item in payload["undecided"]:
                print(f"    - {item['image']}: {item['evidence']}")
        if payload["errors"]:
            print(
                f"  {len(payload['errors'])} INSTRUMENT ERROR(s) -- the gate could "
                f"not measure these, and the gate FAILS on them:"
            )
            for item in payload["errors"]:
                print(f"    - {item['image']}: {item['probe']}: {item['evidence']}")
        if payload["stale_gaps"]:
            print(
                f"  {len(payload['stale_gaps'])} STALE baseline entr(ies) -- the "
                f"gap is fixed; drop them so it cannot return silently:"
            )
            for name in payload["stale_gaps"]:
                print(f"    - {name}")
        if payload["orphan_gaps"]:
            print(
                f"  {len(payload['orphan_gaps'])} ORPHANED baseline entr(ies) -- "
                f"the image is not in the matrix any more; drop them so the "
                f"baseline cannot outlive the matrix:"
            )
            for name in payload["orphan_gaps"]:
                print(f"    - {name}")

    # DRIFTED fails the gate. UNDECIDED does NOT: a submodule that is not
    # checked out here is an unanswered question, not a broken image, and a
    # CI runner without submodules must not go permanently red.
    #
    # A STALE baseline entry fails too: the defect it recorded has been
    # fixed, and leaving it in the baseline would let it come back unnoticed.
    # So does an ORPHANED one: the image it describes is gone from the
    # matrix, and the baseline must not outlive it.
    #
    # So does an INSTRUMENT ERROR: the gate's own probe could not measure,
    # and a gate that cannot measure fails closed.
    return (
        1
        if (
            payload["problems"]
            or payload["stale_gaps"]
            or payload["orphan_gaps"]
            or payload["errors"]
        )
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
