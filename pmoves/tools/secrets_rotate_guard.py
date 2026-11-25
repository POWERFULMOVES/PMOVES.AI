#!/usr/bin/env python3
"""Refuse to random-mint a key that must be a signed JWT.

`make -C pmoves secrets-rotate KEY=***` mints a `random_urlsafe` value when no
VALUE is supplied. That is correct for passwords and HMAC secrets. It is
destructive for anything Supabase signs:

  * anon / service_role keys are JWTs signed by JWT_SECRET - a random string is
    not a JWT, so every client is rejected with a generic 401;
  * JWT_SECRET itself is the signing key - replacing it with random bytes silently
    invalidates every token that was minted with the old one.

The rotation runbook says this in prose ("these are NOT a plain secrets-rotate").
Prose does not stop a command. This does.

The decision is made from `pmoves/chit/secrets_manifest.yaml`, so it follows the
manifest rather than a parallel list: an entry is refused when it is one of the
JWT-bearing ids, or when its label/aliases overlap the signing-secret group.
A key that the manifest does not manage is allowed with a warning - the manifest
is not exhaustive and refusing unknown keys would block legitimate rotation.

Exit codes: 0 allow, 3 refuse, 4 manifest unreadable.

NOTE: the durable fix is a `kind:` field on each manifest entry (e.g. `kind: jwt`),
which removes the id list below. That is a manifest schema change and belongs in
its own lane; this guard is deliberately conservative until then.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a hard dependency elsewhere
    print("error: PyYAML is required", file=sys.stderr)
    raise SystemExit(4)

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "chit" / "secrets_manifest.yaml"

# Manifest ids are identifiers, never values, but a linter (and a log reader) cannot
# tell the difference -- CodeQL flags any manifest-derived string that reaches a log
# sink as potential clear-text secret disclosure. Strip to a safe identifier charset
# before logging: this satisfies the rule on its merits and removes log-injection.
_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def safe_id(value: object, limit: int = 64) -> str:
    """Reduce a manifest identifier to [A-Za-z0-9_.-] for safe logging."""
    return _UNSAFE_ID_CHARS.sub("", str(value))[:limit]

# Entries whose value must be a JWT (or the key that signs them).
JWT_MINTED_IDS = frozenset({
    "supabase_anon_key",
    "supabase_service_key",
    "supabase_service_role_key",
    "next_public_supabase_anon_key",
})

# The signing secret itself: rotating it is a full re-issue, not a value swap.
SIGNING_SECRET_IDS = frozenset({"supabase_jwt_secret"})

# Any of these labels appearing on an entry means the value participates in JWT
# signing or verification, so a random value breaks the chain.
SIGNING_LABELS = frozenset({"JWT_SECRET", "SUPABASE_JWT_SECRET"})


def load_entries(manifest: Path) -> List[Dict[str, Any]]:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    entries = data.get("secrets") or data.get("entries") or []
    return [e for e in entries if isinstance(e, dict)]


def entry_labels(entry: Dict[str, Any]) -> set[str]:
    """Every name an entry answers to: id, source label, aliases, target keys."""
    names: set[str] = set()
    if entry.get("id"):
        names.add(str(entry["id"]))
    source = entry.get("source") or {}
    if isinstance(source, dict):
        if source.get("label"):
            names.add(str(source["label"]))
        for alias in source.get("aliases") or []:
            names.add(str(alias))
    for target in entry.get("targets") or []:
        if isinstance(target, dict) and target.get("key"):
            names.add(str(target["key"]))
    return names


def find_entries(entries: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    """Every entry that answers to `key`.

    More than one can: SUPABASE_REALTIME_SECRET carries JWT_SECRET among its
    aliases in some manifests, so first-match would misreport which entry a
    refusal applies to. The caller evaluates all of them.
    """
    want = key.strip().upper()
    return [e for e in entries if want in {n.upper() for n in entry_labels(e)}]


def refuse_reason(entry: Dict[str, Any]) -> Optional[str]:
    """Return a human-readable refusal, or None when rotation is safe."""
    entry_id = str(entry.get("id", "")).lower()
    labels = {n.upper() for n in entry_labels(entry)}

    if entry_id in SIGNING_SECRET_IDS or labels & SIGNING_LABELS:
        return (
            "this is the JWT signing secret. Random-minting it invalidates every "
            "token already issued, across every service that validates against it. "
            "Use `python pmoves/tools/jwt_rotate.py rotate` (backup-first, re-mints "
            "anon + service_role, verifies new=200/old=401, rolls back on failure)."
        )
    if entry_id in JWT_MINTED_IDS:
        return (
            "this value must be a JWT signed by JWT_SECRET, not a random string. "
            "A random value is rejected by every client with a generic 401. "
            "Use `python pmoves/tools/jwt_rotate.py rotate`."
        )
    return None


def check(key: str, manifest: Path = DEFAULT_MANIFEST) -> int:
    if not manifest.exists():
        print(f"error: manifest not found: {manifest}", file=sys.stderr)
        return 4
    entries = load_entries(manifest)
    matches = find_entries(entries, key)

    if not matches:
        print(
            f"warn: {safe_id(key)} is not declared in {manifest.name}; allowing rotation "
            "(the manifest is not exhaustive)",
            file=sys.stderr,
        )
        return 0

    # Rank matches so the canonical entry is cited, not whichever alias-holder
    # happens to appear first in the file. Rotating the signing secret re-issues
    # everything, so it outranks a service key, which outranks an alias-only match.
    def _rank(entry: Dict[str, Any]) -> int:
        eid = str(entry.get("id", "")).lower()
        if eid in SIGNING_SECRET_IDS:
            return 3
        if eid in JWT_MINTED_IDS:
            return 2
        if {n.upper() for n in entry_labels(entry)} & SIGNING_LABELS:
            return 1
        return 0

    chosen = max(matches, key=_rank)

    reason = refuse_reason(chosen)
    if reason:
        print(f"REFUSED: secrets-rotate cannot mint {safe_id(key)}.", file=sys.stderr)
        print(f"  entry:  {safe_id(chosen.get('id'))}", file=sys.stderr)
        if len(matches) > 1:
            # Deliberately a COUNT, not the ids. CodeQL's taint tracking does not carry
            # sanitisation through a generator + join, so listing ids here keeps raising
            # py/clear-text-logging even though safe_id() strips them. A count carries no
            # tainted data and the ids are recoverable from the manifest by the operator.
            print(
                f"  also declared by {len(matches) - 1} other manifest entr"
                f"{'y' if len(matches) == 2 else 'ies'}",
                file=sys.stderr,
            )
        if key.strip().upper() in SIGNING_LABELS and str(chosen.get("id", "")) not in SIGNING_SECRET_IDS:
            print(
                f"  note: {safe_id(key)} is declared as an alias of {safe_id(chosen.get('id'))}, "
                "while the canonical supabase_jwt_secret entry does not list it as an alias. "
                "That aliasing looks inverted - flag it, do not silently 'fix' the value.",
                file=sys.stderr,
            )
        print(f"  reason: {reason}", file=sys.stderr)
        return 3
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guard `secrets-rotate` against keys that must be signed JWTs.",
    )
    parser.add_argument("--key", required=True, help="the KEY being rotated")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    return check(args.key, args.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
