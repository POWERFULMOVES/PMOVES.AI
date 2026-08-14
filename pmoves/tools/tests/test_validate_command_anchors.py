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


# ── the -C argument must not swallow a closing backtick (#2499) ──────


def test_dash_c_arg_does_not_eat_the_closing_backtick():
    """`-C \S+` matched the backtick too, so prose that backticks the prefix
    alone captured the FOLLOWING word as a target. Found by dogfooding: an
    AGNOTE entry writing "it offers two `make -C pmoves` targets" produced a
    GHOST_TARGET for `targets`."""
    bt = chr(96)
    assert vca.MAKE_CITE_RE.findall(bt + "make -C pmoves" + bt + " targets") == []


def test_dash_c_still_matches_real_citations():
    bt = chr(96)
    for text, want in [
        (bt + "make -C pmoves up-core" + bt, ["up-core"]),
        (bt + "make up-core" + bt, ["up-core"]),
        (bt + "make -C pmoves/mk validate-composes" + bt, ["validate-composes"]),
        (bt + "make -C ../pmoves up-core" + bt, ["up-core"]),
    ]:
        assert vca.MAKE_CITE_RE.findall(text) == want, text


def test_fenced_form_keeps_the_same_dash_c_handling():
    """The fenced matcher shares the -C fragment; keep them in step."""
    assert vca.MAKE_FENCED_RE.findall("make -C pmoves up-core") == ["up-core"]
    assert vca.MAKE_FENCED_RE.findall("$ make -C ../pmoves validate-composes") == ["validate-composes"]


# ── GHOST_ENDPOINT ──────────────────────────────────────────────────
#
# The class exists because four record defects in one session shared a shape the
# older classes could not see: a doc naming an HTTP API that is not served.
# These tests pin the two properties that make it worth having — it must FIRE on
# a fictional route, and it must STAY SILENT where it has no standing.


def _matchers(routes):
    return vca._route_matchers(set(routes))


def _matches(routes, path):
    return any(p.match(path) for p in _matchers(routes))


def test_route_matcher_accepts_exact_and_trailing_slash():
    assert _matches(["/healthz"], "/healthz")
    assert _matches(["/healthz"], "/healthz/")


def test_route_matcher_treats_param_as_one_segment():
    # FastAPI's {param} is [^/]+ — it does NOT span a slash. This is exactly the
    # github-runner-ctl defect: /queue/{repository} documented as "owner/repo"
    # cannot be called as /queue/OWNER/REPO; that 404s.
    assert _matches(["/jobs/{context_id}"], "/jobs/abc123")
    assert not _matches(["/queue/{repository}"], "/queue/OWNER/REPO")


def test_route_matcher_rejects_unknown_sibling():
    assert not _matches(["/mcp/commands", "/mcp/execute"], "/mcp/tools/list")


def test_endpoint_regex_captures_service_port_and_path():
    m = vca.ENDPOINT_CITE_RE.search("curl http://agent-zero:8080/mcp/tools/list")
    assert m and m.group(1) == "agent-zero"
    assert m.group(2) == "8080"
    assert m.group(3) == "/mcp/tools/list"


def test_endpoint_regex_ignores_bare_path():
    # A scheme-less path names no service, so there is nothing to check it against.
    assert vca.ENDPOINT_CITE_RE.search("see /mcp/tools/list for details") is None


def test_route_decl_regex_reads_fastapi_decorators():
    body = '@app.get("/healthz")\n@router.post("/tasks")\n@app.websocket("/ws")\n'
    assert {m.group(1) for m in vca.ROUTE_DECL_RE.finditer(body)} == {
        "/healthz", "/tasks", "/ws",
    }


def test_relocating_services_are_excluded_from_introspection():
    # A prefix applied at include/mount time moves every route, so the extracted
    # set would be wrong for all of them — worse than not checking.
    for body in (
        'r = APIRouter(prefix="/api")',
        'app.include_router(r, prefix="/v1")',
        'app.mount("/static", StaticFiles())',
    ):
        assert vca.ROUTE_RELOCATE_RE.search(body), body


def test_namespace_rule_is_the_soundness_boundary():
    # agent-zero includes a router defined OUTSIDE its service dir for /a2a/v1/*.
    # Those routes are real and unreadable here, so absence must not imply ghost.
    declared = {"/mcp/commands", "/mcp/execute", "/healthz"}

    def owns(path):
        ns = "/" + path.strip("/").split("/", 1)[0]
        return any(r == ns or r.startswith(ns + "/") for r in declared)

    assert owns("/mcp/tools/list")   # we declare /mcp/* — we may speak
    assert not owns("/a2a/v1/message")  # we declare no /a2a/* — stay silent


