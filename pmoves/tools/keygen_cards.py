"""Signing-card key generation backed by pmoves-keygen (charmbracelet fork).

Generates Ed25519 SSH key pairs and auto-populates the machine-loadable
(ml) halves of pmoves/config/signing_identity_cards.yaml:

    ml:
      primary_method: ssh
      ssh_fingerprint: "SHA256:..."
      ssh_allowed_signers_line: "<agent_id> ssh-ed25519 AAAA... pmoves@pmoves.ai"

Also supports a plain SSH-auth mode that emits fleet-access keypairs via
the *_FILE secrets-funnel pattern.

Passphrases are resolved from (in order):
    1. --passphrase-env VAR   (recommended; e.g. CHIT_SIGNING_KEY_PASSPHRASE)
    2. KEYGEN_PASSPHRASE
Never a CLI argument, so they stay out of shell history and process
listings.

Usage:
    python3 -m pmoves.tools.keygen_cards generate --agent crush
    python3 -m pmoves.tools.keygen_cards generate --agent hermes --dry-run
    python3 -m pmoves.tools.keygen_cards ssh-auth --name jetson-1
    python3 -m pmoves.tools.keygen_cards audit
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CARDS_PATH = REPO_ROOT / "pmoves" / "config" / "signing_identity_cards.yaml"
KEYGEN_REPO = REPO_ROOT / "pmoves-keygen"
DEFAULT_KEY_DIR = REPO_ROOT / "pmoves" / "chit" / "keys"

COMMENT_SUFFIX = "pmoves@pmoves.ai"


@dataclass
class KeyArtifacts:
    authorized_key: str  # "ssh-ed25519 AAAA... name"
    fingerprint: str  # "SHA256:..."
    key_type: str
    private_key_path: Path
    public_key_path: Path


def _resolve_cli() -> str:
    """Locate or build the keygen-cli binary from the pmoves-keygen submodule."""
    binary = KEYGEN_REPO / "keygen-cli"
    if not binary.exists():
        subprocess.run(
            ["go", "build", "-o", str(binary), "./cmd/keygen-cli"],
            cwd=KEYGEN_REPO,
            check=True,
            capture_output=True,
        )
    return str(binary)


def _passphrase_from(args: argparse.Namespace) -> str | None:
    if args.passphrase_env:
        return os.environ.get(args.passphrase_env) or None
    return os.environ.get("KEYGEN_PASSPHRASE") or None


def generate_key(path: Path, args: argparse.Namespace) -> KeyArtifacts:
    """Generate a keypair at path via keygen-cli, returning parsed artifacts."""
    env = dict(os.environ)
    passphrase = _passphrase_from(args)
    if passphrase:
        env["KEYGEN_PASSPHRASE"] = passphrase

    result = subprocess.run(
        [_resolve_cli(), str(path)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    fields = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()

    return KeyArtifacts(
        authorized_key=fields["authorized_key"],
        fingerprint=fields["fingerprint"],
        key_type=fields["key_type"],
        private_key_path=path,
        public_key_path=Path(str(path) + ".pub"),
    )


def _load_cards() -> tuple[Any, str]:
    """Minimal YAML handling with comment preservation via ruamel if available."""
    try:
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.preserve_quotes = True
        data = yaml.load(CARDS_PATH.read_text())
        return data, "ruamel"
    except ImportError:
        import yaml

        data = yaml.safe_load(CARDS_PATH.read_text())
        return data, "plain"


def cmd_generate(args: argparse.Namespace) -> int:
    data, mode = _load_cards()
    cards = data.get("cards", [])
    card = next((c for c in cards if c.get("h", {}).get("agent_id") == args.agent), None)
    if card is None:
        print(f"error: no signing card with agent_id '{args.agent}'", file=sys.stderr)
        print(
            f"       known: {', '.join(sorted(c.get('h', {}).get('agent_id', '?') for c in cards))}",
            file=sys.stderr,
        )
        return 1

    DEFAULT_KEY_DIR.mkdir(parents=True, exist_ok=True)
    key_path = DEFAULT_KEY_DIR / f"{args.agent}-signing"
    if key_path.exists():
        print(f"error: key already exists at {key_path} (refusing to overwrite)", file=sys.stderr)
        return 1

    artifacts = generate_key(key_path, args)

    # Rebuild the allowed-signers line with the card's agent principal and
    # the PMOVES comment, per the 5x5 signing-card contract.
    parts = artifacts.authorized_key.split()
    keytype, blob = parts[0], parts[1]
    allowed_signers = f"{args.agent} {keytype} {blob} {COMMENT_SUFFIX}"

    print(f"card_id:      {card.get('card_id')}")
    print(f"agent:        {args.agent}")
    print(f"fingerprint:  {artifacts.fingerprint}")
    print(f"private key:  {artifacts.private_key_path}")
    print(f"public key:   {artifacts.public_key_path}")
    print(f"ml patch:")
    print(f"  ssh_fingerprint: \"{artifacts.fingerprint}\"")
    print(f"  ssh_allowed_signers_line: \"{allowed_signers}\"")

    if args.dry_run:
        print("\n(dry-run: cards file untouched; private key kept for inspection)")
        return 0

    if mode == "ruamel":
        ml = card.setdefault("ml", {})
        ml["primary_method"] = "ssh"
        ml["ssh_fingerprint"] = artifacts.fingerprint
        ml["ssh_allowed_signers_line"] = allowed_signers
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # never wrap the long allowed-signers line
        with CARDS_PATH.open("w") as fh:
            yaml.dump(data, fh)
        print(f"\npatched {CARDS_PATH}")
        return 0

    print(
        "\nnote: ruamel.yaml not installed — apply the ml patch above by hand "
        "(pip install ruamel.yaml for auto-patch)",
        file=sys.stderr,
    )
    return 2


def cmd_ssh_auth(args: argparse.Namespace) -> int:
    """Generate a fleet SSH-access keypair for a node/agent."""
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_KEY_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    key_path = out_dir / args.name
    if key_path.exists():
        print(f"error: key already exists at {key_path}", file=sys.stderr)
        return 1

    artifacts = generate_key(key_path, args)
    print(json.dumps({
        "name": args.name,
        "authorized_key": artifacts.authorized_key,
        "fingerprint": artifacts.fingerprint,
        "private_key_path": str(artifacts.private_key_path),
        "public_key_path": str(artifacts.public_key_path),
        "secrets_funnel_hint": f"point a *_FILE variable at {artifacts.private_key_path}",
    }, indent=2))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Report which cards still lack their ml SSH half."""
    import yaml

    data = yaml.safe_load(CARDS_PATH.read_text())
    pending, complete = [], []
    for card in data.get("cards", []):
        agent = card.get("h", {}).get("agent_id", "?")
        ml = card.get("ml", {}) or {}
        has_ssh = bool(ml.get("ssh_fingerprint") and ml.get("ssh_allowed_signers_line"))
        (complete if has_ssh else pending).append(agent)
    print(f"complete ({len(complete)}): {', '.join(sorted(complete)) or '-'}")
    print(f"pending-ml ({len(pending)}): {', '.join(sorted(pending)) or '-'}")
    print("\nnext: python3 -m pmoves.tools.keygen_cards generate --agent <id>")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--passphrase-env", help="env var holding the key passphrase")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("generate", help="generate + patch a signing card's ml half")
    p_gen.add_argument("--agent", required=True, help="agent_id from signing_identity_cards.yaml")
    p_gen.add_argument("--dry-run", action="store_true")
    p_gen.set_defaults(func=cmd_generate)

    p_ssh = sub.add_parser("ssh-auth", help="generate a fleet SSH-access keypair")
    p_ssh.add_argument("--name", required=True, help="node/agent name (e.g. jetson-1)")
    p_ssh.add_argument("--out-dir")
    p_ssh.set_defaults(func=cmd_ssh_auth)

    p_aud = sub.add_parser("audit", help="list cards missing their ml SSH half")
    p_aud.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
