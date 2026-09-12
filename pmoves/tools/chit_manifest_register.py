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
    # Tier 5: Agent — Cipher Memory's inbound bearer. Same shape as the
    # GROQ_API_KEY note above: live in env.shared and consumed by compose
    # (`CIPHER_API_TOKEN=${CIPHER_API_TOKEN:-}` in docker-compose.agents.yml)
    # but never registered, so the funnel never routed it into env.tier-agent
    # and `manifest-audit` showed no cipher row at all.
    #
    # The visible symptom is a 401, not a missing var: `.claude/mcp.json` sends
    # `Bearer ${CIPHER_API_TOKEN:-}`, an unset var collapses to an empty bearer,
    # and Cipher rejects it. `.claude/context/cipher.md` already documents that
    # ("header expands empty without the env var -> 401, expected") — the gap
    # was that nothing in the pipeline was responsible for supplying it.
    #
    # Registering it also makes rotation a Known Road instead of a hand-edit:
    # change the value, `make -C pmoves secrets-funnel`, recreate cipher.
    "CIPHER_API_TOKEN": {"tier": "agent", "required": False},
    # Tier 5: Agent — the Claude Code coding-plan credential.
    # env.tier-agent.example has declared this since PR #2359, and both compose
    # files wire `${CLAUDE_CODE_OAUTH_TOKEN:-}` into the archon service, but it
    # was never registered HERE — so the funnel never emitted it and the var
    # arrives empty on every node. Meanwhile ANTHROPIC_API_KEY (metered, and a
    # registered slot) is set fleet-wide from env.shared, and the Claude CLI
    # PREFERS it over the OAuth token. Net effect: archon boots healthy, passes
    # its health check, and every workflow dies on
    # `billing_error: Credit balance is too low`.
    # MODEL_FABRIC_CONTRACT.md:44 already lists `Claude Code Max` in the
    # approved coding-plan inventory, so this is a missing slot rather than a
    # new policy decision.
    "CLAUDE_CODE_OAUTH_TOKEN": {"tier": "agent", "required": False},
    # Tier 5: Agent — the GitHub App identity the fleet mints tokens with.
    #
    # These two are the runtime half of a signing identity, not ordinary config.
    # signing_identity_cards.yaml declares `ml.primary_method: github-app` on
    # every agent card and leaves `ml.github_app_installation_id` null with the
    # comment "populated from GH_APP_INSTALLATION_ID secret at runtime"
    # (pmoves/config/signing_identity_cards.yaml:53). Nothing in the pipeline was
    # responsible for supplying that secret: neither name appeared in this
    # REGISTRY, so the funnel never routed either into env.tier-agent.
    #
    # The failure is node-shaped, which is why it stayed invisible. On the node
    # where the operator hand-placed the values, the card resolves and the CHIT
    # room-activation checklist passes; on every node brought up from the funnel
    # the same checklist has no key material to resolve. Same family as
    # JUICEFS_META_PASSWORD below — one node works, no second node can be stood
    # up without hand-copying a secret, which is the thing the funnel exists to
    # prevent.
    #
    # env.tier-agent is not a guess: github_webhook_auto_config.py:447-460 opens
    # `pmoves/env.tier-agent` by name and fails with "GH_APP_ID or GH_APP_SEC not
    # found in env.tier-agent". It reads from a file nothing was writing to.
    #
    # required=False, and here that is not the silent choice the CHIT_PROD_
    # PASSPHRASE note below warns about: both consumers already fail loudly and
    # name the missing variable — github_client.py:61 raises "Configure GH_APP_ID,
    # GH_APP_INSTALLATION_ID, and GH_APP_SEC", and the webhook tool returns the
    # message quoted above. Under `--merge` (strict) required=True would instead
    # fail the whole funnel — and therefore every unrelated service — on any node
    # that legitimately does not mint GitHub tokens.
    #
    # min_length is shape, not presence. `[ -n "$VAR" ]` accepts a truncated id,
    # and secrets_sync.py:218 is the only place in the pipeline that measures a
    # value rather than testing it for emptiness: an under-length value is
    # WITHHELD and warned with both numbers, so compose's `${VAR:?}` refuses at
    # `up` time instead of a container booting with a half id.
    #
    # The floors are minimums for a modern GitHub App, not the local values:
    # installation ids are currently 8 digits and app ids 6-7, so 7/5 catch the
    # two-character truncation family while still admitting a shorter legacy id.
    # What they do NOT catch: a one-character truncation, or a value of the right
    # length that is not numeric at all. The registry has no `pattern` field
    # (build_entry supports tier/required/aliases/min_length; RECONCILED_FIELDS
    # is ("min_length",)) and adding one would mean changing the emitter, the
    # v1 sync and the funnel's validator together — deliberately out of scope
    # here rather than half-done.
    #
    # GH_APP_SEC is deliberately ABSENT from this registry despite being the
    # third leg of the same credential. It is a PEM private key, and
    # secrets_sync.py:251 `_drop_multiline` refuses to emit any newline-bearing
    # value into a line-based env file (compose env_file is strictly one
    # VAR=VAL per line). Registering it here would create a slot that reports as
    # delivered and is dropped with a warning on every run. It needs the *_FILE
    # convention or a Docker secret; see the PR that added these two.
    "GH_APP_INSTALLATION_ID": {"tier": "agent", "required": False, "min_length": 7},
    "GH_APP_ID": {"tier": "agent", "required": False, "min_length": 5},
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
    # bundles carry only that name. secrets_sync.py:112 (_first_usable) resolves label first,
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
    # PMOVES MCP Gateway inbound auth. The gateway binds 0.0.0.0 across four
    # fleet networks so every agent can reach it; without this token and without
    # --allow-unauthenticated it refuses remote callers, which is the correct
    # default. required=True because docker-compose.mcp-gateway.yml declares it
    # ${MCP_GATEWAY_AUTH_TOKEN:?} — an unset value fails the whole `up`, and
    # file-wide interpolation means it would gate every service in that file.
    "MCP_GATEWAY_AUTH_TOKEN": {"tier": "agent", "required": True},
    # Tier: data -- the scoped JuiceFS metadata role's password.
    #
    # The cross-node lane (handoffs/juicefs-meta-scoped-role-and-tailnet-exposure)
    # created a non-superuser `juicefs_meta` Postgres role and cut B850's mount
    # over to it. But the credential never entered the pipeline: it lives at
    # /home/pmoves/.pmoves-secrets/juicefs_meta_pw -- a hand-placed file, under a
    # different user's home, bind-mounted to /run/secrets/jfs_meta_pw, and
    # referenced NOWHERE in this repo. So B850 works and no second node can be
    # brought up without hand-copying a secret, which is the thing the funnel
    # exists to prevent.
    #
    # This is now load-bearing rather than tidy: pg_hba (PR #2702) admits ONLY
    # juicefs_meta from the tailnet and rejects every other role there, so a
    # remote mount has no fallback credential -- it authenticates as this role
    # or not at all.
    #
    # required=False, unlike its neighbours: only the nodes that actually mount
    # pmoves-media need it. Under `--merge` (strict) a required slot fails the
    # whole funnel on every node that legitimately lacks it. The silence that
    # required=False buys elsewhere does not apply here -- an absent value fails
    # loudly at mount time with an auth error, not quietly at runtime.
    "JUICEFS_META_PASSWORD": {"tier": "data", "required": False},
    "NATS_EVENT_BUS_TOKEN": {"tier": "data", "required": True},
    "PMOVES_BRIDGE_TOKEN": {"tier": "worker", "required": True},
    # ActivePieces self-host (docker-compose.activepieces.yml, PR #2906). The
    # pinned 0.86.3 image reads AP_JWT_SECRET for stable auth signing across
    # app+worker restarts (NOT AP_SIGNING_SECRET — that key is ignored by this
    # image). Queue mode note: split app/worker containers require
    # AP_QUEUE_MODE=REDIS in BOTH, set in the overlay.
    "AP_POSTGRES_PASSWORD": {"tier": "worker", "required": False},
    "AP_JWT_SECRET": {"tier": "worker", "required": False, "min_length": 32},
    "AP_ENCRYPTION_KEY": {"tier": "worker", "required": False},
    # min_length=64 is not a style preference -- supabase-realtime is Phoenix, and
    # Plug's cookie store raises at REQUEST time, not boot:
    #   (ArgumentError) cookie store expects conn.secret_key_base to be at least
    #   64 bytes  (plug/lib/plug/session/cookie.ex:184)
    # So the container reports "running", answers 500 to everything, and its health
    # check just accumulates failures. Measured on 4090 2026-08-22: the value was
    # exactly 48 characters and the failing streak stood at 6118.
    #
    # 48 is not arbitrary either -- `secrets-rotate` defaults to LEN=48, so the
    # default mint is 16 characters short of what this specific consumer accepts.
    # Nothing in the pipeline compared the two numbers: `required: True` checks
    # presence and secrets_hardening_audit.py checks that env.supabase holds only
    # placeholders. Neither is a length check. Rotate with LEN=64 or more.
    "SECRET_KEY_BASE": {"tier": "supabase", "required": True, "min_length": 64},
    "VAULT_ENC_KEY": {"tier": "supabase", "required": True},
    "LOGFLARE_PRIVATE_ACCESS_TOKEN": {"tier": "supabase", "required": True},
    "LOGFLARE_PUBLIC_ACCESS_TOKEN": {"tier": "supabase", "required": True},
    # Tier: Supabase — gotrue's outbound mailer credential. Without it gotrue
    # cannot send confirmation or password-reset mail, so signup produces
    # permanently-unconfirmed rows and the only account recovery is the admin
    # API. Only the password is a secret; SMTP_HOST/PORT/USER/ADMIN_EMAIL are
    # plain config and live in env.shared.
    "SMTP_PASS": {"tier": "supabase", "required": False},
    # Tier 5: Agent — E2B agent-sandbox credentials (PR #2982).
    #
    # ROOT CAUSE of the sandbox lane being dark: neither name appeared anywhere
    # in this REGISTRY or in brand_defaults.py. Positive control: 25 other
    # labels were registered here at the time, so the search was working — E2B
    # was simply never funnel-managed. Nothing generated, validated, delivered
    # or rotated it, and the only symptom available was the provider rejecting
    # a request deep inside a provisioning call.
    #
    # There are THREE deployment modes and they need DIFFERENT subsets:
    #   cloud           E2B_API_KEY
    #   selfhost-gcp    E2B_ACCESS_TOKEN  (+ E2B_DOMAIN, non-secret config)
    #   selfhost-local  E2B_API_KEY + E2B_ACCESS_TOKEN
    #                   (+ E2B_API_URL / E2B_DEBUG, non-secret config)
    # Only the two credentials belong here. The URLs, E2B_DOMAIN and E2B_DEBUG
    # are routing config, not secrets, and live in env.shared(.example) —
    # putting plain config through the secrets funnel would make rotation and
    # audit noisier without protecting anything.
    #
    # required=False for both: no single node needs both modes, and under
    # `--merge` (strict) a required slot fails the whole funnel on every node
    # that legitimately lacks it. An absent E2B credential fails loudly at
    # `make -C pmoves sandbox-preflight` (exit 3), not quietly at runtime, so
    # the silence that required=False usually buys does not apply here.
    #
    # min_length is a floor, NOT the shape check. e2b_ + 32 hex = 36 and
    # sk_e2b_ + 32 hex = 39. The failure actually observed on B850 was a
    # 42-character E2B_API_KEY missing its leading "e2" — LONGER than the
    # floor, so min_length would have passed it, exactly as `[ -n "$VAR" ]`
    # did. Prefix + charset + per-mode length are enforced at delivery by
    # pmoves/scripts/e2b_mode.sh; this floor only catches gross truncation.
    "E2B_API_KEY": {"tier": "agent", "required": False, "min_length": 36},
    "E2B_ACCESS_TOKEN": {"tier": "agent", "required": False, "min_length": 39},
}