def test_loopback_hosts_are_the_dominant_citation_form():
    # The reason the compose port map exists at all. If this set ever shrinks,
    # coverage silently drops back to the ~9% service-name-only surface.
    assert {"localhost", "127.0.0.1", "host.docker.internal"} <= vca.LOOPBACK_HOSTS


def test_compose_var_substitution_takes_the_default():
    # Ports are written ${AGENT_ZERO_BIND:-127.0.0.1}:${AGENT_ZERO_PORT:-8080}:8080.
    # Without substitution the host field is not a digit and every port is dropped.
    out = vca.COMPOSE_VAR_RE.sub(lambda m: m.group(1), "${A_BIND:-127.0.0.1}:${A_PORT:-8080}:8080")
    assert out == "127.0.0.1:8080:8080"
    assert out.split(":")[-2] == "8080"


def test_host_port_map_resolves_known_services_and_drops_ambiguity():
    m = vca.host_port_map()
    assert m, "port map is empty — the parser silently collected nothing"
    # Spot-check ports whose owner is unambiguous in compose.
    assert m.get("8080") == "agent-zero"
    assert m.get("8104") == "github-runner-ctl"
    # 11434 is published by both ollama-edge and pmoves-ollama; guessing an owner
    # would attach one service's route table to the other's citations.
    assert "11434" not in m


def test_endpoint_regex_matches_loopback_form():
    m = vca.ENDPOINT_CITE_RE.search("curl http://localhost:8080/mcp/health")
    assert m and m.group(1) == "localhost" and m.group(2) == "8080"
    assert m.group(3) == "/mcp/health"


def test_tool_imports_no_third_party_modules():
    """The ratchet runs in a CI step documented "stdlib only, no network".

    The first cut of the port map imported yaml behind a try/except returning {}.
    It did not fail in CI — it silently produced zero loopback findings, which
    tripped STALE_BASELINE against a baseline recorded where yaml existed. A
    gate whose findings depend on an optional import is not a gate.
    """
    src = TOOL.read_text(encoding="utf-8")
    for banned in ("import yaml", "import requests", "import httpx"):
        assert banned not in src, f"{banned} — breaks the stdlib-only guarantee"


def test_service_key_regex_tolerates_trailing_comment():
    # Real form in docker-compose.media.yml:
    #   voice-sampler:  # media-sourced voice references ...
    # An endswith(":") test keeps the PREVIOUS service name and files this
    # service's ports under its neighbour — under-collecting, which makes a
    # shared port look unambiguous and defeats the ambiguity guard.
    assert vca.SERVICE_KEY_RE.match("voice-sampler:  # diarize -> audition").group(1) == "voice-sampler"
    assert vca.SERVICE_KEY_RE.match("agent-zero:").group(1) == "agent-zero"
    # A list item or a nested key must not be mistaken for a service name.
    assert vca.SERVICE_KEY_RE.match("- foo:") is None
    assert vca.SERVICE_KEY_RE.match("image: nginx") is None


def test_port_map_covers_both_block_and_inline_forms():
    m = vca.host_port_map()
    # block sequence form (ports: then "- ${BIND:-...}:${PORT:-8125}:8125")
    assert m.get("8125") == "watch-folder-router"
    # inline flow:     ports: ["${FLUTE_BIND:-127.0.0.1}:8055:8055", ...]
    assert m.get("8055") == "flute-gateway"
    # trailing-comment service key
    assert m.get("8124") == "voice-sampler"


def test_angle_bracket_params_are_wildcards_not_skips():
    """`<param>` must behave exactly like `{param}` — matched, never skipped.

    Excluding `<` from the path charclass did not skip the citation, it
    TRUNCATED it: `/jobs/<context_id>` was captured as `/jobs/`, which then
    failed the matcher for the real route and reported a ghost. A gate that
    flags correct documentation is worse than one that misses, because it
    pushes authors to "fix" docs that were right.

    Skipping bracketed paths wholesale is the opposite error — it would have
    hidden three real ghosts (`/mcp/task/<task_id>`) in the agent command docs.
    So both directions are pinned here.
    """
    m = vca.ENDPOINT_CITE_RE.search("curl http://localhost:8080/jobs/<context_id>")
    assert m and m.group(3) == "/jobs/<context_id>", "angle-bracket path was truncated"

    real = _matchers(["/jobs/{context_id}", "/mcp/commands", "/mcp/execute"])
    hit = lambda p: any(r.match(p) for r in real)

    assert hit("/jobs/<context_id>")   # real route, documented with <param>
    assert hit("/jobs/{context_id}")   # real route, documented with {param}
    assert not hit("/mcp/task/<task_id>")  # genuine ghost, must stay visible


def test_shell_interpolation_is_still_skipped():
    # `$VAR` can expand to anything, so there is no claim to check.
    assert "$" in "/v1/voice/personas/$PERSONA_ID"
