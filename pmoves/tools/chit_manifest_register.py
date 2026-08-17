#!/usr/bin/env python3
"""Idempotently register missing entries in the v2 CHIT secrets manifest.

Per the tier-map doctrine (PR #2041): the secrets manifests are MACHINE-EMITTED
artifacts — agents and operators edit code-level registries, never the YAML by
hand. ``generate_chit_v2.py`` was the one-shot v1→v2 migration (its TIER_MAPPING
only re-tiers entries that already exist); this tool is the ongoing additive
lever: it ensures an entry EXISTS in the v2 manifest for every label declared in
``REGISTRY`` below, then ``make -C pmoves chit-manifest-sync`` derives v1 and
``make -C pmoves secrets-funnel`` projects the tier env files.

Design constraints (mirrors chit_manifest_merge.py conservatism):
  * Additive only — existing entries are NEVER modified or reordered.
  * New entries are inserted in alphabetical id position to keep diffs minimal.
  * ``--check`` reports pending additions and writes nothing (exit 1 if any).

Usage:
  python pmoves/tools/chit_manifest_register.py            # apply
  python pmoves/tools/chit_manifest_register.py --check    # gate/report

Exit codes:
  0  manifest already complete (or additions applied)
  1  --check found pending additions
  4  parse or usage error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"

# ── The agent-editable lever ─────────────────────────────────────────────────
# label -> {tier, required, aliases}. Adding a key here + running this tool +
# chit-manifest-sync + secrets-funnel is the complete sanctioned path for
# routing a new secret into the tier env files.
#
# Provider keys are required=False: their absence on a given node is normal
# (per-node provider enablement); the funnel warns instead of failing.
REGISTRY: Dict[str, Dict[str, Any]] = {
    # Tier 3: LLM (external provider keys) — TensorZero/worker lanes read
    # these from env.tier-llm.
    "HF_TOKEN": {"tier": "llm", "required": False},
    # Kimi coding plan (Moonshot). Canonical name matches the operator's GH
    # prod secret; the legacy Moonshot name stays honored as a source alias.
    # TensorZero's model config still reads the legacy name at the gateway —
    # compose maps it from this canonical key.
    "KIMI_CODING_API": {
        "tier": "llm",
        "required": False,
        "aliases": ["MOONSHOT_API_KEY"],
    },
    # Exported by sync-secrets-local since early on, but never registered —
    # so bundle materialization silently dropped it and transcribe-backend
    # (which hard-requires it at import) crash-loops on rehydrated nodes.
    "GROQ_API_KEY": {"tier": "llm", "required": False},
    "KILOCODE_API_KEY": {"tier": "llm", "required": False},
    "OLLAMA_API_KEY": {"tier": "llm", "required": False},
    "MINIMAX_API_KEY": {"tier": "llm", "required": False},
    "NVIDIA_API_KEY": {"tier": "llm", "required": False},
    # Tier 5: Agent — fleet-canonical Agent Zero inbound-MCP credential
    # (issue #2056 / PR #2057). MCP_SERVER_TOKEN is the legacy alias.
    "AGENT_ZERO_MCP_TOKEN": {
        "tier": "agent",
        "required": False,
        "aliases": ["MCP_SERVER_TOKEN"],
    },
    # Tier: supabase — Studio basic-auth through the Kong gateway. These became
    # HARD-REQUIRED when supabase-kong moved to DB-less declarative mode: the
    # vendored kong.yml declares a `basicauth_credentials` entry, and Kong
    # VALIDATES its declarative config at boot, so an empty password makes the
    # gateway refuse to start ("in 'password': length must be at least 1") —
    # taking /rest/v1, /auth/v1 and /storage/v1 down with it. Under the previous
    # DB-backed mode Kong booted happily with no config at all, which is why
    # neither name existed in any env file before now.
    # required:False so a node without them still materializes tier files; the
    # boot failure is loud and self-describing if they are genuinely absent.
    "DASHBOARD_USERNAME": {"tier": "supabase", "required": False},
    "DASHBOARD_PASSWORD": {"tier": "supabase", "required": False},
    # Internal fleet tokens — required ${VAR:?} compose vars that were absent from
    # the v2 manifest, so `docker compose up` file-wide interpolation aborted on
    # the field laptop. Randomly minted into env.shared; registering here
    # materializes them into the tier env files the funnel emits, so no service is
    # gated from a field node.
    # The CHIT passphrase, under the name the RUNTIME reads. Every compose file
    # writes `CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?...}` — the container-side name
    # is CHIT_PASSPHRASE, the host-side name is CHIT_PROD_PASSPHRASE, and only the
    # former was ever registered. 26 refs across 5 compose files / 12 services, and
    # since compose interpolates the whole file before running anything, the absence
    # gated every `up-*` target on the node rather than only those services.
    #
    # The alias is the load-bearing part: the GH secret is named CHIT_PASSPHRASE (no
    # CHIT_PROD_* secret exists in either scope, verified 2026-08-17), so older
    # bundles carry only that name. secrets_sync.py:120-131 resolves label first,
    # then aliases, and emits the CANONICAL target key either way — the same shape as
    # KIMI_CODING_API / MOONSHOT_API_KEY.
    #
    # required=True follows the neighbours below rather than the DASHBOARD_* pattern,
    # and the choice is not free: SECRETS_SYNC_FLAGS defaults to `--merge` (strict),
    # so on a node that genuinely lacks the secret the funnel now fails instead of
    # emitting tier files. That is the intended trade — required=False is not
    # "safer", it is silent: build_outputs() only records a missing key in `missing`
    # when required is set, so the funnel would keep reporting 0 errors for a node
    # whose every container is ungated, which is the exact defect being closed.
    # Escape hatch for a node that really should not have it: SECRETS_ALLOW_MISSING=1.
    "CHIT_PROD_PASSPHRASE": {
        "tier": "agent",
        "required": True,
        "aliases": ["CHIT_PASSPHRASE"],
    },
    "NATS_EVENT_BUS_TOKEN": {"tier": "data", "required": True},
    "PMOVES_BRIDGE_TOKEN": {"tier": "worker", "required": True},
    "SECRET_KEY_BASE": {"tier": "supabase", "required": True},
    "VAULT_ENC_KEY": {"tier": "supabase", "required": True},
    "LOGFLARE_PRIVATE_ACCESS_TOKEN": {"tier": "supabase", "required": True},
    "LOGFLARE_PUBLIC_ACCESS_TOKEN": {"tier": "supabase", "required": True},
    # Tier: Supabase — gotrue's outbound mailer credential. Without it gotrue
    # cannot send confirmation or password-reset mail, so signup produces
    # permanently-unconfirmed rows and the only account recovery is the admin
    # API. Only the password is a secret; SMTP_HOST/PORT/USER/ADMIN_EMAIL are
    # plain config and live in env.shared.
    "SMTP_PASS": {"tier": "supabase", "required": False},
}


def snake(label: str) -> str:
    return label.lower()


def build_entry(label: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    tier = spec["tier"]
    source: Dict[str, Any] = {"type": "cgp", "label": label}
    aliases = spec.get("aliases")
    if aliases:
        source["aliases"] = list(aliases)
    return {
        "id": snake(label),
        "source": source,
        "targets": [
            {"file": ".env.generated", "key": label},
            {"file": f"env.tier-{tier}", "key": label},
            {"github_secret": label},
            {"docker_secret": f"pmoves_{snake(label)}"},
        ],
        "required": bool(spec.get("required", False)),
        "tier": tier,
    }


def existing_labels(entries: Sequence[Any]) -> set[str]:
    labels: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = entry.get("source") or {}
        label = source.get("label")
        if label:
            labels.add(str(label))
        for alias in source.get("aliases") or []:
            labels.add(str(alias))
    return labels


def insert_alphabetical(entries: List[Any], entry: Dict[str, Any]) -> None:
    new_id = entry["id"]
    for idx, existing in enumerate(entries):
        existing_id = existing.get("id", "") if isinstance(existing, dict) else ""
        if existing_id > new_id:
            entries.insert(idx, entry)
            return
    entries.append(entry)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to the v2 manifest (default: pmoves/chit/secrets_manifest_v2.yaml)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report pending additions without writing (exit 1 if any)",
    )
    args = parser.parse_args(argv)

    try:
        manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"[error] cannot load manifest: {exc}", file=sys.stderr)
        return 4
    if not isinstance(manifest, dict) or not isinstance(manifest.get("entries"), list):
        print("[error] manifest has no entries list", file=sys.stderr)
        return 4

    entries: List[Any] = manifest["entries"]
    known = existing_labels(entries)
    pending = {
        label: spec for label, spec in REGISTRY.items() if label not in known
    }

    if not pending:
        print("manifest complete: all registry labels present")
        return 0

    for label, spec in sorted(pending.items()):
        print(f"{'would add' if args.check else 'adding'}: {label} -> tier {spec['tier']}")

    if args.check:
        return 1

    for label, spec in sorted(pending.items()):
        insert_alphabetical(entries, build_entry(label, spec))

    args.manifest.write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {args.manifest} (+{len(pending)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
