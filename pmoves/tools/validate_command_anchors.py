#!/usr/bin/env python3
"""
Anchor documented commands to the things they name.

A doc that says `make foo` is a promise. This checks the promise resolves.

WHY THIS EXISTS
---------------
Three failures on 2026-08-08, all the same shape — a doc naming something that
isn't there:

  * `.claude/skills/ci-expedition/SKILL.md` documented a reclaim command that
    `.claude/hooks/pre-tool.sh` blocks on a substring scan. An agent copying it
    got a refusal, nothing ran, and the output still read like cleanup happened.
  * The same skill documented `docker builder prune -af` long after #2473
    superseded it in the canonical script — one of four drifting copies.
  * `pmoves/docs/operations/UP_TARGET_INVENTORY.md` shipped a reproduction
    command that counted the file itself, so its own numbers were unreproducible.

`docs_reconcile.py` does not catch these: it checks *freshness* (commit dates,
staleness), not whether a named thing exists.

A second batch on 2026-08-14, same shape, different surface — documented HTTP
APIs that are not served:

  * `.claude/context/agent-zero-orchestration.md` documented `/mcp/health`,
    `/mcp/agents` and `/mcp/subordinate/create`. None were ever implemented.
    #2449 bannered that file and five others by hand; the same fictional
    `/mcp/*` surface survived in nine more docs the manual pass never reached.
  * `pmoves/docs/infrastructure/github-runner-agent-zero-integration.md` ships
    `curl .../queue/POWERFULMOVES/PMOVES.AI` against `@app.get("/queue/{repository}")`.
    FastAPI's `{param}` is one segment, so the documented call 404s.

Freshness could not see either: both docs were recently edited and confidently
wrong. That is what GHOST_ENDPOINT is for — age is not accuracy.

SCOPE AND TOPOLOGY, NOT JUST DOCKER
-----------------------------------
Make targets reach docker, ssh, python, git, systemd, NATS and each other. An
anchor keyed only to docker would miss most of the surface, so every target is
classified by SCOPE, and remote-scope targets are additionally checked against
the known-node TOPOLOGY (`pmoves/config/fleet-map.yaml`, the per-node scopes in
`pmoves/configs/claws/scopes/`, and `pmoves/config/operator_nodes.yaml`) rather
than against a hardcoded host list.

FINDING CLASSES
---------------
  GHOST_TARGET    a doc backticks `make <t>` and no such target is defined
  GHOST_PATH      a doc cites `<repo file>:<line>` and that file does not exist
                  (line-numbered citations only — a bare path is too often a
                   model name or a runtime dir to be worth flagging)
  UNRUNNABLE_DOC  a documented command matches a damage-control BLOCKED_PATTERN,
                  so following the doc produces a refusal, not an action
  UNKNOWN_HOST    a documented `ssh <host>` names a host absent from the fleet
                  topology (this also catches raw IPs, which must never appear
                  in committed docs)
  GHOST_ENDPOINT  a doc cites `http://<service>:<port>/<path>` against a PMOVES
                  service whose routes we can read, and that service declares no
                  such route -- i.e. the doc documents an API that is not there
  GHOST_ROAD      the damage-control guard offers a `make` target as the
                  "correct path" and no such target exists — a blocked agent is
                  routed into a wall at the moment it is least able to recover
  STALE_BASELINE  a baselined key that no longer occurs — i.e. it was FIXED.
                  Also a failure: leaving it in the file re-accepts the same
                  defect if it returns, which is not "count only goes down".

RATCHET SEMANTICS
-----------------
Findings present when the baseline was taken are recorded in
`pmoves/configs/command_anchors/_known_gaps.yaml` and do not fail the build. Any
finding NOT in the baseline fails. The count only goes down. Same shape as
validate-composes and validate-dockerfile-paths.

Usage:
    python pmoves/tools/validate_command_anchors.py            # gate
    python pmoves/tools/validate_command_anchors.py --json     # machine-readable
    python pmoves/tools/validate_command_anchors.py --write-baseline

Exit codes:
    0 = no findings outside the baseline
    1 = new findings
    2 = error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PMOVES = REPO_ROOT / "pmoves"
BASELINE = PMOVES / "configs" / "command_anchors" / "_known_gaps.yaml"

# Docs whose commands are expected to be live. Archived material is excluded:
# a runbook in docs/archive/ is a record of what was true, not a promise.
DOC_ROOTS = [
    PMOVES / "docs",
    REPO_ROOT / ".claude" / "skills",
    REPO_ROOT / ".claude" / "context",
    REPO_ROOT / ".claude" / "commands",
    REPO_ROOT / ".claude" / "agents",
    REPO_ROOT / "deploy" / "runbooks",
]
# The ALWAYS-LOADED orientation files. An agent entering this repo reads these
# before it reads anything else, so a dead reference here is the highest-cost
# kind there is: first contact is misdirection, the agent improvises, and the
# breakage gets blamed on the model. `.claude/CLAUDE.md` currently tells every
# agent that `make -C pmoves worktree-sitrep-strict` is "authoritative — prefer
# this"; no such target exists.
DOC_FILES = [
    REPO_ROOT / ".claude" / "CLAUDE.md",
    REPO_ROOT / ".claude" / "BOOTSTRAP.md",
    REPO_ROOT / ".claude" / "PATTERNS.md",
    REPO_ROOT / ".claude" / "CATALOG.md",
    REPO_ROOT / ".claude" / "PINOKIO_LAUNCHER_GUIDE.md",
    REPO_ROOT / ".claude" / "README.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "AGENTS.md",
]
# `.claude/learnings/` is deliberately excluded alongside archive/: a learnings
# file records what was true during a past session. It is a log, not a promise.
DOC_EXCLUDE_PARTS = {"archive", "_archive", "node_modules", "pmoves_all_in_one_v10", "learnings"}

# The damage-control guard's routing table. Every `make -C pmoves <t>` it offers
# as a "correct path" is a promise made at the exact moment an agent is blocked
# and least able to recover — so a dead road here routes a well-behaved agent
# into a wall and then blames it for improvising.
GUARD_PATTERNS = REPO_ROOT / ".claude" / "hooks" / "damage-control" / "patterns.yaml"

MAKEFILES = [PMOVES / "Makefile"]

# ── Make target discovery ───────────────────────────────────────────


def _makefiles() -> List[Path]:
    files = [p for p in MAKEFILES if p.is_file()]
    mkdir = PMOVES / "mk"
    if mkdir.is_dir():
        files.extend(sorted(mkdir.glob("*.mk")))
    return files


TARGET_DEF_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.-]*)\s*:(?!=)")


def discover_targets() -> Dict[str, Path]:
    """target name -> file that defines it."""
    found: Dict[str, Path] = {}
    for f in _makefiles():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = TARGET_DEF_RE.match(line)
            if m and not line.startswith("\t"):
                found.setdefault(m.group(1), f)
    return found


# ── Scope classification ────────────────────────────────────────────
# Ordered: first match wins, most specific first. `meta` is the fallback for a
# target whose body only calls other targets.

SCOPE_PATTERNS = [
    ("remote", re.compile(r"\bssh\b|tailscale\s+ssh")),
    ("systemd", re.compile(r"\bsystemctl\b|\bjournalctl\b")),
    ("docker", re.compile(r"\bdocker\b|\$\(DC\)|\$\(OVERLAY_DC\)|docker\s+compose")),
    ("python", re.compile(r"\$\(PYTHON\)|\bpython3?\b|\buv\s+run\b")),
    ("git", re.compile(r"\bgit\s+(submodule|clone|fetch|worktree|checkout)\b")),
    ("nats", re.compile(r"\bnats\b")),
    ("secrets", re.compile(r"secrets[-_]|\bsops\b|\bage\b")),
]


def target_bodies() -> Dict[str, List[str]]:
    """target name -> its recipe lines."""
    bodies: Dict[str, List[str]] = {}
    for f in _makefiles():
        cur = None
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("\t"):
                if cur:
                    bodies.setdefault(cur, []).append(line)
                continue
            m = TARGET_DEF_RE.match(line)
            cur = m.group(1) if m else None
    return bodies


def classify_scope(body: Iterable[str]) -> str:
    text = "\n".join(body)
    for name, pat in SCOPE_PATTERNS:
        if pat.search(text):
            return name
    if "$(MAKE)" in text:
        return "meta"
    return "other"


# ── Topology: known hosts ───────────────────────────────────────────


def known_hosts() -> Set[str]:
    """Hostnames the fleet actually declares. Never a hardcoded list."""
    hosts: Set[str] = set()

    scopes = PMOVES / "configs" / "claws" / "scopes"
    if scopes.is_dir():
        for p in scopes.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            ident = data.get("identity") or {}
            for key in ("hostname", "node"):
                if ident.get(key):
                    hosts.add(str(ident[key]))
            hosts.add(p.stem)

    for rel in ("config/fleet-map.yaml", "config/operator_nodes.yaml"):
        p = PMOVES / rel
        if not p.is_file():
            continue
        # Deliberately regex, not a YAML parse: these files carry PLACEHOLDER
        # values and comments, and a parse failure should not blind the check.
        for m in re.finditer(r"\b(pmoves-[a-z0-9-]+)\b", p.read_text(encoding="utf-8", errors="replace")):
            hosts.add(m.group(1))

    return hosts


# ── Damage-control blocked patterns ─────────────────────────────────


def blocked_patterns() -> List[str]:
    """Read BLOCKED_PATTERNS from the hook rather than restating them here.

    Restating would create exactly the drift this tool exists to detect.
    """
    hook = REPO_ROOT / ".claude" / "hooks" / "pre-tool.sh"
    if not hook.is_file():
        return []
    text = hook.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"BLOCKED_PATTERNS=\((.*?)\)", text, re.S)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


# ── Doc scanning ────────────────────────────────────────────────────


def live_docs() -> List[Path]:
    out: List[Path] = [p for p in DOC_FILES if p.is_file()]
    for root in DOC_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            if DOC_EXCLUDE_PARTS & set(p.parts):
                continue
            out.append(p)
    return out


# Two forms carry a documented make command, and BOTH are executable to a
# reader: an inline span `make foo`, and a bare line inside a fenced block.
# The fenced form is the more common one in runbooks, so keying only on the
# backtick missed most of the surface (caught in review on #2488).
MAKE_CITE_RE = re.compile(r"`make\s+(?:-C\s+[A-Za-z0-9_./-]+\s+)?([a-z][a-z0-9-]{2,})")
MAKE_FENCED_RE = re.compile(r"^\s*(?:\$\s*)?make\s+(?:-C\s+[A-Za-z0-9_./-]+\s+)?([a-z][a-z0-9-]{2,})", re.M)
FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\n(.*?)^```", re.M | re.S)
INLINE_SPAN_RE = re.compile(r"`([^`\n]+)`")
# Only LINE-NUMBERED citations. A bare `pmoves/foo` in a doc is as likely to be
# an ollama model name, a runtime output dir, or a gitignored env file as it is
# a source reference — flagging those buries the signal. "`path:123`" is
# unambiguously a claim about source, and it is the form that goes stale.
PATH_CITE_RE = re.compile(r"`((?:pmoves|deploy|\.claude|\.github)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+):\d+(?:-\d+)?`")
SSH_CITE_RE = re.compile(r"ssh\s+(?:-\S+\s+)*(?:root@|[a-z][a-z0-9_-]*@)?([A-Za-z0-9][A-Za-z0-9._-]+)")


SERVICES = PMOVES / "services"

# FastAPI/Starlette route declarations. One uniform style covers the fleet:
# 59 of 97 service dirs declare routes this way.
ROUTE_DECL_RE = re.compile(
    r"""@(?:\w+)\.(?:get|post|put|delete|patch|head|options|websocket)\(\s*["']([^"']+)["']"""
)

# A service whose real prefix we cannot compute statically would produce false
# GHOST_ENDPOINTs for every route it has, which is worse than no check at all --
# the noise gets baselined and the class stops meaning anything. So a service is
# introspectable ONLY if it declares routes and does NOT relocate them at
# include/mount time.
ROUTE_RELOCATE_RE = re.compile(
    r"APIRouter\([^)]*prefix\s*=|include_router\([^)]*prefix\s*=|\.mount\("
)


# ROUTE_RELOCATE_RE catches routes MOVED to a different path. This catches routes
# we simply cannot see: a router included from outside the service directory
# contributes real routes with no marker in this tree. agent-zero does exactly
# that for /a2a/v1/* via include_router(create_a2a_router()) with no prefix.
ROUTE_EXTERNAL_RE = re.compile(r"include_router\(|\.mount\(")


def complete_route_services() -> Set[str]:
    """Services whose declared route set is provably COMPLETE.

    No include_router, no mount -- every route is an @app decorator in this dir,
    so anything a doc cites that does not match is a ghost, full stop. These
    services do not need the namespace rule, and applying it to them hides real
    findings: botz-gateway serves only /v1/*, /healthz and /metrics, so a doc
    citing botz-gateway:8054/tools is plainly wrong -- but the namespace rule
    stayed silent because the service "owns no /tools namespace".
    """
    out: Set[str] = set()
    if not SERVICES.is_dir():
        return out
    for svc in sorted(SERVICES.iterdir()):
        if not svc.is_dir():
            continue
        external = False
        for py in svc.rglob("*.py"):
            if "test" in py.name or "node_modules" in py.parts:
                continue
            try:
                body = py.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if ROUTE_EXTERNAL_RE.search(body):
                external = True
                break
        if not external:
            out.add(svc.name)
    return out


def service_routes() -> Dict[str, Set[str]]:
    """service dir name -> declared route paths, for services we can read safely."""
    out: Dict[str, Set[str]] = {}
    if not SERVICES.is_dir():
        return out
    for svc in sorted(SERVICES.iterdir()):
        if not svc.is_dir():
            continue
        routes: Set[str] = set()
        relocates = False
        for py in svc.rglob("*.py"):
            if "test" in py.name or "node_modules" in py.parts:
                continue
            try:
                body = py.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if ROUTE_RELOCATE_RE.search(body):
                relocates = True
                break
            routes |= {m.group(1) for m in ROUTE_DECL_RE.finditer(body)}
        if routes and not relocates:
            out[svc.name] = routes
    return out


def _route_matchers(routes: Set[str]) -> List[re.Pattern]:
    """Compile declared routes, treating {param} as one path segment."""
    pats: List[re.Pattern] = []
    for r in routes:
        esc = "".join(
            r"[^/]+" if part.startswith("{") and part.endswith("}") else re.escape(part)
            for part in re.split(r"(\{[^}]+\})", r)
            if part
        )
        pats.append(re.compile(rf"^{esc}/?$"))
    return pats


# Only host:port forms. A bare `/healthz` in prose names no service, and a
# scheme-less path is as often a URL fragment as an API claim.
#
# `<` and `>` MUST stay in the path class even though a bracketed segment is
# never a real route. `<param>` is a normal doc convention, and excluding the
# bracket does not skip the citation -- it TRUNCATES it. `/jobs/<context_id>`
# captured as `/jobs/`, which then failed the matcher for the real route
# `/jobs/{context_id}` and reported a ghost. The placeholder skip below can
# only fire on characters the capture actually kept. A gate that flags correct
# documentation is worse than one that misses: it pushes authors to "fix" docs
# that were right.
ENDPOINT_CITE_RE = re.compile(
    r"https?://([A-Za-z0-9][A-Za-z0-9_.-]*):(\d{2,5})(/[A-Za-z0-9_./{}<>%:-]*)"
)


# Docs overwhelmingly write `http://localhost:8080/...`, not `http://agent-zero:8080/...`
# -- 1574 of the 1732 endpoint citations in the scanned tree take the loopback
# form. Checking only the service-name form would cover 9% of the surface while
# reading like it covered the surface, which is the exact failure this whole
# ratchet exists to stop. So loopback host:port is resolved to a service through
# the compose port map.
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"}

SERVICE_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+):\s*(?:#.*)?$")

COMPOSE_VAR_RE = re.compile(r"\$\{[A-Za-z0-9_]+:-([^}]*)\}")


def host_port_map() -> Dict[str, str]:
    """host port -> service, for ports that name exactly one service.

    Deliberately stdlib-only. The first cut imported yaml behind a try/except
    that returned {} when it was missing. In the CI step documented "stdlib
    only, no network" that did not fail -- it silently produced ZERO loopback
    findings, which then tripped STALE_BASELINE against a baseline recorded on a
    machine that had yaml. A gate whose findings depend on an optional import,
    and degrades quietly when it is absent, is the exact defect this ratchet
    exists to catch. So the port map is parsed directly.

    Only one shape matters and compose writes it consistently:

        services:
          <name>:
            ports:
            - ${BIND:-127.0.0.1}:${PORT:-8080}:8080
            - "9090:9090"

    A port published by more than one service (11434 by two ollamas, 9096 by
    three jellyfins, 80/443 by nginx and traefik) cannot be resolved to a single
    route table, so it is dropped rather than guessed.
    """
    owners: Dict[str, Set[str]] = {}
    for f in sorted(PMOVES.glob("docker-compose*.yml")):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        in_services = False
        svc = ""
        in_ports = False
        for raw in lines:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip())
            stripped = raw.strip()

            if indent == 0:
                in_services = stripped.startswith("services:")
                svc, in_ports = "", False
                continue
            if not in_services:
                continue

            # A 2-space key names a service and ends any previous ports block.
            # The trailing-comment form is real and common --
            #   voice-sampler:  # media-sourced voice references ...
            # -- so an endswith(":") test silently keeps the PREVIOUS service
            # name and files that service's ports under its neighbour. That is
            # the under-collecting direction: it makes a shared port look
            # unambiguous and defeats the ambiguity guard.
            if indent == 2:
                key = SERVICE_KEY_RE.match(stripped)
                if key:
                    svc = key.group(1)
                    in_ports = False
                    continue
            if not svc:
                continue

            if in_ports:
                if stripped.startswith("- "):
                    entry = COMPOSE_VAR_RE.sub(lambda m: m.group(1), stripped[2:])
                    entry = entry.split("#")[0].strip().strip("\"'")
                    parts = entry.split("/")[0].split(":")
                    if len(parts) >= 2 and parts[-2].isdigit():
                        owners.setdefault(parts[-2], set()).add(svc)
                    continue
                in_ports = False  # this line is a sibling key, fall through

            if indent == 4 and stripped == "ports:":
                in_ports = True
                continue

            # Inline flow sequence: ports: ["${BIND:-127.0.0.1}:8055:8055", ...]
            # Used by flute-gateway, traefik and ~20 others. Missing this form
            # made the parser UNDER-collect, which is the dangerous direction:
            # a port published by two services looked like it belonged to one,
            # and the ambiguity guard never fired.
            if indent == 4 and stripped.startswith("ports:") and "[" in stripped:
                inner = stripped[stripped.index("[") + 1:]
                inner = inner.rsplit("]", 1)[0] if "]" in inner else inner
                for item in inner.split(","):
                    entry = COMPOSE_VAR_RE.sub(lambda m: m.group(1), item)
                    entry = entry.strip().strip("\"'")
                    parts = entry.split("/")[0].split(":")
                    if len(parts) >= 2 and parts[-2].isdigit():
                        owners.setdefault(parts[-2], set()).add(svc)
    return {p: next(iter(v)) for p, v in owners.items() if len(v) == 1}


def scan_endpoints(routes_by_svc: Dict[str, Set[str]]) -> List[dict]:
    findings: List[dict] = []
    matchers = {s: _route_matchers(r) for s, r in routes_by_svc.items()}
    complete = complete_route_services()
    ports = host_port_map()
    self_name = Path(__file__).name

    for doc in live_docs():
        rel = doc.relative_to(REPO_ROOT).as_posix()
        if self_name in rel:
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        seen: Set[str] = set()
        for m in ENDPOINT_CITE_RE.finditer(text):
            svc, port, path = m.group(1), m.group(2), m.group(3)
            if svc in LOOPBACK_HOSTS:
                svc = ports.get(port, "")
            if svc not in matchers:
                continue
            path = path.split("?", 1)[0].split("#", 1)[0]
            if path in ("/", ""):
                continue
            # `$` means shell interpolation -- the segment could expand to
            # anything, so there is no claim to check.
            if "$" in path:
                continue
            # `<param>` is NOT skipped. It is a normal doc convention for a path
            # parameter, and it contains no slash, so it matches the `[^/]+` a
            # declared `{param}` compiles to. That keeps both directions honest:
            #   /jobs/<context_id>  matches real /jobs/{context_id}  -> silent
            #   /mcp/task/<id>      matches no declared /mcp route   -> flagged
            # Skipping bracketed paths wholesale would have hidden three real
            # ghosts in the agent command docs.
            if any(p.match(path) for p in matchers[svc]):
                continue
            # SOUNDNESS GATE. A service may include a router defined outside its
            # own directory (agent-zero does exactly this for /a2a/v1/*, via
            # `include_router(create_a2a_router())` with the router living in
            # python.features.a2a.server). Those routes are real and invisible
            # here, so "not in my extracted set" does NOT mean "not served".
            #
            # We only speak where we have standing: flag a path ONLY if the
            # service already declares at least one route in the same top-level
            # namespace. If agent-zero declares /mcp/commands, then /mcp is a
            # namespace it owns and a missing /mcp/tools/list is a real claim.
            # It declares no /a2a/* route, so we stay silent about /a2a/v1/*
            # rather than guess.
            # Services with a provably complete route set skip the namespace
            # rule -- there is nothing unseen to be wrong about.
            if svc not in complete:
                ns = "/" + path.strip("/").split("/", 1)[0]
                if not any(r == ns or r.startswith(ns + "/") for r in routes_by_svc[svc]):
                    continue
            key = f"{svc}{path}"
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "kind": "GHOST_ENDPOINT",
                "doc": rel,
                "detail": key,
                "scope": "http",
            })
    return findings


def scan(targets: Dict[str, Path], scopes: Dict[str, str]) -> List[dict]:
    findings: List[dict] = []
    hosts = known_hosts()
    blocked = blocked_patterns()
    self_name = Path(__file__).name

    for doc in live_docs():
        rel = doc.relative_to(REPO_ROOT).as_posix()
        text = doc.read_text(encoding="utf-8", errors="replace")

        cited: Set[str] = {m.group(1) for m in MAKE_CITE_RE.finditer(text)}
        for block in FENCE_RE.findall(text):
            cited |= {m.group(1) for m in MAKE_FENCED_RE.finditer(block)}
        for t in sorted(cited):
            # `up-<service>` / `overlay-up-<tier>` are placeholders, not targets.
            # The trailing hyphen is the tell.
            if t in targets or t.endswith("-"):
                continue
            findings.append({
                "kind": "GHOST_TARGET",
                "doc": rel,
                "detail": t,
                "scope": "-",
            })

        for m in PATH_CITE_RE.finditer(text):
            cited = m.group(1)
            if (REPO_ROOT / cited).exists():
                continue
            findings.append({"kind": "GHOST_PATH", "doc": rel, "detail": cited, "scope": "-"})

        for pat in blocked:
            # Only flag inside fenced/inline command context, and never flag the
            # tool or the hook itself — both must name the patterns to work.
            if self_name in rel or "hooks/" in rel:
                continue
            # Walk LINES, not spans. A span carries only the command; the
            # discriminator lives on the line around it. Testing the span alone
            # flagged `.claude/PATTERNS.md` and `AGENTS.md`, both of which carry
            # a "| Raw command (blocked) | Known Road |" table — the two docs
            # doing this exactly right.
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                # Documentation ABOUT the guard, not instruction THROUGH it:
                # either it names the Known Road on the same line, or it frames
                # the command as blocked/dangerous.
                if ROAD_IN_LINE_RE.search(line) or DESCRIBES_BLOCK_RE.search(line):
                    continue
                forms = [line] if line.startswith(("$", "ssh ", "docker ", "make ", "sudo ")) else []
                forms.extend(m.group(1) for m in INLINE_SPAN_RE.finditer(line))
                for cand in forms:
                    if pat.lower() in cand.lower():
                        findings.append({
                            "kind": "UNRUNNABLE_DOC",
                            "doc": rel,
                            "detail": f"{pat!r} in: {cand[:80]}",
                            "scope": "docker",
                        })

        for m in SSH_CITE_RE.finditer(text):
            host = m.group(1)
            if host in hosts or host in {"root", "localhost"}:
                continue
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host):
                findings.append({"kind": "UNKNOWN_HOST", "doc": rel, "detail": f"raw IP {host}", "scope": "remote"})
            elif host.startswith("pmoves-") or host.endswith(".ts.net"):
                findings.append({"kind": "UNKNOWN_HOST", "doc": rel, "detail": host, "scope": "remote"})

    # attach scope to ghost targets whose name matches a known family
    for f in findings:
        if f["kind"] == "GHOST_TARGET":
            fam = f["detail"].split("-")[0]
            sibling = next((t for t in targets if t.startswith(fam + "-")), None)
            if sibling:
                f["scope"] = scopes.get(sibling, "-")

    return findings


# ── The guard's own routing table ───────────────────────────────────


GUARD_ROAD_RE = re.compile(r"make\s+-C\s+pmoves\s+([a-z][a-z0-9-]{2,})")
# Placeholders, not targets: the guard writes `up-<service>` to mean "the up-
# target for whatever service you meant". Flagging those would be noise.
GUARD_ROAD_SKIP = {"up-", "up-service"}
# Used to tell "here is the correct path" apart from "run this".
ROAD_IN_LINE_RE = re.compile(r"make\s+-C\s+pmoves\s+[a-z][a-z0-9-]{2,}|/deploy:|Known Road")
# "Blocks: X, Y" / "Raw command (blocked)" / an anti-pattern bullet is a
# description of the wall, not an instruction to walk into it.
DESCRIBES_BLOCK_RE = re.compile(r"\bBlocks?:|\bblocked\b|\bDangerous Operation\b|\bNEVER\b|\banti-pattern\b|\bmass deletion\b|Raw command|❌", re.I)


def scan_guard_roads(targets: Dict[str, Path]) -> List[dict]:
    """A blocked agent is routed by patterns.yaml. Check where it gets sent.

    This is the ratchet aimed one layer inward: the same GHOST_TARGET question,
    asked of the thing that answers the question for everyone else.
    """
    if not GUARD_PATTERNS.is_file():
        return []
    rel = GUARD_PATTERNS.relative_to(REPO_ROOT).as_posix()
    text = GUARD_PATTERNS.read_text(encoding="utf-8", errors="replace")
    findings: List[dict] = []
    for t in sorted({m.group(1) for m in GUARD_ROAD_RE.finditer(text)}):
        if t in targets or t in GUARD_ROAD_SKIP or t.endswith("-"):
            continue
        findings.append({
            "kind": "GHOST_ROAD",
            "doc": rel,
            "detail": f"guard offers `make -C pmoves {t}` as the correct path; no such target",
            "scope": "guard",
        })
    return findings


# ── Baseline ────────────────────────────────────────────────────────


def _key(f: dict) -> str:
    return f"{f['kind']}|{f['doc']}|{f['detail']}"


def load_baseline() -> Set[str]:
    if not BASELINE.is_file():
        return set()
    keys: Set[str] = set()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- "):
            keys.add(line[2:].strip().strip('"'))
    return keys


def write_baseline(findings: List[dict]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Baselined command-anchor gaps — validate_command_anchors.py",
        "#",
        "# Each entry is a doc naming something that does not resolve. They are",
        "# recorded so the gate can be enforced today; they are NOT approved.",
        "# The list may shrink. Adding to it should require saying why.",
        "known_gaps:",
    ]
    for k in sorted({_key(f) for f in findings}):
        lines.append(f'  - "{k}"')
    BASELINE.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    targets = discover_targets()
    if not targets:
        print("ERROR: no make targets discovered — wrong repo root?", file=sys.stderr)
        return 2

    bodies = target_bodies()
    scopes = {t: classify_scope(bodies.get(t, [])) for t in targets}
    findings = scan(targets, scopes) + scan_guard_roads(targets) + scan_endpoints(service_routes())

    if args.write_baseline:
        write_baseline(findings)
        print(f"Baseline written: {len(set(_key(f) for f in findings))} entries -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    baseline = load_baseline()
    live = {_key(f) for f in findings}
    new = [f for f in findings if _key(f) not in baseline]
    # A baselined key that no longer occurs was FIXED. Leaving it in the file
    # would re-accept the same defect if it came back, which contradicts the
    # count-only-down claim this ratchet makes. Surfacing it is what makes the
    # count actually go down instead of merely not going up.
    stale = sorted(baseline - live)

    if args.json:
        print(json.dumps({
            "total": len(findings),
            "baselined": len(findings) - len(new),
            "new": new,
            "stale_baseline": stale,
        }, indent=2))
        return 1 if (new or stale) else 0

    by_scope: Dict[str, int] = {}
    for t, s in scopes.items():
        by_scope[s] = by_scope.get(s, 0) + 1
    print("Make targets by scope: " + ", ".join(f"{k}={v}" for k, v in sorted(by_scope.items())))
    print(f"Anchor findings: {len(findings)} total, {len(findings) - len(new)} baselined, {len(new)} new")

    if stale:
        print(f"\nSTALE BASELINE — {len(stale)} entr{'y' if len(stale) == 1 else 'ies'} no longer occur:")
        for k in stale[:20]:
            print(f"  {k}")
        if len(stale) > 20:
            print(f"  ... and {len(stale) - 20} more")
        print("\nThese were fixed. Drop them so the same defect cannot return silently:")
        print("  make -C pmoves validate-command-anchors-baseline")

    if not new and not stale:
        print("PASS — no findings outside the baseline, no stale entries.")
        return 0

    if not new:
        return 1

    print("\nNEW findings (not in baseline):")
    for f in sorted(new, key=lambda x: (x["kind"], x["doc"])):
        print(f"  {f['kind']:<15} [{f['scope']}] {f['doc']}")
        print(f"                  -> {f['detail']}")
    print("\nFix the doc, or add the target/path it names.")
    print("To accept deliberately: python pmoves/tools/validate_command_anchors.py --write-baseline")
    return 1


if __name__ == "__main__":
    sys.exit(main())