def snake(label: str) -> str:
    return label.lower()


def build_entry(label: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    tier = spec["tier"]
    source: Dict[str, Any] = {"type": "cgp", "label": label}
    aliases = spec.get("aliases")
    if aliases:
        source["aliases"] = list(aliases)
    entry: Dict[str, Any] = {
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
    min_length = spec.get("min_length")
    if min_length:
        entry["min_length"] = int(min_length)
    return entry


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


# Fields this tool will reconcile on an entry that ALREADY exists.
#
# The add-only pass below is correct for its job and wrong as the whole job: it
# keys on `label not in known`, so a registry entry that gains a NEW CONSTRAINT
# is invisible to it -- the label is already present, nothing is "pending", and
# the tool prints "manifest complete" while the constraint never reaches the
# emitted YAML. A gate that cannot reach the file it gates is not a gate.
#
# Deliberately narrow. `required` and `targets` are NOT reconciled: an operator
# may have tuned those per-node, and silently reverting them to the registry's
# view would be a different bug wearing this one's clothes. Only constraints the
# registry is the sole author of belong here.
RECONCILED_FIELDS = ("min_length",)


def reconcile_entry(existing: Dict[str, Any], spec: Dict[str, Any]) -> List[str]:
    """Bring one existing manifest entry in line with the registry. Returns changes."""
    changes: List[str] = []
    for field in RECONCILED_FIELDS:
        want = spec.get(field)
        have = existing.get(field)
        if want is None and have is None:
            continue
        if want is None:
            del existing[field]
            changes.append(f"{field}: {have} -> (removed)")
        elif have != want:
            existing[field] = want
            changes.append(f"{field}: {have if have is not None else '(unset)'} -> {want}")
    return changes


def entry_label(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    source = entry.get("source")
    if not isinstance(source, dict):
        return ""
    return str(source.get("label") or "")


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

    # Reconcile constraint drift on entries that already exist. Without this the
    # tool is add-only and a registry constraint added to an EXISTING label never
    # lands in the manifest -- see RECONCILED_FIELDS.
    drift: List[str] = []
    for entry in entries:
        label = entry_label(entry)
        spec = REGISTRY.get(label)
        if not spec:
            continue
        probe = dict(entry) if args.check else entry
        for change in reconcile_entry(probe, spec):
            drift.append(f"{label}: {change}")

    if not pending and not drift:
        print("manifest complete: all registry labels present, no constraint drift")
        return 0

    for label, spec in sorted(pending.items()):
        print(f"{'would add' if args.check else 'adding'}: {label} -> tier {spec['tier']}")
    for line in sorted(drift):
        print(f"{'would update' if args.check else 'updating'}: {line}")

    if args.check:
        return 1

    for label, spec in sorted(pending.items()):
        insert_alphabetical(entries, build_entry(label, spec))

    args.manifest.write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(
        f"wrote {args.manifest} (+{len(pending)} entries, "
        f"{len(drift)} constraint update(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
