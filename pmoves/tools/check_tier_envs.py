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

    Values are compared by digest and never printed. Identical values are not
    reported -- an export that agrees with the file is harmless.
    """
    import hashlib
    import os

    def digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    # env.shared is compose's PRIMARY --env-file; the tier files layer over it.
    sources = [Path("env.shared")] + [Path(f"env.tier-{t}") for t in TIERS]
    owned: dict[str, tuple[str, str]] = {}  # key -> (file, value)
    for path in sources:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key:
                # Later files override earlier ones, matching compose's own order.
                owned[key] = (path.name, value.strip())

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

    if rc == 0 and shadow_found:
        # Never let the summary contradict the lines above it, for the same
        # reason the drift summary was fixed: the reader believes the last line.
        print(
            "SHADOWED KEYS PRESENT (not failing: pass --strict to make this an "
            "error). The files on disk are correct; the container will not get "
            "them until the export is cleared."
        )
    elif rc == 0:
        if args.drift and drift_found:
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
