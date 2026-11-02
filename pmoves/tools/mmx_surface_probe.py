#!/usr/bin/env python3
"""Probe the installed ``mmx`` CLI and snapshot its command surface.

WHY THIS EXISTS
---------------
``pmoves/docs/services/MMX_CLI_SURFACE.md`` is a promise: it tells a sidecar
which ``mmx`` invocations exist. A promise that names a command the CLI does not
have is worse than no promise -- the caller gets a non-zero exit at run time,
on a device, with a half-written output file.

The doc drifted. It was written against the ``Pmoves-minimax-cli`` submodule
(and an older npm build), and the installed npm build has since moved:
resources were added (``agent``), commands were renamed
(``speech list-voices`` -> ``speech voices``), a resource was dropped
(``music``), and the version moved on.

So the surface is now MEASURED, not remembered. This tool reads the installed
CLI's own ``--help`` output and writes a deterministic snapshot:

    pmoves/configs/mmx_surface/cli_surface.json

``pmoves/tools/mmx_surface_parity.py`` then holds the doc against that
snapshot, so the two cannot drift apart again without the gate going red.

WHAT IT RUNS (and what it never runs)
-------------------------------------
Only ``--version`` and ``--help``. Never ``auth login``, never a model call,
never anything that reaches the network or the API. The surface is a property
of the binary, not of the account, so the probe needs no credentials and makes
no request.

FAIL CLOSED
-----------
A missing binary, an unexecutable binary, a non-zero ``--help`` exit, an
unparseable help page, a resource whose help cannot be read: every one of
these aborts the probe with a non-zero exit and writes NOTHING. A partial
snapshot that looks like truth is worse than no snapshot at all, because the
parity gate would then compare the doc against a hole.

DETERMINISM
-----------
The snapshot is sorted at every level and serialised with ``sort_keys=True``,
so re-running the probe against the same binary produces byte-identical
output. A CI job can therefore ``diff`` a fresh probe against the committed
snapshot and expect no difference.

Exit codes: 0 snapshot written | 1 the surface could not be measured.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = REPO_ROOT / "pmoves" / "configs" / "mmx_surface" / "cli_surface.json"

#: Bumped when the snapshot's shape changes in a way a consumer must notice.
SURFACE_SCHEMA = "pmoves.mmx-cli-surface/v1"

#: CSI escape sequences. The CLI colourises its help output when it believes
#: it is attached to a terminal; a colourised help page must not turn into
#: colourised resource names.
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")

#: A command word in this CLI is lowercase, optionally hyphenated.
COMMAND_WORD_RE = re.compile(r"^[a-z][a-z0-9-]*$")

HELP_TIMEOUT_SECONDS = 60

#: The only argument shapes this probe is ever allowed to execute. Anything
#: else is a bug in the probe, and a bug here would run a model call.
def _is_allowed_shape(args: list[str]) -> bool:
    if args in (["--version"], ["--help"]):
        return True
    return len(args) == 2 and args[1] == "--help"


class ProbeError(RuntimeError):
    """The surface could not be measured.

    Raised instead of returning a partial result. The caller turns this into a
    non-zero exit and writes no snapshot.
    """


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from CLI output."""
    return ANSI_RE.sub("", text)


def resolve_mmx(explicit: str | None = None) -> str:
    """Return the path to the ``mmx`` executable.

    Resolution order:

    1. ``explicit`` (``--mmx-bin``) -- an explicit request wins over anything
       found on ``PATH``; it may be a path or a bare command name.
    2. ``shutil.which("mmx")`` -- on Windows this resolves through ``PATHEXT``
       to the npm shim (``mmx.cmd``/``mmx.CMD``); on POSIX it resolves to the
       ``bin/mmx`` symlink.
    3. the ``mmx.cmd`` / ``mmx.ps1`` variants, for hosts whose ``PATHEXT`` does
       not cover them.
    """
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return str(candidate)
        found = shutil.which(explicit)
        if found:
            return found
        raise ProbeError(
            f"--mmx-bin {explicit!r} is neither an existing file nor a command on PATH"
        )

    for name in ("mmx", "mmx.cmd", "mmx.ps1"):
        found = shutil.which(name)
        if found:
            return found

    raise ProbeError(
        "the mmx CLI was not found on PATH. Install it with "
        "`npm install -g mmx-cli`, or point the probe at it with --mmx-bin."
    )


def _argv(exe: str, args: list[str]) -> list[str]:
    """Build the argv for one invocation, handling the Windows PowerShell shim."""
    if exe.lower().endswith(".ps1"):
        return [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            exe,
            *args,
        ]
    return [exe, *args]


def _assert_offline_args(args: list[str]) -> None:
    """Refuse to run anything that is not a help or version request."""
    if not _is_allowed_shape(args):
        raise ProbeError(
            f"refusing to run `mmx {' '.join(args)}`: the probe may only run --version, "
            "--help and `<resource> --help`"
        )


def run_mmx(exe: str, args: list[str]) -> str:
    """Run one ``mmx`` help/version invocation and return its stripped output."""
    _assert_offline_args(args)
    argv = _argv(exe, args)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HELP_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        # OSError covers a MISSING binary (FileNotFoundError) AND a binary
        # that cannot be EXECUTED: PermissionError on POSIX, and the Windows
        # "not a valid Win32 application" / "access denied" errors. Both are
        # ProbeError, not a raw traceback: a missing binary gets a loving
        # error message, and so does an unexecutable one.
        raise ProbeError(f"could not execute {exe!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(
            f"`mmx {' '.join(args)}` did not finish within {HELP_TIMEOUT_SECONDS}s"
        ) from exc

    if proc.returncode != 0:
        detail = strip_ansi(proc.stderr or proc.stdout or "").strip()
        raise ProbeError(
            f"`mmx {' '.join(args)}` exited {proc.returncode}"
            + (f": {detail.splitlines()[0]}" if detail else "")
        )

    stdout_text = strip_ansi(proc.stdout or "")
    stderr_text = strip_ansi(proc.stderr or "")
    output = stdout_text if stdout_text.strip() else stderr_text
    if not output.strip():
        raise ProbeError(f"`mmx {' '.join(args)}` produced no output")
    return output


