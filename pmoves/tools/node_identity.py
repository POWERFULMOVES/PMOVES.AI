#!/usr/bin/env python3
"""Resolve which node a session is on, and which registered agent it IS.

The launcher selects a ROLE (`--agent node-steward`). That answers "what am I
doing", never "who am I". This module answers the second question, and is the
half `pmoves/config/agent_registry.yaml`'s `topology.node_affinity` was written
for but nothing read.

Two rules, both deliberate:

  1. NORMALISE, never compare raw. `node_affinity: [5090]` is a YAML *integer*
     in 38 registry entries and never equals the string "5090". Every value
     goes through `canonical_node()`.

  2. DECLARE, never infer. Eight registry agents claim the 4090 under one
     spelling or another, so "the agent whose affinity matches this node" is
     ambiguous. The identity comes from `default_identity` in
     `node-vocabulary.yaml` (or the PMOVES_NODE_IDENTITY override) and is then
     VALIDATED against the registry. An unresolvable identity is a stated
     finding with a reason, never a silent fallback.

CLI:
    python pmoves/tools/node_identity.py --harness claude-code
    python pmoves/tools/node_identity.py --format shell   # eval-able exports
    python pmoves/tools/node_identity.py --format cmd     # bare KEY=VALUE for
                                                          # Windows `for /f`
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VOCABULARY_PATH = REPO_ROOT / "pmoves" / "configs" / "node-vocabulary.yaml"
REGISTRY_PATH = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"

# Values declared in the vocabulary that are known NOT to be a single machine.
# Identity never binds to one of these; they are declared so the gate can tell
# "unknown spelling" from "known to be something else".
NON_NODE_KINDS = frozenset({"class", "placeholder", "runner-label", "unresolved"})


def _norm(raw: Any) -> str:
    """Fold a raw node value to its lookup form.

    `str()` first: this is the whole integer fix. Casefold so a hostname
    (`PMOVES-4090`) matches a config spelling (`pmoves-4090`).
    """
    return str(raw).strip().casefold()


@dataclass(frozen=True)
class Node:
    canonical: str
    kind: str
    reach: str | None
    aliases: tuple[str, ...]
    default_identity: dict[str, str]
    # The SIGNING-CARD spelling cipher requires as `agentId`, per harness. It is
    # NOT default_identity: those are registry spellings (claude_b850) and
    # cipher answers 403 to them -- the card is b850-claude. Declared per node in
    # node-vocabulary.yaml, never derived; see that file's header for the
    # harnesses deliberately left out.
    cipher_agent_id: dict[str, str] = field(default_factory=dict)
    # What a session ANNOUNCES. Distinct again from both of the above: the
    # registry key is what node_identity validates, the card is what cipher
    # accepts, and this is what the operator reads. Declared per node, never
    # derived -- deriving it from either of the others is how the drift began.
    display_identity: dict[str, str] = field(default_factory=dict)

    @property
    def is_machine(self) -> bool:
        return self.kind not in NON_NODE_KINDS


def load_vocabulary(path: Path | None = None) -> dict[str, Node]:
    """Return an alias -> Node index. Every alias of every entry is a key."""
    path = path or VOCABULARY_PATH
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    index: dict[str, Node] = {}
    for entry in doc.get("nodes") or []:
        canonical = str(entry["canonical"])
        node = Node(
            canonical=canonical,
            kind=entry.get("kind", "node"),
            reach=entry.get("reach"),
            aliases=tuple(str(a) for a in (entry.get("aliases") or [canonical])),
            default_identity=dict(entry.get("default_identity") or {}),
            cipher_agent_id=dict(entry.get("cipher_agent_id") or {}),
            display_identity=dict(entry.get("display_identity") or {}),
        )
        for alias in (*node.aliases, canonical):
            key = _norm(alias)
            existing = index.get(key)
            if existing is not None and existing.canonical != canonical:
                raise ValueError(
                    f"alias {alias!r} is claimed by both {existing.canonical!r} "
                    f"and {canonical!r} -- an alias must name exactly one node"
                )
            index[key] = node
    return index


def canonical_node(raw: Any, vocab: dict[str, Node] | None = None) -> str | None:
    """Canonical name for any spelling, or None if the spelling is undeclared.

    None means "not in the vocabulary" -- a finding to report, not a value to
    fall back from.
    """
    if raw is None:
        return None
    node = (vocab if vocab is not None else load_vocabulary()).get(_norm(raw))
    return node.canonical if node else None


def this_node(
    vocab: dict[str, Node] | None = None,
    env: dict[str, str] | None = None,
    hostname: str | None = None,
) -> tuple[str | None, str]:
    """Identify the current node. Returns (canonical_or_None, how_or_why).

    PMOVES_NODE_ID is the documented runtime id (AUTOMODE_FLEET_CONFIG.md) and
    wins when set. It is NOT set on every node -- this machine's own
    settings.local.json carries an empty `env` block -- so the hostname is a
    real fallback here, not a theoretical one.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    env = env if env is not None else dict(os.environ)

    declared = env.get("PMOVES_NODE_ID", "").strip()
    if declared:
        canonical = canonical_node(declared, vocab)
        if canonical:
            return canonical, f"PMOVES_NODE_ID={declared}"
        return None, (
            f"PMOVES_NODE_ID={declared!r} is not a declared node name. Add it as "
            f"an alias in {VOCABULARY_PATH.name} rather than leaving it to match "
            f"nothing."
        )

    host = hostname if hostname is not None else socket.gethostname()
    canonical = canonical_node(host, vocab)
    if canonical:
        return canonical, f"hostname={host} (PMOVES_NODE_ID unset)"
    return None, (
        f"PMOVES_NODE_ID is unset and hostname {host!r} is not a declared node "
        f"name. Set PMOVES_NODE_ID, or add the hostname as an alias in "
        f"{VOCABULARY_PATH.name}."
    )


