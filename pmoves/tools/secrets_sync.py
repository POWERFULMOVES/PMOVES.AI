"""Generate env files from the CHIT secrets manifest."""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

import yaml

from pmoves.chit.codec import decode_secret_map, load_cgp
from pmoves.tools.secret_shape import inspect_value
from pmoves.tools.secrets_self_generated import (
    SELF_GENERATED,
    _SUPABASE_JWT_KEYS,
    EVENT_ACTIONS,
    EVENT_REASONS,
    EVENT_ROLES,
    KNOWN_RUNTIMES,
    compose_consumers,
    compose_service_names,
    fill_self_generated,
)

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
    # Vendor-guaranteed leading substring, when the label declares one. "" means
    # unconstrained.
    #
    # This is the constraint that would have caught E2B_API_KEY. It arrived 42
    # characters starting `b_` instead of 44 starting `e2b_` -- the leading `e2`
    # lost in delivery -- and because presence was the only gate, it materialized
    # into every tier file and the E2B Danger Room simply never ran. min_length
    # alone would not have caught it: 42 is not obviously short.
    prefix: str = ""


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
        prefix = item.get("prefix", "")
        if not isinstance(prefix, str):
            raise ValueError(f"Entry {entry_id} has non-string prefix")
        entries.append(
            Entry(
                id=entry_id,
                label=label,
                required=required,
                targets=targets,
                aliases=aliases,
                min_length=min_length,
                prefix=prefix,
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
    shape_withheld: List[str] = []
    shape_warnings: List[str] = []
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
        # Charset and shape -- the class this pipeline has never inspected.
        #
        # The min_length check below measures a value's LENGTH; nothing ever
        # measured its CHARACTERS. A delivered GATE_API_KEY carries an EM DASH
        # (U+2014) inside the key, and the only reason that is known is that a
        # third-party vendor CLI inspected it before putting it in an HTTP header
        # and said so in plain language. See pmoves/tools/secret_shape.py for the
        # full defect, and for why a lookalike glyph withholds while an ordinary
        # non-ASCII character only warns.
        #
        # Withheld, never repaired. Stripping the em dash is a GUESS at the real
        # value, and a guessed key produces the same opaque 401 as the corrupt one
        # while destroying the evidence that anything was wrong. Refusing makes
        # compose's `${VAR:?}` name the variable at `up` time instead. Same
        # doctrine as the under-length branch: loud beats late.
        verdict = inspect_value(entry.label, value, prefix=entry.prefix)
        shape_warnings.extend(verdict.warn)
        # Branch on `.withhold` explicitly. A ShapeVerdict instance is always
        # truthy, so `if verdict:` would read as "there is a problem" while being
        # unconditionally true.
        if verdict.withhold:
            shape_withheld.extend(verdict.withhold)
            if rejected_out is not None:
                for target in entry.targets:
                    rejected_out.setdefault(target.file, set()).add(target.key)
            if entry.required:
                missing.append(entry.label)
            continue
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
    if shape_withheld:
        print(
            "WARNING: withheld "
            + str(len(shape_withheld))
            + " mis-shaped secret(s): "
            + "; ".join(sorted(shape_withheld))
            + " -- a lookalike glyph (em dash for hyphen, smart quote, "
            "non-breaking space, zero-width) or a wrong vendor prefix means the "
            "value was corrupted BEFORE it reached this pipeline, typically by a "
            "copy-paste through a PDF, rich-text editor or rendered web page. "
            "Re-deliver the credential by retyping it or copying from a "
            "plain-text source. The funnel deliberately does NOT strip the "
            "character: a guessed value fails identically to a corrupt one while "
            "hiding that anything was wrong. Nothing above is secret material -- "
            "only the variable name, the codepoint, the position and the length.",
            file=sys.stderr,
        )
    if shape_warnings:
        print(
            "WARNING: "
            + str(len(shape_warnings))
            + " delivered secret(s) carry a suspicious character and were emitted "
            "ANYWAY: "
            + "; ".join(sorted(shape_warnings))
            + " -- not withheld, because a human-chosen password may legitimately "
            "contain these and several registered labels are passwords. But a "
            "non-ASCII character cannot be placed in an HTTP header at all, and "
            "surrounding whitespace is emitted verbatim, so verify each against "
            "its source.",
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


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that understands compose's own tags (``!reset``, ``!override``).
    Without it the overlays that use them fail to parse and their services drop
    out of the consumer list."""


def _compose_tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node):
    # Build the tagged block as plain data rather than dropping it: an
    # `!override` env list carries the replacement values, and a label named
    # only there must still show up as a consumer. (Over-inclusion on `!reset`
    # is harmless for a "who might need a recreate" list.)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _compose_tag)


def load_compose_docs(paths: Sequence[Path] | None = None, out=None) -> tuple[list, list[str]]:
    """``(docs, skipped_file_names)`` for every pmoves/docker-compose*.yml."""
    out = out or sys.stdout
    if paths is None:
        paths = sorted((REPO_ROOT / "pmoves").glob("docker-compose*.yml"))
    docs, skipped = [], []
    for path in paths:
        try:
            docs.append(yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader) or {})
        except (OSError, yaml.YAMLError) as exc:
            skipped.append(path.name)
            print(f"[secrets-sync] WARN could not read {path.name} for the compose service list ({type(exc).__name__})", file=out)
    return docs, skipped


_CONTEXT_KEYS = ("SUPABASE_RUNTIME", "SUPABASE_URL", "SUPABASE_REST_URL")
_SOURCES = ("shell env", "secret map", "unset")
_EVENT_LABELS = tuple(_SUPABASE_JWT_KEYS)
_UNRECOGNISED = "<unrecognised>"


def _closed(value: object, choices: Sequence[str]) -> str:
    """Return the CONSTANT member of *choices* equal to *value*, else a fixed
    marker. What is returned is always an element of a literal tuple, never the
    input, so nothing derived from the secret map (or a value in it) can reach
    the announcement -- the printers below only print what this returns."""
    for choice in choices:
        if choice == value:
            return choice
    return _UNRECOGNISED


def runtime_context(
    secrets: Mapping[str, str], environ: Mapping[str, str]
) -> tuple[Dict[str, str], Dict[str, str]]:
    """``(context, sources)``: the shell env wins over the secret map, exactly as
    it wins over compose's --env-file, INCLUDING a set-but-empty export (which
    fill_self_generated then treats as unknown). *sources* names where each
    context key came from, so a stray export is visible in the announcement."""
    context = {**secrets, **environ}
    sources = {}
    for key in _CONTEXT_KEYS:
        sources[key] = "shell env" if key in environ else "secret map" if key in secrets else "unset"
    return context, sources


def _describe_context(context: Mapping[str, str], sources: Mapping[str, str], local_services) -> str:
    from pmoves.tools.secrets_self_generated import _host_is_local

    parts = []
    for key in _CONTEXT_KEYS:
        src = _closed(sources.get(key, "unset"), _SOURCES)
        if src == "unset":
            parts.append(f"{key}=unset")
            continue
        val = (context.get(key) or "").strip()
        if not val:
            shown = "EMPTY"
        elif key == "SUPABASE_RUNTIME":
            # The runtime NAME only if it is a known one; never the raw value.
            shown = next((r for r in KNOWN_RUNTIMES if r == val), "other")
        else:  # never print a URL: hostnames can be topology
            shown = "local" if _host_is_local(val, local_services) else "remote"
        parts.append(f"{key}={shown} (from {src})")
    return "; ".join(parts)


# Known Roads that recreate the consumers a Supabase key change reaches. Printed
# as guidance only; this tool never starts or recreates anything.
_RECREATE_ROADS = (
    "make -C pmoves up-supabase   # supabase-kong (consumer keys), rest, studio, storage, ...",
    "make -C pmoves up-cipher     # cipher-api",
    "make -C pmoves up-agents     # agent-zero, archon, ...",
    "make -C pmoves up-ui         # UI builds with a baked-in anon key (rebuild)",
)


def _refusal_text(e: Mapping[str, str], sources: Mapping[str, str]) -> str:
    label = _closed(e.get("label"), _EVENT_LABELS)
    reason = _closed(e.get("reason"), EVENT_REASONS)
    expired = reason.startswith("expired_")
    base = reason[len("expired_"):] if expired else reason
    if base == "not_minted_here":
        why = ("was not minted by this node (no local JWT secret verifies it); "
               + ("it is EXPIRED: obtain a new key from its issuer (cloud project / Supabase CLI / peer node)"
                  if expired else "it may be correct for its own verifier"))
    elif base.startswith("empty_"):
        var = _closed(base[len("empty_"):], _CONTEXT_KEYS)
        src = _closed(sources.get(var, "unset"), _SOURCES)
        why = (f"{var} is set but EMPTY (from {src}); the runtime cannot "
               "be judged. Unset it or give it its real value")
    elif base == "runtime_unknown":
        why = ("SUPABASE_RUNTIME is not stated; on a compose-runtime node re-run with "
               "SUPABASE_RUNTIME=compose exported")
    else:
        why = f"this node's compose Supabase is not its verifier ({base})"
    state = "expired, " if expired else ""
    return f"[secrets-sync] WARN {label} {state}left unchanged: {why}"


def announce_jwt_events(
    events: Sequence[Mapping[str, str]],
    docs: Sequence[Mapping] | None = None,
    out=None,
    context: Mapping[str, str] | None = None,
    sources: Mapping[str, str] | None = None,
    local_services=None,
    written_labels: set | None = None,
) -> List[str]:
    """Print what the self-generated guard changed or refused -- NAMES only.

    A re-mint changes a key that running containers captured at create time;
    until every consumer is recreated the stack is half-old, half-new (Kong's
    consumer key is the sharpest case: every Kong client is refused). So the
    consumers are listed from the compose files themselves, not a typed list.
    Returns the consumer service names (for tests).
    """
    out = out or sys.stdout
    if not events:
        return []
    if context is not None and sources is not None:
        print("[secrets-sync] runtime context: " + _describe_context(context, sources, local_services), file=out)
    # Rebuild every event from the closed vocabulary before anything prints:
    # each field becomes the constant it equals (or the unrecognised marker).
    closed = [
        {"label": _closed(e.get("label"), _EVENT_LABELS),
         "role": _closed(e.get("role"), EVENT_ROLES),
         "action": _closed(e.get("action"), EVENT_ACTIONS),
         "reason": _closed(e.get("reason"), EVENT_REASONS)}
        for e in events
    ]
    for e in closed:
        if e["action"] == "left_unchanged":
            print(_refusal_text(e, sources or {}), file=out)
    # *written_labels*: labels that actually reach an env file on this run
    # (None = all). A re-mint that is not written -- excluded by --keys, a
    # report-only run, or an aborted run -- needs no recreate, and saying
    # "RECREATE" for it would send an operator to restart half the mesh for a
    # value that never changed on disk (#3433 review r4429049880).
    def written(e):
        return written_labels is None or e["label"] in written_labels

    for e in closed:
        if e["action"] == "reminted" and not written(e):
            print(f"[secrets-sync] NOT WRITTEN {e['label']} ({e['role']}): re-mint computed "
                  f"({e['reason']}) but this run does not write it; nothing to recreate for it",
                  file=out)
    reminted = [e for e in closed if e["action"] == "reminted" and written(e)]
    if not reminted:
        return []
    for e in reminted:
        print(f"[secrets-sync] RE-MINTED {e['label']} ({e['role']}): {e['reason']}", file=out)
    labels = sorted({e["label"] for e in closed
                     if e["action"] in ("reminted", "filled") and written(e)
                     and e["label"] != _UNRECOGNISED})
    if docs is None:
        docs, _ = load_compose_docs(out=out)
    consumers = compose_consumers(labels, docs)
    print(
        "[secrets-sync] RECREATE every consumer of the re-minted keys, or the stack runs "
        "half-old/half-new (Kong refuses every client whose key differs from its consumer key):",
        file=out,
    )
    print("[secrets-sync]   services naming them in compose: " + (", ".join(consumers) or "(none found)"), file=out)
    print("[secrets-sync]   plus any service that inherits them via env_file. Known Roads:", file=out)
    for road in _RECREATE_ROADS:
        print(f"[secrets-sync]     {road}", file=out)
    return consumers


def emitted_labels(entries: Sequence["Entry"], outputs: Mapping[str, Mapping[str, str]]) -> set:
    """Labels (and their aliases) of the entries build_outputs actually emitted:
    an entry counts only if one of its target keys is present in that target
    file's output. This is the set write_env_files will materialize."""
    written: set = set()
    for entry in entries:
        if any(target.key in outputs.get(target.file, {}) for target in entry.targets):
            written.add(entry.label)
            written.update(entry.aliases)
    return written


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
    # JWTs, minted under the verifiers' ${SUPABASE_JWT_SECRET:-${JWT_SECRET}})
    # so they project without operator input and are never emitted as
    # placeholders. It overwrites an existing value ONLY when this node minted
    # it (signature verifies under a local JWT secret), this node's compose
    # Supabase is its verifier, and it is expired or signed with the other
    # local secret (see fill_self_generated). Every change and every refusal is
    # announced below by NAME, with where the runtime context came from.
    compose_docs, _skipped = load_compose_docs()
    local_services = compose_service_names(compose_docs) if compose_docs else None
    context, sources = runtime_context(secrets, os.environ)
    jwt_events: List[Dict[str, str]] = []
    secrets = fill_self_generated(
        secrets, context=context, events=jwt_events, local_services=local_services
    )

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
    # Announce only now, against what this run actually WRITES: labels whose
    # entry build_outputs emitted (not merely entries that survived --keys --
    # a shape/charset veto withholds a value silently for an optional entry or
    # under --allow-missing), and only on a generate run that is not aborting.
    aborting = bool(missing) and not args.allow_missing
    writes = args.command == "generate" and not aborting
    announce_jwt_events(jwt_events, docs=compose_docs, context=context, sources=sources,
                        local_services=local_services,
                        written_labels=emitted_labels(entries, outputs) if writes else set())
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
