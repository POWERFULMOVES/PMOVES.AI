"""Generate env files from the CHIT secrets manifest."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

import yaml

from pmoves.chit.codec import decode_secret_map, load_cgp
from pmoves.tools.secrets_self_generated import fill_self_generated, SELF_GENERATED, _SUPABASE_JWT_KEYS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent


@dataclass
class Target:
    file: str
    key: str


@dataclass
class Entry:
    id: str
    label: str
    required: bool
    targets: Sequence[Target]
    aliases: Sequence[str] = ()
    # Minimum usable length, in characters. 0 means "unconstrained".
    #
    # Some consumers reject a secret that is present, non-empty, and simply too
    # short -- and they reject it at RUNTIME, long after the funnel reported
    # success. Phoenix's cookie store is the worked example: it raises
    # "cookie store expects conn.secret_key_base to be at least 64 bytes" on
    # every request, so supabase-realtime answers 500 while its container stays
    # "running". Measured on 4090 2026-08-22: SECRET_KEY_BASE was 48 chars and
    # the health check had failed 6118 consecutive times, which reads as a flaky
    # service rather than a mis-sized secret.
    min_length: int = 0


def load_manifest(path: Path) -> tuple[Path, Sequence[Entry]]:
    manifest_data = yaml.safe_load(path.read_text())
    if not isinstance(manifest_data, Mapping):
        raise ValueError("Manifest must be a mapping")
    if manifest_data.get("version") != 1:
        raise ValueError("Unsupported manifest version")

    default_targets: Sequence[Target] = []
    defaults = manifest_data.get("defaults", {})
    if isinstance(defaults, Mapping):
        target_data = defaults.get("targets", [])
        if isinstance(target_data, list):
            default_targets = [_parse_target(item) for item in target_data]

    cgp_file = manifest_data.get("cgp_file")
    if not isinstance(cgp_file, str):
        raise ValueError("Manifest missing 'cgp_file'")
    cgp_path = (REPO_ROOT / cgp_file).resolve()

    entries_raw = manifest_data.get("entries")
    if not isinstance(entries_raw, list):
        raise ValueError("Manifest 'entries' must be a list")

    entries: List[Entry] = []
    for item in entries_raw:
        if not isinstance(item, Mapping):
            continue
        entry_id = item.get("id")
        source = item.get("source", {})
        if not isinstance(entry_id, str):
            raise ValueError("Entry missing id")
        if not isinstance(source, Mapping):
            raise ValueError(f"Entry {entry_id} missing source mapping")
        if source.get("type") != "cgp":
            raise ValueError(f"Entry {entry_id} uses unsupported source")
        label = source.get("label")
        if not isinstance(label, str):
            raise ValueError(f"Entry {entry_id} missing source label")

        aliases_raw = source.get("aliases", [])
        aliases = (
            [a for a in aliases_raw if isinstance(a, str)]
            if isinstance(aliases_raw, list)
            else []
        )

        targets_data = item.get("targets")
        if isinstance(targets_data, list) and targets_data:
            targets = [_parse_target(t) for t in targets_data]
        else:
            targets = list(default_targets)
        if not targets:
            raise ValueError(f"Entry {entry_id} has no targets")

        required = bool(item.get("required", True))
        min_length = item.get("min_length", 0)
        if not isinstance(min_length, int) or isinstance(min_length, bool) or min_length < 0:
            raise ValueError(f"Entry {entry_id} has non-integer min_length")
        entries.append(
            Entry(
                id=entry_id,
                label=label,
                required=required,
                targets=targets,
                aliases=aliases,
                min_length=min_length,
            )
        )

    return cgp_path, entries


def _parse_target(data: Mapping) -> Target:
    if not isinstance(data, Mapping):
        raise ValueError("Target must be a mapping")
    file_name = data.get("file")
    key = data.get("key")
    if not isinstance(file_name, str) or not file_name:
        raise ValueError("Target missing file")
    if key is None:
        key = ""
    if not isinstance(key, str) or not key:
        raise ValueError("Target missing key")
    return Target(file=file_name, key=key)


def _first_usable(secrets: Mapping[str, str], entry: "Entry") -> str | None:
    """First of label-then-aliases whose value is non-empty after stripping.

    Returns None when every candidate is absent OR present-but-blank, so callers
    can treat "delivered as empty" and "never delivered" identically — which is how
    every consumer of a line-based env file already treats them.
    """
    for key in (entry.label, *entry.aliases):
        value = secrets.get(key)
        if value is not None and value.strip():
            return key
    return None


def build_outputs(
    secrets: Mapping[str, str],
    entries: Sequence[Entry],
    *,
    strict: bool = True,
    rejected_out: Dict[str, set] | None = None,
) -> tuple[Dict[str, Dict[str, str]], List[str]]:
    """Materialise per-file outputs.

    ``rejected_out``, when supplied, is filled with ``{file: {key, ...}}`` for
    values that were WITHHELD. Callers writing in merge mode must delete those
    keys explicitly: merge reads the existing file and updates it, so simply
    omitting a key leaves the previous -- rejected -- value in place. Optional
    rather than a third return value so existing callers keep working.
    """
    outputs: Dict[str, Dict[str, str]] = defaultdict(dict)
    missing: List[str] = []
    too_short: List[str] = []
    for entry in entries:
        # Honor legacy aliases: an operator may supply a deprecated name (e.g.
        # MCP_SERVER_TOKEN) that maps to a canonical label. Emit the canonical
        # target keys from whichever alias carries a USABLE value.
        #
        # "Usable" excludes present-but-empty, and that distinction is the whole
        # point. This previously tested key presence alone (`source_key not in
        # secrets`), so a canonical label sitting in the bundle with an EMPTY value
        # won over a populated alias: the empty was written as `KEY=` into every
        # target file and kept out of `missing` even when required.
        #
        # Measured on B850, 2026-08-18: `env.shared` carries CHIT_PROD_PASSPHRASE
        # with a zero-length value while the GH-delivered CHIT_PASSPHRASE alias
        # carries the real one. chit-export encodes env.shared into the bundle, so
        # the blank canonical shadowed the good alias at exactly this line.
        #
        # Why blank is worse than absent: compose's `${KEY:?}` rejects empty as well
        # as unset, but `${KEY?}` accepts it, and anything that SOURCES an env file
        # and exports it re-exports the blank — where shell environment then beats
        # every `--env-file`. An empty secret is not a secret; treat it as absent.
        source_key = _first_usable(secrets, entry)
        if source_key is None:
            if entry.required:
                missing.append(entry.label)
            # Cleared or never delivered -- either way this key must NOT survive
            # in the generated targets. `write_env_files` runs in merge mode by
            # default (SECRETS_SYNC_FLAGS), and merge PRESERVES keys it is not
            # given, so omitting one leaves the previous value live for Compose.
            #
            # Concretely: clear CIPHER_API_TOKEN in env.shared, rerun
            # `make -C pmoves secrets-funnel`, and without this the old token
            # stays in env.tier-agent and Cipher keeps requiring auth -- the
            # documented way to return it to unauthenticated mode silently does
            # nothing. Omission is not removal.
            #
            # This is the same treatment the min_length branch below already
            # gives a too-short value, and it is what `_first_usable` documents:
            # absent and present-but-blank are handled identically.
            if rejected_out is not None:
                for target in entry.targets:
                    rejected_out.setdefault(target.file, set()).add(target.key)
            continue
        value = secrets[source_key]
        # A secret can be present, non-empty, and still unusable because it is too
        # SHORT. That is the same failure family as blank-is-not-absent above, one
        # rung further along: `_first_usable` already refuses "" because an empty
        # secret is not a secret, and a 48-character value where the consumer
        # demands 64 is not a secret either -- it is a value that parses, passes
        # every gate, materializes into every tier file, and then fails at runtime.
        #
        # Withhold rather than emit. Emitting a known-bad value buys a container
        # that boots and then answers 500 forever; withholding it makes compose's
        # `${VAR:?}` refuse at `up` time with the variable named. Loud beats late.
        if entry.min_length and len(value) < entry.min_length:
            too_short.append(
                f"{entry.label} (have {len(value)} chars, need >= {entry.min_length})"
            )
            if rejected_out is not None:
                for target in entry.targets:
                    rejected_out.setdefault(target.file, set()).add(target.key)
            if entry.required:
                missing.append(entry.label)
            continue
        for target in entry.targets:
            outputs[target.file][target.key] = value
    if too_short:
        print(
            "WARNING: withheld "
            + str(len(too_short))
            + " under-length secret(s): "
            + ", ".join(sorted(too_short))
            + " -- rotate with `make -C pmoves secrets-rotate KEY=<NAME> LEN=<n>`. "
            "LEN is CHARACTERS, not bytes (bootstrap_env.py truncates: "
            "`secrets.token_urlsafe(length)[:length]`), and it DEFAULTS TO 48 -- "
            "which is how an under-length value gets minted without anyone choosing "
            "one. The value is present but shorter than its consumer accepts, so "
            "emitting it would produce a service that starts and then fails every "
            "request.",
            file=sys.stderr,
        )
    if missing and strict:
        joined = ", ".join(sorted(missing))
        raise KeyError(f"Missing required secrets: {joined}")
    return outputs, missing


def _drop_multiline(relative: str, values: Mapping[str, str]) -> Dict[str, str]:
    """Refuse to emit newline-bearing values into a line-based env file.

    Docker Compose `env_file`/`--env-file` and `docker run --env-file` are strictly
    one ``VAR=VAL`` per line; multi-line values are unsupported even when quoted, so a
    value with embedded ``\\n``/``\\r`` (e.g. a PEM/OpenSSH private key) splatters across
    lines and every continuation re-parses as a bogus ``VAR`` — the loader fails with
    ``unexpected character ... in variable name``. Such secrets must be delivered via the
    ``*_FILE`` convention (services.common.env.get_secret reads ``KEY`` then ``KEY_FILE``)
    or Docker ``secrets:`` (mounted at ``/run/secrets/<name>``), never as an inline env var.
    Refs: https://docs.docker.com/reference/compose-file/services/#env_file ;
    https://docs.docker.com/compose/how-tos/use-secrets/
    """
    safe: Dict[str, str] = {}
    skipped: List[str] = []
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            skipped.append(key)
            continue
        safe[key] = value
    if skipped:
        print(
            f"WARNING: {relative}: skipped {len(skipped)} multi-line secret(s) "
            f"({', '.join(sorted(skipped))}) — multi-line values corrupt line-based "
            "env files. Deliver via the *_FILE convention (services.common.env.get_secret) "
            "or Docker secrets, not an inline env var.",
            file=sys.stderr,
        )
    return safe


def write_env_files(
    outputs: Mapping[str, Mapping[str, str]],
    *,
    merge: bool = False,
    remove: Mapping[str, set] | None = None,
) -> None:
    """Write env files. ``remove`` names keys to DELETE in merge mode.

    Omission is not removal. Merge reads the existing file and updates it with
    the new outputs, so a key left out of ``outputs`` keeps whatever the file
    already held -- which for a withheld secret means the rejected value stays
    live for Compose. `--merge` is the funnel default (SECRETS_SYNC_FLAGS), so
    without this the withholding above would have changed nothing on any node
    that had already been funnelled once.
    """
    header = "# Auto-generated by pmoves.tools.secrets_sync. Do not edit.\n"
    for relative in sorted(set(outputs) | set(remove or {})):
        values = dict(outputs.get(relative, {}))
        env_path = PROJECT_ROOT / relative
        env_path.parent.mkdir(parents=True, exist_ok=True)
        values = _drop_multiline(relative, values)

        if merge and env_path.exists():
            # Selective rotation: read existing, update only specified keys
            existing: Dict[str, str] = {}
            comments: List[str] = []
            for raw_line in env_path.read_text().splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    comments.append(raw_line)
                    continue
                if "=" in stripped:
                    k, v = stripped.split("=", 1)
                    # Defensive: ignore lines from an already-corrupt file (a prior
                    # multi-line value leaves continuation lines whose "key" is not a
                    # valid env identifier) so the corruption is not propagated.
                    if not k.isidentifier():
                        continue
                    existing[k] = v
            # Merge: new values override existing for specified keys
            existing.update(values)
            for key in (remove or {}).get(relative, ()):  # rejected -> absent
                existing.pop(key, None)
            lines = comments + [""]
            for key in sorted(existing):
                lines.append(f"{key}={existing[key]}")
            env_path.write_text("\n".join(lines) + "\n")
        else:
            # Full regeneration (original behavior)
            lines_out = [header]
            for key in sorted(values):
                lines_out.append(f"{key}={values[key]}\n")
            env_path.write_text("".join(lines_out))


def report(outputs: Mapping[str, Mapping[str, str]]) -> str:
    rows = []
    for file_name, values in sorted(outputs.items()):
        rows.append(f"{file_name}: {len(values)} entries")
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed env files from CHIT secrets manifest.")
    parser.add_argument(
        "command",
        choices=("generate", "report"),
        help="generate env files or report planned outputs",
    )
    parser.add_argument(
        "--manifest",
        default="pmoves/chit/secrets_manifest.yaml",
        help="path to secrets manifest (default: pmoves/chit/secrets_manifest.yaml)",
    )
    parser.add_argument(
        "--cgp",
        default=None,
        help="override CGP file path from manifest (default: use manifest cgp_file)",
    )
    parser.add_argument(
        "--keys",
        nargs="*",
        default=None,
        help="Optional subset of secret labels to sync (selective rotation)",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        default=False,
        help="warn on missing required secrets instead of failing",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        default=False,
        help="merge into existing tier files instead of overwriting",
    )
    args = parser.parse_args(argv)

    manifest_path = (REPO_ROOT / args.manifest).resolve()
    cgp_path, entries = load_manifest(manifest_path)

    # Allow CLI override of CGP path
    if args.cgp:
        cgp_path = Path(args.cgp).expanduser().resolve()

    secrets = decode_secret_map(load_cgp(cgp_path))
    # Funnel-side guard: fill self-generated secrets (Supabase anon/service_role
    # JWTs derived from JWT_SECRET) so they project without operator input and
    # are never emitted as placeholders. Never overwrites an existing value.
    secrets = fill_self_generated(secrets)

    # Filter entries if --keys is specified (selective rotation)
    if args.keys:
        key_set = set(args.keys)
        # Auto-expand JWT_SECRET rotation to include all derived JWT keys
        # so derived values (anon/service_role) are regenerated in sync.
        if "JWT_SECRET" in key_set:
            key_set |= set(_SUPABASE_JWT_KEYS)
        entries = [e for e in entries if e.label in key_set]

    rejected: Dict[str, set] = {}
    outputs, missing = build_outputs(
        secrets, entries, strict=False, rejected_out=rejected
    )
    # Filter out self-generated secrets from the missing report — they are
    # either derivable (handled by fill_self_generated) or generated elsewhere
    # (e.g. POSTGRES_PASSWORD at db-init), so they are never operator gaps.
    missing = [k for k in missing if k not in SELF_GENERATED]
    if missing:
        joined = ", ".join(sorted(missing))
        if args.allow_missing:
            print(f"WARNING: Missing secrets (non-fatal): {joined}", file=sys.stderr)
        else:
            print(f"ERROR: Missing required secrets: {joined}", file=sys.stderr)
            return 1

    if args.command == "report":
        print(report(outputs))
        return 0

    write_env_files(
        outputs, merge=args.merge or bool(args.keys), remove=rejected
    )
    print(report(outputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
