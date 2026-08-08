"""Regression net for the command-anchor ratchet.

Tests the classifiers and the baseline mechanism against synthetic inputs, so a
change to the tool that stops it finding things fails here rather than silently
passing CI forever.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "validate_command_anchors.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_command_anchors", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_command_anchors"] = mod
    spec.loader.exec_module(mod)
    return mod


vca = _load()


# ── scope classification ────────────────────────────────────────────
# Make targets are not all docker. If this collapses to one scope the tool has
# stopped being topology-aware and the UNKNOWN_HOST check goes with it.


@pytest.mark.parametrize(
    "body,expected",
    [
        (["\t@docker compose up -d nats"], "docker"),
        (["\t@$(DC) --profile agents up -d"], "docker"),
        (["\tssh root@pmoves-kvm4-1 'df -h /'"], "remote"),
        (["\t@systemctl enable --now docker-fleet-cleanup.timer"], "systemd"),
        (["\t@$(PYTHON) $(CURDIR)/tools/x.py"], "python"),
        (["\t@git submodule update --init"], "git"),
        (["\t@$(MAKE) --no-print-directory up-core"], "meta"),
        (["\t@echo hello"], "other"),
    ],
)
def test_scope_classification(body, expected):
    assert vca.classify_scope(body) == expected


def test_remote_beats_docker_when_both_present():
    # An ssh that runs docker on another node is a REMOTE operation — the host
    # is the thing that needs checking, not the docker verb.
    assert vca.classify_scope(["\tssh root@pmoves-kvm4-1 'docker ps'"]) == "remote"


# ── citation regexes ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("run `make up-core` first", ["up-core"]),
        ("run `make -C pmoves validate-composes`", ["validate-composes"]),
        ("`make -C pmoves docker-fleet-cleanup-run`", ["docker-fleet-cleanup-run"]),
        ("make up-core without backticks", []),
    ],
)
def test_make_citation_regex(text, expected):
    assert vca.MAKE_CITE_RE.findall(text) == expected


def test_path_citation_requires_a_line_number():
    """A bare path is too often a model name or runtime dir to flag."""
    assert vca.PATH_CITE_RE.findall("`pmoves/mk/infra.mk:89`") == ["pmoves/mk/infra.mk"]
    # no line number -> not a source citation
    assert vca.PATH_CITE_RE.findall("`pmoves/qwen3-embed-0.6b`") == []
    assert vca.PATH_CITE_RE.findall("`pmoves/data/agentgym/runs/`") == []


def test_path_citation_accepts_a_range():
    assert vca.PATH_CITE_RE.findall("`.github/workflows/x.yml:12-20`") == [".github/workflows/x.yml"]


# ── blocked patterns are READ, not restated ─────────────────────────


def test_blocked_patterns_come_from_the_hook():
    """Restating them in the tool would create the drift the tool detects."""
    src = TOOL.read_text(encoding="utf-8")
    assert "pre-tool.sh" in src
    pats = vca.blocked_patterns()
    # The hook exists in this repo and declares a non-empty list.
    assert isinstance(pats, list)
    if (vca.REPO_ROOT / ".claude" / "hooks" / "pre-tool.sh").is_file():
        assert pats, "hook is present but no patterns parsed — the regex drifted"


# ── topology comes from config, never a hardcoded list ──────────────


def test_known_hosts_are_discovered_not_hardcoded():
    src = TOOL.read_text(encoding="utf-8")
    assert "fleet-map.yaml" in src
    assert "claws" in src
    hosts = vca.known_hosts()
    assert isinstance(hosts, set)


# ── baseline mechanism ──────────────────────────────────────────────


def test_key_is_stable_across_identical_findings():
    a = {"kind": "GHOST_TARGET", "doc": "d.md", "detail": "x", "scope": "-"}
    b = {"kind": "GHOST_TARGET", "doc": "d.md", "detail": "x", "scope": "docker"}
    # scope is descriptive, not part of identity — otherwise reclassifying a
    # target would silently un-baseline every finding attached to it.
    assert vca._key(a) == vca._key(b)


def test_key_separates_different_docs():
    a = {"kind": "GHOST_TARGET", "doc": "a.md", "detail": "x"}
    b = {"kind": "GHOST_TARGET", "doc": "b.md", "detail": "x"}
    assert vca._key(a) != vca._key(b)


# ── the repo's own state ────────────────────────────────────────────


def test_targets_are_discoverable():
    targets = vca.discover_targets()
    assert len(targets) > 100, "target discovery collapsed"
    assert "up-core" in targets


def test_scopes_are_plural_in_practice():
    """Guards against a regex change that lumps everything into one bucket."""
    targets = vca.discover_targets()
    bodies = vca.target_bodies()
    scopes = {vca.classify_scope(bodies.get(t, [])) for t in targets}
    assert len(scopes) >= 4, f"expected a spread of scopes, got {scopes}"


# ── review-driven regressions (#2488) ───────────────────────────────
# Each of these encodes a gap the first revision shipped with.


def test_fenced_make_commands_are_seen():
    """The fenced form is the COMMON one in runbooks and was missed entirely."""
    block = "make up-core\n$ make -C pmoves validate-composes\n"
    found = {m.group(1) for m in vca.MAKE_FENCED_RE.finditer(block)}
    assert found == {"up-core", "validate-composes"}


def test_fence_regex_extracts_block_bodies():
    doc = "text\n```bash\nmake ghost-target\n```\nmore\n"
    blocks = vca.FENCE_RE.findall(doc)
    assert any("ghost-target" in b for b in blocks)


def test_inline_span_regex_finds_prose_commands():
    """A blocked command inline in prose is still copy-pasteable."""
    prose = "To roll back further, `docker volume rm <project>_traefik-acme` \u2014 but only if"
    spans = vca.INLINE_SPAN_RE.findall(prose)
    assert any("docker volume rm" in s for s in spans)


def test_inline_span_does_not_span_newlines():
    assert vca.INLINE_SPAN_RE.findall("`a\nb`") == []


# ── orientation coverage + guard self-check (#2494) ─────────────────


def test_always_loaded_orientation_files_are_scanned():
    """First contact must be verified. .claude/CLAUDE.md tells every agent that
    `worktree-sitrep-strict` is authoritative; no such target exists."""
    docs = {d.as_posix() for d in vca.live_docs()}
    for must in ("CLAUDE.md", "BOOTSTRAP.md", "PATTERNS.md", "AGENTS.md"):
        assert any(d.endswith(must) for d in docs), f"{must} not scanned"


def test_learnings_are_excluded():
    """A learnings file records what was true in a past session. Log, not promise."""
    assert "learnings" in vca.DOC_EXCLUDE_PARTS


def test_guard_routing_table_is_checked():
    """The ratchet aimed one layer inward: where does a blocked agent get sent?"""
    targets = vca.discover_targets()
    findings = vca.scan_guard_roads(targets)
    assert isinstance(findings, list)
    for f in findings:
        assert f["kind"] == "GHOST_ROAD"
        assert f["scope"] == "guard"


def test_guard_road_placeholders_are_not_flagged():
    """`up-<service>` is a placeholder; the trailing hyphen is the tell."""
    assert "up-" in vca.GUARD_ROAD_SKIP


def test_naming_a_road_on_the_line_exempts_it():
    """`.claude/PATTERNS.md` and AGENTS.md carry a blocked-command -> Known Road
    table. Those are the cure; flagging them would punish the docs doing it right."""
    row = "| `docker volume " + "rm` | `make -C pmoves volume-reset SERVICE=...` | `/deploy:services` |"
    assert vca.ROAD_IN_LINE_RE.search(row)


def test_describing_a_block_exempts_it():
    for line in ("# Blocks: dangerous ops, etc.",
                 "| Raw command (blocked) | Known Road |",
                 "- NEVER do this anywhere"):
        assert vca.DESCRIBES_BLOCK_RE.search(line), line


def test_discriminators_carry_no_control_characters():
    """A literal backslash-b in a heredoc escape-interprets to 0x08 and silently
    turns the word boundary into a backspace. That happened here once; the regex
    then matched nothing and the exemption looked broken rather than absent."""
    for rx in (vca.DESCRIBES_BLOCK_RE, vca.ROAD_IN_LINE_RE, vca.GUARD_ROAD_RE):
        assert chr(8) not in rx.pattern
        assert chr(12) not in rx.pattern
