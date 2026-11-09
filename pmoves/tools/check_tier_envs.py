#!/usr/bin/env python3
"""Cross-platform validation for tiered env files.

Checks:
1. All expected tier files exist (or have .example counterparts).
2. DRIFT detection: keys in .example but missing from runtime tier files.
   This catches the exact class of bug where secrets_sync.py generates a tier
   file but omits keys that the .example says should be present.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path


TIERS = ("data", "supabase", "api", "llm", "worker", "media", "agent", "ui")


def parse_env_keys(path: Path) -> set[str]:
    """Extract variable names from a dotenv-style file."""
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def check_existence() -> list[str]:
    """Check that all tier env files exist. Return list of hard-missing tiers."""
    missing_hard: list[str] = []
    for tier in TIERS:
        env_file = Path(f"env.tier-{tier}")
        example = Path(f"env.tier-{tier}.example")
        if env_file.exists():
            continue
        if example.exists():
            print(f"WARN: {env_file} missing (example exists)")
            print("   Fix: run 'make bootstrap-tier-envs' or 'make secrets-funnel'")
        else:
            print(f"ERROR: {env_file} missing (no example found)")
            missing_hard.append(str(env_file))
    return missing_hard


def check_drift() -> list[str]:
    """Compare .example keys against runtime tier files. Return drift warnings."""
    drift: list[str] = []
    for tier in TIERS:
        env_file = Path(f"env.tier-{tier}")
        example = Path(f"env.tier-{tier}.example")
        if not example.exists() or not env_file.exists():
            continue

        example_keys = parse_env_keys(example)
        runtime_keys = parse_env_keys(env_file)
        missing = sorted(example_keys - runtime_keys)
        if missing:
            drift.append(f"DRIFT env.tier-{tier}: {len(missing)} keys in .example but not in runtime")
            for key in missing:
                drift.append(f"  - {key}")
            drift.append("  Fix: run 'make secrets-funnel' to regenerate from CHIT source,")
            drift.append("       or add missing keys to secrets_manifest_v2.yaml")
    return drift


def parse_dotenv_value(raw: str) -> str:
    """Normalize a dotenv right-hand side to the value Compose resolves.

    This tool compares a file's value against a shell export, so it has to read
    the file the way Compose does. It did not: it stored ``value.strip()``, the
    raw text.

    That is not a corner case here. ``tools/brand_defaults.py:114-120`` QUOTES
    every value containing whitespace or ``#``, on the recorded grounds that
    "both consumers strip surrounding double quotes" -- so this repo's own
    generator emits values whose raw spelling never equals what any consumer
    sees. Comparing raw text reported a correct export as shadowing; and an
    export carrying the raw quoted spelling, which really does change what the
    container receives, compared equal and was missed.

    Models the compose-go dotenv rules this repo can produce: surrounding
    single or double quotes are stripped, escapes are processed only inside
    double quotes, and an unquoted value ends at a whitespace-preceded ``#``.
    Interpolation (``${OTHER}``) is deliberately NOT expanded -- its result
    depends on the very process environment under test, and brand_defaults
    refuses to quote values carrying ``$`` for the same reason.
    """
    value = raw.strip()
    if not value:
        return ""
    if value[0] in ("'", '"'):
        quote = value[0]
        escapes = {"n": "\n", "t": "\t", "r": "\r"}
        buf: list[str] = []
        i = 1
        while i < len(value):
            ch = value[i]
            # Only double quotes process escapes; '...' is literal.
            if quote == '"' and ch == "\\" and i + 1 < len(value):
                nxt = value[i + 1]
                buf.append(escapes.get(nxt, nxt))
                i += 2
                continue
            if ch == quote:
                return "".join(buf)
            buf.append(ch)
            i += 1
        return value  # unterminated quote: treat the text as literal
    # Unquoted: an inline comment needs whitespace in front of the `#`, so a
    # `#` inside a password is data.
    match = re.search(r"\s#", value)
    if match:
        value = value[: match.start()]
    return value.strip()


def compose_env_files() -> list[Path]:
    """The --env-file stack the Makefile hands Compose, in Compose's order.

    Mirrors ``COMPOSE_ENV_FILES`` (``pmoves/Makefile:97-134``). check_shadow()
    first shipped with a hand-written list -- env.shared plus the eight tiers --
    that differed from it in two ways, each of which changes the answer:

      * MISSING TIERS FALL BACK TO ``.example``. ``resolve_env_file`` takes
        ``env.tier-X`` if present, else ``env.tier-X.example``. A node that has
        not run the funnel is running off the examples, and an export shadowing
        one of them was invisible to this check.
      * THREE OPTIONAL OVERLAYS LOAD AFTER EVERY TIER, so they outrank them.
        Reporting a divergence from a tier file that a later overlay has
        already overridden names a file the operator would edit in vain, and
        the suggested ``env -u KEY`` would restore the overlay's value rather
        than the reported one.

    The two runtime switches are read from the process environment because that
    is where make reads them: ``SUPABASE_RUNTIME ?= compose`` (Makefile:30) and
    ``INCLUDE_ENV_LOCAL_IN_COMPOSE``.
    """

    def resolve(name: str) -> Path | None:
        path = Path(name)
        if path.exists():
            return path
        example = Path(f"{name}.example")
        return example if example.exists() else None

    files: list[Path] = []
    primary = resolve("env.shared")
    if primary is not None:
        files.append(primary)
    for tier in TIERS:
        resolved = resolve(f"env.tier-{tier}")
        if resolved is not None:
            files.append(resolved)

    runtime = os.environ.get("SUPABASE_RUNTIME", "compose")

    env_local = Path(".env.local")
    if env_local.exists() and (
        runtime != "compose"
        or os.environ.get("INCLUDE_ENV_LOCAL_IN_COMPOSE") == "1"
    ):
        files.append(env_local)

    supa_runtime = Path("env.supa.runtime")
    if supa_runtime.exists() and runtime == "cli":
        files.append(supa_runtime)

    urlencoded = Path("env.tier-supabase.urlencoded")
    if urlencoded.exists():
        files.append(urlencoded)

    return files


def check_shadow() -> list[str]:
    """Report pipeline-owned keys that a process-environment export shadows.

    THE FAILURE THIS CATCHES. Docker Compose resolves interpolation from the
    shell environment BEFORE any `--env-file`. So an exported variable silently
    outranks the entire secrets pipeline: `secrets-rotate` writes env.shared,
    `secrets-funnel` propagates to every tier file, every file on disk is
    correct -- and the container still receives the stale exported value. Every
    step reports success. Only the container disagrees, and nothing asks it.

    Measured 2026-09-02: SECRET_KEY_BASE was rotated 48 -> 96 chars and funnelled
    to all eight tier files. supabase-realtime was then recreated and came up
    with 48 chars, still crash-looping on "cookie store expects
    conn.secret_key_base to be at least 64 bytes". The session shell held a stale
    48-char export. Two rotations looked like they had failed; both had in fact
    succeeded on disk.

    This is the same family as check_drift(): the pipeline produced the right
    value and something downstream silently won. Drift catches the value never
    arriving; shadow catches it arriving and being overruled.

    WHY THIS REPORTS RATHER THAN UNSETS. Stripping the offending variables before
    invoking compose would "fix" it, but it would also silently break anyone
    deliberately overriding a value for a one-off run -- a regression that would
    itself be invisible. Detection is the honest half: name the variable, name
    the fix, let the operator decide. `env -u <KEY> make ...` unblocks a single
    command; clearing it from the launching shell fixes it for good.

    The files consulted are the ones compose is actually given -- see
    compose_env_files() -- and each side is read through dotenv semantics
    before comparison, so a quoted file value and its unquoted export are
    recognised as the same value.

    Values are compared by digest and never printed. Identical values are not
    reported -- an export that agrees with the file is harmless.
    """
    def digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    owned: dict[str, tuple[str, str]] = {}  # key -> (file, parsed value)
    for path in compose_env_files():
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export ") :].strip()
            if key:
                # Later files override earlier ones, matching compose's order,
                # so the file named in the report is the one that actually wins.
                owned[key] = (path.name, parse_dotenv_value(value))

    shadowed: list[str] = []
    for key, (source, file_value) in sorted(owned.items()):
        shell_value = os.environ.get(key)
        if shell_value is None or shell_value == file_value:
            continue
        shadowed.append(
            f"  - {key}: shell={digest(shell_value)} but {source}={digest(file_value)}"
        )

    if not shadowed:
        return []
    return (
        [
            f"SHADOWED {len(shadowed)} pipeline-owned key(s): a process-environment "
            "export outranks every --env-file,",
            "  so compose injects the exported value and the funnelled value never "
            "reaches the container.",
            "  (values shown as sha256[:12] -- never the secrets themselves)",
        ]
        + shadowed
        + [
            "  Fix (one command):  env -u <KEY> make -C pmoves <target>",
            "  Fix (permanent):    unset <KEY> in the shell that launches your tooling,",
            "                      then re-run the recreate so the container re-reads it.",
            "  Verify at the far end, not here: "
            "docker exec <ctr> sh -c 'echo ${#<KEY>}'",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate tiered env files.")
    # Drift ON by default. It shipped opt-in, the Makefile target passed no
    # flags, and so the check that catches "declared in .example, absent from the
    # runtime tier" never ran in the pipeline. That is how Z_AI_API_KEY reached
    # env.tier-llm.example, two hardcoded TIER_MAPPINGs, and the funnel -- while
    # being absent from the runtime tier on every node that reads it. SPARK hit
    # the same shape with Hermes.
    parser.add_argument(
        "--drift",
        action="store_true",
        default=True,
        help="Check key drift between .example and runtime files (default: on)",
    )
    parser.add_argument(
        "--no-drift",
        dest="drift",
        action="store_false",
        help="Skip the drift check (existence only).",
    )
    # Default ON, for the reason the --drift comment above records: a check that
    # ships opt-in, behind a Makefile target that passes no flags, never runs.
    parser.add_argument(
        "--shadow",
        action="store_true",
        default=True,
        help=(
            "Check whether a process-environment export shadows a pipeline-owned "
            "key (default: on). Compose prefers the shell over every --env-file."
        ),
    )
    parser.add_argument(
        "--no-shadow",
        dest="shadow",
        action="store_false",
        help="Skip the shadow check.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat drift/shadow warnings as errors (non-zero exit)",
    )
    args = parser.parse_args(argv)

    print("Checking tier environment files...")
    rc = 0
    drift_found = False

    # 1. Existence check
    missing_hard = check_existence()
    if missing_hard:
        print("")
        print("Missing tier files will cause services to fail or use defaults.")
        print("Fix: run 'make bootstrap-tier-envs' then 'make secrets-funnel'")
        rc = 1

    # 2. Drift check (always run if --drift or --strict)
    if args.drift or args.strict:
        drift = check_drift()
        if drift:
            print("")
            for line in drift:
                print(line)
            drift_found = True
            if args.strict:
                rc = 1

    # 3. Shadow check: the files can be perfect and still lose to the shell.
    shadow_found = False
    if args.shadow or args.strict:
        shadow = check_shadow()
        if shadow:
            print("")
            for line in shadow:
                print(line)
            shadow_found = True
            if args.strict:
                rc = 1

    if rc == 0:
        # Never let the summary contradict the lines above it -- in EITHER half.
        # `rc == 0 and shadow_found` used to win outright, so a run that found
        # both printed "The files on disk are correct" directly after listing
        # keys missing from those very files. That sent the operator to clear an
        # export while the drift went unmentioned, and recreated the
        # contradictory-summary failure the drift branch below was fixed for.
        if drift_found and shadow_found:
            print(
                "DRIFT AND SHADOWED KEYS BOTH PRESENT (not failing: pass --strict "
                "to make this an error). Keys above are declared in .example but "
                "absent from the runtime tier, AND an export outranks the files "
                "for other keys. Clearing the export is not sufficient on its "
                "own -- the missing tier keys still have to be funnelled."
            )
        elif shadow_found:
            print(
                "SHADOWED KEYS PRESENT (not failing: pass --strict to make this an "
                "error). The files on disk are correct; the container will not get "
                "them until the export is cleared."
            )
        elif drift_found:
            # Previously this branch printed "no drift detected" unconditionally,
            # immediately after listing the drift. A summary that contradicts the
            # output above it is worse than no summary: the reader believes the
            # last line.
            print(
                "DRIFT PRESENT (not failing: pass --strict to make this an error). "
                "Keys above are declared in .example but absent from the runtime "
                "tier, so every consumer reading that tier gets nothing."
            )
        elif args.drift:
            print("OK: All tier env files exist, no drift detected.")
        else:
            print("OK: All tier env files exist.")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
