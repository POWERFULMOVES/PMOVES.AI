#!/usr/bin/env python3
"""Resolve which node a session is on, and which registered agent it IS.

A launcher may select a ROLE (`--agent node-steward`; since 2026-10-01 only on
request -- the default main session carries no agent). A role answers "what am
I doing", never "who am I". This module answers the second question, and is the
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
# The register-identity vocabulary: who an agent IS in the claim register, as
# opposed to which registry key it is (above) or which cipher card it signs with.
IDENTITY_VOCABULARY_PATH = REPO_ROOT / "pmoves" / "config" / "identity_vocabulary.yaml"

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
      - the node's DEFAULT does not claim the node in its node_affinity

    AFFINITY IS A PREFERENCE (operator correction 2026-10-08; agent_registry.yaml
    says so of claude_b850 itself: "a preference, not an exclusive claim").
    Identity is the aggregate -- card, signature, alters, roles, lineage, ACK
    trail -- and the node is a fact about the session, never a permission to be
    the identity. So an identity DECLARED for this session (PMOVES_NODE_IDENTITY
    naming a registered agent) binds on any machine node, and the explanation
    records it as off-affinity. The auto-binding of the node's default_identity,
    when nothing is declared, still requires affinity: that is the node vouching
    for its own default, not a session declaring who it is. NOTE: declaring is
    attribution, not authentication -- an env var names the identity and nothing
    here proves the session holds it.
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
        if override:
            return node, declared, (
                f"node {node} via {how}; identity {declared} via {source}, "
                f"off-affinity on {node} (node_affinity {affinity!r} is a preference)"
            )
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
    identity: str | None = None,
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

    A WORN IDENTITY CARRIES ITS OWN CARD. `cipher_agent_id` is declared per node
    per harness, beside that node's `default_identity`, so it names the card of
    the node's DEFAULT. When `identity` (the registry identity actually bound) is
    not that default -- a PMOVES_NODE_IDENTITY override, or an identity worn on a
    node that has its own default (A.12 multiplicity) -- the node's declaration
    is the wrong card: a session bound as claude_b850 would write memory as the
    node's own agent. The answer is then the cipher_agent_id declared beside
    `identity` on the node(s) whose default it IS -- still declared, never
    derived. No such node, or two that disagree, yields None with the reason.
    `identity=None` keeps the node-default lookup unchanged.
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

    if identity and entry.default_identity.get(harness) != identity:
        # vocab is an alias index, so one node appears once per alias; keying
        # on canonical collapses that.
        homes = {
            n.canonical: (n.cipher_agent_id.get(harness) or "").strip()
            for n in vocab.values()
            if n.default_identity.get(harness) == identity
        }
        cards = sorted({card for card in homes.values() if card})
        if len(cards) == 1:
            return cards[0], (
                f"cipher agentId {cards[0]!r} declared beside {identity!r} on "
                f"{', '.join(sorted(homes))}; worn on {entry.canonical!r}, whose own "
                f"{harness!r} default is {entry.default_identity.get(harness)!r}"
            )
        if len(cards) > 1:
            return None, (
                f"no cipher agentId: {identity!r} is declared with conflicting cards "
                f"{cards} across {sorted(homes)}. Set PMOVES_CIPHER_AGENT_ID."
            )
        return None, (
            f"no cipher agentId for {identity!r}: it is not {entry.canonical!r}'s "
            f"{harness!r} default, and no node declares a cipher_agent_id beside it in "
            f"{VOCABULARY_PATH.name}. The node's own card would name a different agent; "
            f"set PMOVES_CIPHER_AGENT_ID."
        )

    declared = (entry.cipher_agent_id.get(harness) or "").strip()
    if not declared:
        return None, (
            f"no cipher agentId declared for harness {harness!r} on {entry.canonical!r}. "
            "Cipher requires one on every call, so declare it per call or add it to "
            "node-vocabulary.yaml -- it is NOT the registry identity, and it is not "
            "derivable from it."
        )
    return declared, f"cipher agentId {declared!r} declared for {harness!r} on {entry.canonical!r}"


def _fold_identity(raw: Any) -> str:
    """Same fold identity_lineage._norm applies to author strings, so a name
    this resolver hands a session is looked up exactly as the collision gate
    will look it up when the session signs with it."""
    text = str(raw).strip().replace("\u2192", "->")
    return " ".join(text.split()).casefold()


def resolve_register_name(
    registry_identity: str | None,
    node: str | None,
    vocab: dict[str, Node] | None = None,
    env: dict[str, str] | None = None,
    path: Path | None = None,
) -> tuple[str | None, str | None, str]:
    """Resolve (name, register_form, explanation) for the identity a session IS.

    THE THIRD NAMESPACE. resolve_identity answers "which registry key"
    (claude_b850); resolve_cipher_agent_id answers "which cipher card"
    (b850-claude). Neither is the name the fleet uses for the agent --
    `B850-CLAUDE`, signing the register as `B850-CLAUDE (Knuckles)` -- and a
    launcher that only knows those two told its session "your registered
    identity is claude_b850 ... your selected role is node-steward". The session
    then woke up as the ROLE and spoke of B850-CLAUDE in the third person as the
    party directing it. Operator direction 2026-09-27: the session must wake up
    AS the identity, doing the steward job.

    DECLARED ONLY. `register_form` is read from identity_vocabulary.yaml and
    `name` is its base (the part before any parenthetical). There is no
    transform from claude_b850 that yields `B850-CLAUDE (Knuckles)` while
    yielding the bare `Z890-CLAUDE` the z890 actually signs with, so none is
    attempted: an identity without a register_form returns None with the reason.

    THE SECOND-SESSION RULE. identity_vocabulary.yaml requires a second steward
    session on one node to use a distinct BASE identity. PMOVES_REGISTER_IDENTITY
    names it (e.g. B850-CLAUDE-FUNNEL). It must resolve in the vocabulary, be
    declared for THIS node, and carry a register_form -- otherwise None, never a
    fallback to the primary's name, because falling back is exactly how two
    sessions end up signing one owner string. That rule is about the override,
    not about the identity: the override renames only the register owner string,
    so it stays scoped to identities declared for this node.

    NO NODE GATE ON THE IDENTITY (operator correction 2026-10-08). Identity is the
    aggregate -- card, signature, alters, roles, lineage, ACK trail -- and the
    node is a FACT about the session, never a permission to be the identity. On
    its home node an identity signs its declared register_form, unchanged. Off
    it, the owner string is `<BASE> (<fact>)`, which keeps the identity and
    records where it was worn -- and keeps two concurrent sessions of one
    identity on two nodes from signing one owner string:
      - `<fact>` is the declared token, verbatim, when exactly one
        `node_relations` row in identity_vocabulary.yaml has `node` = this node
        and `mirrored_from` = the identity's home (both via canonical_node). That
        table's doctrine block: "an identity worn on hardware that is not its
        home node ... where it was worn is a separate fact worth keeping";
        ledger example `CLAUDE-OPUS (Z890-mirror-on-5090)`.
      - otherwise the node's canonical name from node-vocabulary.yaml. Not an
        invented spelling: identity_vocabulary.yaml's parenthetical doctrine
        lists the node as one of the parenthetical's declared kinds (`Z890`,
        `SPARK`, `Knuckles`), and identity_lineage.wearing() parses any node
        alias there as `node`. Two rows for one mirror is ambiguous, so neither
        token is used and the explanation names both.
    canonical_identity() folds every one of these forms back to the same
    identity. The table is read from the same document as `identities` rather
    than through identity_lineage's loader, which caches the real file
    module-wide and cannot be pointed at `path`.
    """
    env = os.environ if env is None else env
    path = path or IDENTITY_VOCABULARY_PATH

    if not node:
        return None, None, "no register name: the node itself is unidentified"
    try:
        with open(path, encoding="utf-8") as handle:
            doc = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        return None, None, f"no register name: cannot read {path.name} ({exc})"

    index: dict[str, dict] = {}
    for entry in doc.get("identities") or []:
        if not isinstance(entry, dict) or "canonical" not in entry:
            continue
        for alias in (*(entry.get("aliases") or []), entry["canonical"]):
            index.setdefault(_fold_identity(alias), entry)

    override = (env.get("PMOVES_REGISTER_IDENTITY") or "").strip()
    wanted = override or (registry_identity or "")
    source = "PMOVES_REGISTER_IDENTITY" if override else f"registry identity {registry_identity!r}"
    if not wanted:
        return None, None, "no register name: no registry identity resolved to look up"

    entry = index.get(_fold_identity(wanted))
    if entry is None:
        return None, None, (
            f"no register name: {wanted!r} ({source}) is not an identity or alias "
            f"in {path.name}"
        )
    canonical = str(entry["canonical"])

    vocab = vocab if vocab is not None else load_vocabulary()
    entry_node = canonical_node(entry.get("node"), vocab)
    here = canonical_node(node, vocab)
    if override and entry_node != here:
        # The second-session rule, unchanged. Not a node gate on the identity:
        # the override renames only the register owner string, so a foreign
        # BASE would sign as one aggregate while cipher and the registry carry
        # another. Wearing another identity is PMOVES_NODE_IDENTITY.
        return None, None, (
            f"no register name: identity {canonical!r} ({source}) is declared for "
            f"node {entry.get('node')!r}, not {node!r}. PMOVES_REGISTER_IDENTITY "
            f"names a second session's BASE on its own node; to wear another "
            f"identity, set PMOVES_NODE_IDENTITY."
        )
    if here is None:
        return None, None, (
            f"no register name: {node!r} is not a declared node, so the session's "
            f"node cannot be recorded in its owner string"
        )

    form = str(entry.get("register_form") or "").strip()
    if not form:
        return None, None, (
            f"no register name: identity {canonical!r} ({source}) has no "
            f"register_form in {path.name}. Declare the exact owner string it signs "
            f"the register with; it is not derived."
        )
    name = form.split("(", 1)[0].strip()

    if entry_node != here:
        tokens = sorted(
            str(r["token"]) for r in doc.get("node_relations") or []
            if isinstance(r, dict) and r.get("token")
            and entry_node is not None
            and canonical_node(r.get("node"), vocab) == here
            and canonical_node(r.get("mirrored_from"), vocab) == entry_node
        )
        fact = tokens[0] if len(tokens) == 1 else here
        worn = f"{name} ({fact})"
        if len(tokens) == 1:
            how = f"node_relations token {fact!r}"
        elif tokens:
            how = (f"node {here} -- {len(tokens)} node_relations tokens declared for "
                   f"this mirror ({', '.join(tokens)}), so none is used")
        else:
            how = f"node {here}"
        return name, worn, (
            f"register name {name!r} (signs as {worn!r}) from {path.name}: "
            f"{canonical} (home {entry_node or 'undeclared'}) worn on {here}, "
            f"recorded via {how}; via {source}"
        )
    return name, form, (
        f"register name {name!r} (signs as {form!r}) from {path.name}: "
        f"{canonical}.register_form via {source}"
    )


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
    cipher_id, cipher_why = resolve_cipher_agent_id(args.harness, node, identity=identity)
    # Only looked up for a BOUND identity: naming a session whose registry
    # identity did not resolve would put a name on an unbound session.
    if identity:
        reg_name, reg_form, reg_why = resolve_register_name(identity, node)
    else:
        reg_name, reg_form, reg_why = None, None, "no register name: identity unresolved"

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
        # The name the session IS, and the owner string it signs with. Empty
        # with a reason when undeclared, like the cipher pair above.
        print(f"PMOVES_IDENTITY_NAME={quote(reg_name or '')}")
        print(f"PMOVES_REGISTER_FORM={quote(reg_form or '')}")
        print(f"PMOVES_REGISTER_WHY={quote(reg_why)}")
        return 0

    print(why)
    print(cipher_why)
    print(reg_why)
    return 0 if identity else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