def load_registry(path: Path | None = None) -> dict[str, dict]:
    path = path or REGISTRY_PATH
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    agents = doc.get("agents", doc)
    return {k: v for k, v in agents.items() if isinstance(v, dict)}


def agents_claiming(
    canonical: str,
    registry: dict[str, dict] | None = None,
    vocab: dict[str, Node] | None = None,
) -> list[str]:
    """Registry keys whose node_affinity resolves to `canonical`, sorted.

    Informational: several agents legitimately claim one node. This is what
    makes inference unsafe and declaration necessary.
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    registry = registry if registry is not None else load_registry()
    out = []
    for key, entry in registry.items():
        affinity = (entry.get("topology") or {}).get("node_affinity") or []
        if any(canonical_node(value, vocab) == canonical for value in affinity):
            out.append(key)
    return sorted(out)


def resolve_identity(
    harness: str,
    vocab: dict[str, Node] | None = None,
    registry: dict[str, dict] | None = None,
    env: dict[str, str] | None = None,
    hostname: str | None = None,
) -> tuple[str | None, str | None, str]:
    """Resolve (node, identity, explanation) for `harness` on this node.

    `identity` is None whenever it cannot be established WITHOUT GUESSING, and
    the explanation always says which of the four reasons applies:
      - the node itself is unidentified
      - the node is a placeholder/class, not a machine
      - no identity is declared for this harness on this node
      - one is declared but the registry has no such agent (declared-not-wired)
    """
    vocab = vocab if vocab is not None else load_vocabulary()
    registry = registry if registry is not None else load_registry()
    env = env if env is not None else dict(os.environ)

    node, how = this_node(vocab, env=env, hostname=hostname)
    if node is None:
        return None, None, how

    entry = vocab[_norm(node)]
    if not entry.is_machine:
        return node, None, (
            f"{node!r} is declared as kind={entry.kind!r}, not a machine; "
            f"identity does not bind to it"
        )

    override = env.get("PMOVES_NODE_IDENTITY", "").strip()
    declared = override or entry.default_identity.get(harness, "")
    source = "PMOVES_NODE_IDENTITY" if override else (
        f"{VOCABULARY_PATH.name}: {node}.default_identity.{harness}"
    )

    if not declared:
        known = ", ".join(sorted(entry.default_identity)) or "none"
        return node, None, (
            f"node {node} identified via {how}, but no identity is declared for "
            f"harness {harness!r} (declared harnesses: {known}). Add one to "
            f"{VOCABULARY_PATH.name} or set PMOVES_NODE_IDENTITY."
        )

    if declared not in registry:
        claimants = agents_claiming(node, registry, vocab)
        return node, None, (
            f"identity {declared!r} is declared ({source}) but is not in "
            f"{REGISTRY_PATH.name}. It is declared and not wired -- register it "
            f"before it can bind. Agents that do claim {node}: "
            f"{', '.join(claimants) or 'none'}."
        )

    affinity = (registry[declared].get("topology") or {}).get("node_affinity") or []
    if not any(canonical_node(v, vocab) == node for v in affinity):
        return node, None, (
            f"identity {declared!r} is declared ({source}) but its own "
            f"node_affinity {affinity!r} does not include {node}. Refusing to "
            f"bind an identity to a node it does not claim."
        )

    return node, declared, f"node {node} via {how}; identity {declared} via {source}"


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def resolve_cipher_agent_id(
    harness: str,
    node: str | None,
    vocab: dict[str, Node] | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    """Resolve (cipher agentId, explanation) for `harness` on `node`.

    SEPARATE FROM resolve_identity BY DESIGN. That function answers "which
    registered agent am I", and it works; this one answers "what must I put in
    cipher's `agentId` field", which is a different namespace that happens to
    name the same agent. Folding them together would make one wrong answer look
    like the other -- and the registry spelling IS the wrong answer here, which
    is how it survived: every launcher passed claude_b850 to the carry check and
    read a false `signing card: no` back.

    None is returned whenever the answer is not DECLARED. There is a tempting
    transform -- claude_<x> -> <x>-claude holds for all four claude-code nodes --
    and it is wrong for the fifth harness on the first node it meets: knuckles'
    crush identity is crush_glm52 and its card is plain `crush`. A session told
    to declare its own agentId is better off than one told a spelling cipher
    refuses.

    PMOVES_CIPHER_AGENT_ID overrides, matching how PMOVES_NODE_IDENTITY works
    for the registry identity: the operator is allowed to know better.
    """
    env = os.environ if env is None else env

    override = (env.get("PMOVES_CIPHER_AGENT_ID") or "").strip()
    if override:
        return override, f"cipher agentId {override!r} set by PMOVES_CIPHER_AGENT_ID"

    if not node:
        return None, "no cipher agentId: the node itself is unidentified"

    vocab = load_vocabulary() if vocab is None else vocab
    entry = vocab.get(_norm(node))
    if entry is None:
        return None, f"no cipher agentId: {node!r} is not in the node vocabulary"

    declared = (entry.cipher_agent_id.get(harness) or "").strip()
    if not declared:
        return None, (
            f"no cipher agentId declared for harness {harness!r} on {entry.canonical!r}. "
            "Cipher requires one on every call, so declare it per call or add it to "
            "node-vocabulary.yaml -- it is NOT the registry identity, and it is not "
            "derivable from it."
        )
    return declared, f"cipher agentId {declared!r} declared for {harness!r} on {entry.canonical!r}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--harness", default="claude-code",
        help="which harness is asking (default: claude-code)",
    )
    parser.add_argument(
        "--shell", action="store_true",
        help="emit eval-able POSIX exports instead of a human line",
    )
    parser.add_argument(
        "--format", choices=("human", "shell", "cmd"), default=None,
        help=(
            "output form. `cmd` emits UNQUOTED KEY=VALUE for Windows `for /f` "
            "-- cmd.exe has no eval and would take POSIX quotes literally, so "
            "the .bat launcher cannot consume --shell"
        ),
    )
    args = parser.parse_args(argv)

    fmt = args.format or ("shell" if args.shell else "human")
    node, identity, why = resolve_identity(args.harness)
    cipher_id, cipher_why = resolve_cipher_agent_id(args.harness, node)

    if fmt in ("shell", "cmd"):
        # Always emit both, empty when unresolved: a consumer that tests for
        # emptiness behaves correctly, and one that forgets to test gets an
        # empty string rather than a stale value from the parent environment.
        # OUTPUT NAMES ARE DISTINCT FROM THE INPUT OVERRIDE, deliberately.
        # PMOVES_NODE_IDENTITY is what an operator SETS to force an identity.
        # Emitting the result under that same name means a caller that clears
        # its variables before invoking this tool destroys the override it was
        # about to honour -- which is exactly what the Windows launcher did
        # until running it caught the override being silently ignored.
        quote = _shell_quote if fmt == "shell" else (lambda v: v)
        print(f"PMOVES_NODE={quote(node or '')}")
        print(f"PMOVES_RESOLVED_IDENTITY={quote(identity or '')}")
        print(f"PMOVES_IDENTITY_WHY={quote(why)}")
        # Emitted on every path, empty when undeclared, with its own reason:
        # "cipher wants an agentId and I do not have one" and "cipher wants an
        # agentId and here it is" must not look alike to the launcher.
        print(f"PMOVES_CIPHER_AGENT_ID={quote(cipher_id or '')}")
        print(f"PMOVES_CIPHER_AGENT_WHY={quote(cipher_why)}")
        return 0

    print(why)
    print(cipher_why)
    return 0 if identity else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
