#!/usr/bin/env python3
"""Recover live secret values from the running fleet BEFORE the funnel mints new ones.

THE DEFECT THIS CLOSES
----------------------
``make secrets-funnel`` calls ``secrets-ensure-generated`` unconditionally, and
that step mints every ``SECRETS_ENSURE_KEYS`` entry whose env.shared slot is
absent or empty. That is exactly right on a virgin node. It is a data-loss event
on a node in the recovery state PR #2886 describes -- env.shared has lost the
value but a RUNNING container still holds it -- because the very next line of the
funnel (``secrets-funnel-sync``) materializes the freshly minted value into the
generated tier files. A later ``supabase-pooler`` recreation then receives a
different ``VAULT_ENC_KEY`` and can no longer decrypt the tenant credentials
already stored under the old one, nor the YouTube OAuth cookies that the same key
protects (``services/yt-cookie-refresher/supabase_client.py`` builds a Fernet
from it via ``bytes.fromhex``).

``secrets-runtime-hydrate`` runs earlier in the funnel and does recover values
from containers -- but only Supabase aliases plus Meili, Firefly, Agent Zero and
Invidious. It never looks at these four. So the mint is reached with the slots
still empty and no warning is possible.

The PR body telling the operator to harvest first is not a fix. The step fires
automatically inside ``make secrets-funnel``; documentation cannot guard it.

THE ONE QUESTION
----------------
The branch is NOT "is this node new?". It is:

    does any running container or persisted volume hold state
    encrypted under the old value?

  STATE 1  no holder, no state volume      -> MINT. Correct, not degraded: a
                                              fresh key encrypts nothing that
                                              was encrypted before.
  STATE 2  a running container holds it    -> HARVEST. A harvested value is
                                              strictly better than a minted one.
  STATE 3  no holder, state volume present -> REFUSE. Harvest is impossible AND
                                              minting is destructive. Fail closed.

State 3 is the whole reason this file exists. Per this repo's audit doctrine,
``0 clean / 1 findings / 3 could not measure -- NOT a pass``: an unnecessary
refusal costs an operator five minutes, while an unnecessary mint silently
destroys tenant credentials and passes ``compose config`` on the way out. The
gate that would have caught the damage is the gate the mint satisfies.

WHAT THIS FILE DOES NOT DO
--------------------------
* It never OVERWRITES a slot that already holds a value, even one that disagrees
  with the fleet. It fills empty slots; it is not a reconciler. Rotating live
  material stays operator-invoked (``make secrets-rotate``).
* It never ``docker exec``s. Every read is host-side ``docker inspect``.
* It never renders a value -- not to stdout, not to stderr, not masked. A masked
  ``abcd...wxyz`` still publishes eight characters into a make log that anyone
  can scroll back through. Names, lengths and container identities only.
* It never generates. When a key is safe to mint it says so and returns, leaving
  ``bootstrap_env.py --ensure`` as the single minting path in the repo.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pmoves.tools._secrets_common import is_placeholder as _looks_placeholder

# bootstrap_env.py lives in scripts/ and is not importable as a package member,
# so load it by path. Reusing its rotate_secret is deliberate: the surgical
# single-line replace, the multi-line refusal, the duplicate-key drop and the
# cleared-tombstone unmark are all behaviours a second writer would have to
# reimplement and would eventually get wrong.
_BOOTSTRAP_ENV = _REPO_ROOT / "pmoves" / "scripts" / "bootstrap_env.py"
_spec = importlib.util.spec_from_file_location("_bootstrap_env_for_harvest", _BOOTSTRAP_ENV)
_be = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _be
_spec.loader.exec_module(_be)

read_env_value = _be.read_env_value
rotate_secret = _be.rotate_secret

STATE_SATISFIED = "satisfied"
STATE_HARVEST = "harvest"
STATE_MINT = "mint"
STATE_REFUSE = "refuse"

# Bare truthy words are NOT acknowledgements. A blanket `=1` is the flag that
# gets pasted from a stale runbook into a node it was never reasoned about on;
# naming the key is the point of the gate.
_ACK_NON_KEYS = {"1", "0", "TRUE", "FALSE", "YES", "NO", "ON", "OFF", "ALL", "*"}


@dataclass(frozen=True)
class HarvestSpec:
    """Where a key's pre-existing encrypted state lives, if anywhere.

    ``state_volumes`` are matched as substrings of ``docker volume ls`` names so
    the table survives a project-prefix change (``pmoves_`` here, something else
    on another node) without becoming a guess.
    """

    state_volumes: Tuple[str, ...]
    state_note: str


# MEASURED against pmoves/docker-compose.yml on this branch, not assumed:
#   * supabase-pooler  DATABASE_URL         -> ...@supabase-db:5432/_supabase
#   * supabase-analytics POSTGRES_BACKEND_URL -> ...@supabase-db:5432/_supabase
#   * supabase-db      volumes: supabase-db-data:/var/lib/postgresql/data
# so every row those two services encrypt or authenticate against is inside the
# supabase-db-data volume. The YouTube OAuth ciphertext lives there too --
# services/yt-cookie-refresher/supabase_client.py stores the Fernet-encrypted
# cookies in Supabase; the yt-cookies volume holds only the decrypted output.
_SUPABASE_STATE = ("supabase-db-data",)

HARVEST_SPECS: Dict[str, HarvestSpec] = {
    "SECRET_KEY_BASE": HarvestSpec(
        state_volumes=_SUPABASE_STATE,
        state_note=(
            "Supavisor and Logflare sign session/cookie state with it against the "
            "_supabase database"
        ),
    ),
    "VAULT_ENC_KEY": HarvestSpec(
        state_volumes=_SUPABASE_STATE,
        state_note=(
            "Supavisor's Cloak vault encrypts tenant credentials with it, and the "
            "yt OAuth vault Fernet-encrypts stored YouTube cookies with it"
        ),
    ),
    "LOGFLARE_PUBLIC_ACCESS_TOKEN": HarvestSpec(
        state_volumes=_SUPABASE_STATE,
        state_note="Logflare persists the token's source bindings in the _supabase database",
    ),
    "LOGFLARE_PRIVATE_ACCESS_TOKEN": HarvestSpec(
        state_volumes=_SUPABASE_STATE,
        state_note="Logflare persists the token's source bindings in the _supabase database",
    ),
}


@dataclass
class Decision:
    key: str
    state: str
    reason: str
    detail: str = ""
    holders: Tuple[str, ...] = ()
    value: Optional[str] = None  # never logged, never returned to a caller that prints
    shape_ok: bool = True
    warning: Optional[str] = None

    @property
    def action(self) -> str:
        return {
            STATE_SATISFIED: "none",
            STATE_HARVEST: "harvest",
            STATE_MINT: "mint",
            STATE_REFUSE: "refuse",
        }[self.state]


class DockerProbe:
    """Host-side docker reads. Never ``exec``, never mutating.

    Every method degrades to "nothing found" rather than raising, because a node
    without docker is a legitimate STATE 1 (CI, a fresh clone) and must not be
    turned into a hard funnel failure.
    """

    def __init__(self) -> None:
        self._checked = False
        self._available = False

    @staticmethod
    def _run(cmd: Sequence[str]) -> str:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return ""
        if proc.returncode != 0:
            return ""
        return proc.stdout

    def available(self) -> bool:
        if not self._checked:
            self._checked = True
            self._available = bool(self._run(["docker", "version", "--format", "{{.Server.Version}}"]).strip())
        return self._available

    def container_envs(self) -> Dict[str, Dict[str, str]]:
        if not self.available():
            return {}
        names = [n.strip() for n in self._run(["docker", "ps", "--format", "{{.Names}}"]).splitlines() if n.strip()]
        if not names:
            return {}
        raw = self._run(["docker", "inspect", *names])
        if not raw:
            return {}
        try:
            blobs = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        out: Dict[str, Dict[str, str]] = {}
        for blob in blobs:
            name = (blob.get("Name") or "").lstrip("/")
            envs: Dict[str, str] = {}
            for entry in (blob.get("Config") or {}).get("Env") or []:
                k, sep, v = entry.partition("=")
                if sep:
                    envs[k] = v
            if name:
                out[name] = envs
        return out

    def volumes(self) -> List[str]:
        if not self.available():
            return []
        return [v.strip() for v in self._run(["docker", "volume", "ls", "--format", "{{.Name}}"]).splitlines() if v.strip()]


def parse_ack(raw: Optional[str]) -> Set[str]:
    """Parse SECRETS_HARVEST_ACK_DESTRUCTIVE into a set of key NAMES.

    Anything that is not a plausible env key name -- including every truthy word
    -- is discarded rather than treated as "yes, all of them". An operator who
    means it can name what they mean.
    """
    if not raw:
        return set()
    out: Set[str] = set()
    for token in raw.replace(",", " ").split():
        candidate = token.strip().upper()
        if not candidate or candidate in _ACK_NON_KEYS:
            continue
        if _be._ENV_KEY_RE.match(candidate):
            out.add(candidate)
    return out


def _holders(key: str, container_envs: Mapping[str, Mapping[str, str]]) -> Dict[str, str]:
    """Containers whose environment carries a usable value for *key*.

    Every running container is scanned, not a curated list: the point is to find
    disagreement, and a curated list can only find disagreement among the
    containers someone remembered to curate. A placeholder or empty value is not
    a holder -- there is nothing there worth preserving.
    """
    found: Dict[str, str] = {}
    for name in sorted(container_envs):
        value = (container_envs[name].get(key) or "").strip()
        if value and not _looks_placeholder(value):
            found[name] = value
    return found


def _matching_volumes(spec: Optional[HarvestSpec], volumes: Iterable[str]) -> List[str]:
    if not spec:
        return []
    return sorted({v for v in volumes for token in spec.state_volumes if token in v})


def classify(
    key: str,
    *,
    env_path: Path,
    container_envs: Mapping[str, Mapping[str, str]],
    volumes: Sequence[str],
    registry_path: Optional[str] = None,
    ack_destructive: Optional[Set[str]] = None,
) -> Decision:
    # Match ensure_secret's own predicate exactly. If the two disagreed there
    # would be a slot the guard skips and the mint then fills -- the defect,
    # reintroduced one layer down.
    existing = read_env_value(key, env_path)
    if existing not in (None, ""):
        return Decision(key, STATE_SATISFIED, "already set in the funnel source")

    ack = ack_destructive or set()
    spec = HARVEST_SPECS.get(key)
    holders = _holders(key, container_envs)
    distinct = sorted(set(holders.values()))

    if len(distinct) > 1:
        # Cannot know which value the persisted state is keyed to. Minting is a
        # third wrong answer, so refuse and let an operator decide. An ack does
        # NOT unlock this: acknowledging "there is state I cannot reach" is a
        # different decision from "pick one of two live values for me".
        groups: Dict[str, List[str]] = {}
        for name, value in holders.items():
            groups.setdefault(value, []).append(name)
        arms = " | ".join(
            "%d container(s): %s" % (len(names), ", ".join(sorted(names)))
            for names in sorted(groups.values(), key=lambda n: sorted(n)[0])
        )
        return Decision(
            key,
            STATE_REFUSE,
            "running containers disagree on %s" % key,
            detail=(
                "%s: %d running containers hold %d DIFFERENT values -- %s. "
                "Harvesting would pick one arbitrarily and minting would discard both. "
                "Decide which value the persisted state is keyed to, then set it "
                "explicitly: export PMOVES_ROTATE_VALUE=\"$(...)\" && "
                "make -C pmoves secrets-rotate KEY=%s"
                % (key, len(holders), len(distinct), arms, key)
            ),
            holders=tuple(sorted(holders)),
        )

    if distinct:
        value = distinct[0]
        declared = _be._registry_generator(key, registry_path)
        shape_ok = _be.value_matches_spec(value, declared)
        warning = None
        if not shape_ok:
            # Harvest anyway. Refusing on shape bricks recovery on exactly the
            # node that needs it -- the 4090's VAULT_ENC_KEY was minted urlsafe
            # into a random_hex slot, and the fleet agrees on that broken value.
            # Desync from the running fleet is the larger hazard; say it loudly.
            warning = (
                "harvested value does not match the shape the bootstrap registry "
                "declares for %s (%s). Preserved anyway because it is what the running "
                "fleet agrees on -- desync is worse than malformed -- but this key needs "
                "a deliberate re-key with its consumers stopped."
                % (key, json.dumps(declared or {}, sort_keys=True))
            )
        return Decision(
            key,
            STATE_HARVEST,
            "%d running container(s) hold it, unanimously" % len(holders),
            detail=", ".join(sorted(holders)),
            holders=tuple(sorted(holders)),
            value=value,
            shape_ok=shape_ok,
            warning=warning,
        )

    present = _matching_volumes(spec, volumes)
    if present and key not in ack:
        return Decision(
            key,
            STATE_REFUSE,
            "no holder, but persisted state exists",
            detail=(
                "%s is absent from the funnel source, NO running container holds it, "
                "and the volume(s) %s still exist -- %s. Harvest is impossible and "
                "minting is destructive, so this refuses rather than guessing. "
                "Recover by starting the stack so a holder exists (make -C pmoves supa-up) "
                "and re-running, or by restoring the value from a backup with "
                "make -C pmoves secrets-rotate KEY=%s. If this node genuinely has no "
                "state worth keeping, say so by name -- and only then: "
                "SECRETS_HARVEST_ACK_DESTRUCTIVE=%s make -C pmoves secrets-funnel "
                "(this DESTROYS whatever those volumes hold under the old %s)."
                % (key, ", ".join(present), spec.state_note if spec else "", key, key, key)
            ),
        )

    reason = "no holder and no state volume -- safe to generate"
    if present:
        reason = "no holder; destructive mint acknowledged by name for %s" % key
    return Decision(key, STATE_MINT, reason, detail=", ".join(present))


def build_plan(
    keys: Sequence[str],
    *,
    env_path: Path,
    probe: Optional[object] = None,
    registry_path: Optional[str] = None,
    ack_destructive: Optional[Set[str]] = None,
) -> List[Decision]:
    probe = probe if probe is not None else DockerProbe()
    container_envs = probe.container_envs()
    volumes = probe.volumes()
    return [
        classify(
            key,
            env_path=env_path,
            container_envs=container_envs,
            volumes=volumes,
            registry_path=registry_path,
            ack_destructive=ack_destructive,
        )
        for key in keys
    ]


def apply_plan(plan: Sequence[Decision], *, env_path: Path) -> List[str]:
    """Write every harvested value, or write nothing.

    ALL-OR-NOTHING IS LOAD-BEARING. A partial apply is the sequencing trap in
    miniature: some keys recovered, some minted, ``compose config`` green over
    the top of the damage, and no later run notices because ``--ensure`` reports
    "already set -- left untouched" from then on.
    """
    if any(d.state == STATE_REFUSE for d in plan):
        return []
    written: List[str] = []
    for d in plan:
        if d.state != STATE_HARVEST or d.value is None:
            continue
        rotate_secret(d.key, value=d.value, env_path=env_path)
        written.append(d.key)
    return written


def _report(plan: Sequence[Decision]) -> None:
    width = max((len(d.key) for d in plan), default=1)
    for d in plan:
        stream = sys.stderr if d.state == STATE_REFUSE else sys.stdout
        print("  %-*s  %-8s  %s" % (width, d.key, d.action, d.reason), file=stream)
        if d.warning:
            print("      WARNING: %s" % d.warning, file=sys.stderr)
        if d.state == STATE_REFUSE:
            print("      %s" % d.detail, file=sys.stderr)
        elif d.state == STATE_HARVEST:
            print("      from: %s" % d.detail, file=sys.stdout)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover live secret values from running containers before the funnel "
            "mints replacements. Writes nothing when a value can be minted safely."
        )
    )
    parser.add_argument(
        "--key",
        action="append",
        default=[],
        metavar="NAME",
        help="Key to examine. Repeatable. Normally the SECRETS_ENSURE_KEYS list.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_be.ENV_SHARED_PATH,
        help="Funnel source to fill (default: pmoves/env.shared).",
    )
    parser.add_argument("--registry", default=None, help="Path to bootstrap registry JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify and report; write nothing. Exit code is unchanged.",
    )
    args = parser.parse_args(argv)

    keys = [k.strip() for k in args.key if k.strip()]
    if not keys:
        # Mirrors secrets-ensure-generated's own empty-list guard: an empty key
        # list must mean "examine nothing", never "examine everything".
        print("secrets-harvest: no keys requested — nothing to examine")
        return 0

    ack = parse_ack(os.environ.get("SECRETS_HARVEST_ACK_DESTRUCTIVE"))
    plan = build_plan(
        keys,
        env_path=args.env_file,
        registry_path=args.registry,
        ack_destructive=ack,
    )

    print("secrets-harvest: examined %d key(s) against the running fleet" % len(plan))
    _report(plan)

    refusals = [d for d in plan if d.state == STATE_REFUSE]
    if refusals:
        print(
            "secrets-harvest: REFUSED — %d key(s) could not be measured safely: %s.\n"
            "  Nothing was written. The funnel is stopped BEFORE secrets-ensure-generated "
            "so no value has been minted over live state."
            % (len(refusals), ", ".join(d.key for d in refusals)),
            file=sys.stderr,
        )
        return 3

    if args.dry_run:
        return 0

    written = apply_plan(plan, env_path=args.env_file)
    if written:
        print("secrets-harvest: recovered %d key(s) into %s: %s" % (len(written), args.env_file, ", ".join(written)))
    else:
        print("secrets-harvest: nothing to recover — remaining keys are safe to mint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