def parse_version(text: str) -> str:
    """Pull the ``X.Y.Z`` version out of ``mmx --version`` output."""
    match = VERSION_RE.search(text)
    if not match:
        raise ProbeError(f"could not find a version in the --version output: {text.strip()!r}")
    return match.group(1)


def parse_resources(top_help: str) -> list[str]:
    """Return the resource names from the top-level help's ``Resources:`` block.

    The CLI owns this list; the probe does not invent it. A resource line is
    two-space indented, a name, then two-or-more spaces and a description.
    The block ends at the first line that does not look like a resource line.
    """
    lines = top_help.splitlines()
    try:
        start = lines.index("Resources:")
    except ValueError:
        raise ProbeError("the top-level help has no 'Resources:' section") from None

    resources: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        match = re.match(r"^ {2}(\S+)\s{2,}(\S.*)$", line)
        if not match:
            break
        resources.append(match.group(1))

    if not resources:
        raise ProbeError("no resources could be parsed from the top-level help")
    return resources


def parse_global_flags(top_help: str) -> list[str]:
    """Return the global flag names from the top-level help's ``Global Flags:`` block."""
    lines = top_help.splitlines()
    try:
        start = lines.index("Global Flags:")
    except ValueError:
        raise ProbeError("the top-level help has no 'Global Flags:' section") from None

    flags: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        match = re.match(r"^ {2}(--[A-Za-z0-9][A-Za-z0-9-]*)", line)
        if not match:
            break
        flags.append(match.group(1))

    if not flags:
        raise ProbeError("no global flags could be parsed from the top-level help")
    return flags


def parse_commands(resource: str, resource_help: str) -> list[str]:
    """Return the command names a resource exposes.

    Two shapes are handled, because the CLI uses two:

    * a ``Commands:`` block, whose rows are
      ``<resource> <command...>  <description>`` separated by two-or-more
      spaces. The command may be more than one word (``video task get``), so
      the command path is read as the leading run of lowercase words that
      follows the resource name -- the description is not a command.
    * a resource with no ``Commands:`` block at all (``agent``, ``update``),
      where the command is on the ``Usage:`` line.

    Rows whose leading word is not the resource name are NOT commands. That is
    what keeps ``video``'s model legend (``V2:``, ``T2V:``, ``I2V:``, ``SEF:``,
    ``S2V:``) out of the snapshot.
    """
    lines = resource_help.splitlines()

    commands: list[str] = []
    in_commands = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Commands:":
            in_commands = True
            continue
        if not in_commands:
            continue
        if not stripped:
            break
        parts = re.split(r"\s{2,}", stripped)
        head = parts[0].split()
        if not head or head[0] != resource:
            # Not a command row for this resource (e.g. the video model legend).
            continue
        words = _leading_command_words(head[1:])
        if words:
            commands.append(" ".join(words))

    if commands:
        return sorted(set(commands))

    # No Commands: block -- read the command off the Usage: line.
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("Usage:"):
            continue
        tokens = stripped.split()
        if len(tokens) >= 3 and tokens[1] == "mmx" and tokens[2] == resource:
            words = _leading_command_words(tokens[3:])
            return [" ".join(words)] if words else []
        break

    raise ProbeError(
        f"the help for resource {resource!r} has neither a 'Commands:' section "
        "nor a 'Usage:' line"
    )


def _leading_command_words(tokens: list[str]) -> list[str]:
    """Return the leading run of tokens that look like command words."""
    words: list[str] = []
    for token in tokens:
        if not COMMAND_WORD_RE.match(token):
            break
        words.append(token)
    return words


def build_snapshot(exe: str) -> dict:
    """Measure the installed CLI and return the snapshot structure."""
    version = parse_version(run_mmx(exe, ["--version"]))
    top_help = run_mmx(exe, ["--help"])

    resources = parse_resources(top_help)
    global_flags = parse_global_flags(top_help)

    commands: dict[str, list[str]] = {}
    for resource in resources:
        resource_help = run_mmx(exe, [resource, "--help"])
        commands[resource] = parse_commands(resource, resource_help)

    return {
        "schema": SURFACE_SCHEMA,
        "mmx_version": version,
        "resources": {name: sorted(set(commands[name])) for name in sorted(commands)},
        "global_flags": sorted(set(global_flags)),
    }


def write_snapshot(path: Path, snapshot: dict) -> None:
    """Write the snapshot deterministically (sorted keys, LF endings)."""
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe the installed mmx CLI and snapshot its command surface."
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_SNAPSHOT),
        help="where to write the snapshot (default: %(default)s)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the snapshot to stdout instead of writing it to a file",
    )
    parser.add_argument(
        "--mmx-bin",
        default=None,
        help="path to the mmx executable (default: resolved from PATH)",
    )
    args = parser.parse_args(argv)

    try:
        exe = resolve_mmx(args.mmx_bin)
        snapshot = build_snapshot(exe)
    except ProbeError as exc:
        print(f"mmx-surface-probe: FAILED: {exc}", file=sys.stderr)
        return 1

    if args.stdout:
        sys.stdout.write(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    else:
        out_path = Path(args.out)
        write_snapshot(out_path, snapshot)
        print(
            f"mmx-surface-probe: wrote {out_path} "
            f"(mmx {snapshot['mmx_version']}, "
            f"{len(snapshot['resources'])} resources)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
