"""Ratchet: the /n8n slash commands must not be unsafe to run.

WHAT THIS FILE ASSERTS
----------------------
The ``.claude/commands/n8n/*.md`` files are not documentation -- they are
commands an AGENT EXECUTES. Each one is a shell transcript that gets run
against the live n8n instance. Five properties are asserted here, each
because a review finding showed the command could mislead or leak:

1. **NO RAW URL INTERPOLATION.** A workflow name routinely contains a space,
   an ``&``, a ``#`` or a ``?``. Interpolating the search term straight into
   a query string either makes curl reject the URL or changes the query
   parameters, so the search silently finds the WRONG workflow. The term must
   be URL-ENCODED.
2. **EVERY LISTING PAGES.** The Public REST API's default take is 100, so an
   unpaged listing silently ignores everything past the first hundred
   workflows -- and in these commands that listing is the node-type census
   the model is told to use.
3. **ACTIVATION IS NOT EXECUTION.** ``POST /workflows/{id}/activate`` enables
   a workflow's TRIGGERS; it creates no execution. For a schedule-, manual-
   or queue-triggered workflow, activating it and then reading the executions
   can return an OLDER run, and reporting that as this request's output is a
   lie. The command must filter the executions by when they STARTED, and must
   say plainly that direct execution is unsupported for a non-webhook trigger.
4. **ACTIVATION IS RESTORED.** Activating a cron-triggered workflow arms it
   for every interval, for ever, and nothing else turns it off. The command
   must deactivate again if it is what activated the workflow.
5. **PARAMETER VALUES ARE REDACTED.** A configured node instance's
   ``parameters`` object can carry literal HTTP headers, query parameters,
   webhook secrets and inline credentials. Printing it whole copies those
   secrets into the chat transcript. The credential-bearing VALUES must be
   redacted before anything is emitted.

Hermetic: no network, no docker, no nats, no gh. It reads files in this
repository.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

COMMAND_DIR = REPO_ROOT / ".claude" / "commands" / "n8n"

#: A search term pasted into a query string. ``?name=$ARGUMENTS`` is the
#: shape; the fix is curl's ``--data-urlencode "name=$ARGUMENTS"``.
_RAW_QUERY_INTERPOLATION_RE = re.compile(r"[?&][A-Za-z_][A-Za-z0-9_]*=\$ARGUMENTS")

#: The Public REST API's maximum page size.
PUBLIC_TAKE = 250

#: The redaction marker the commands must use for a credential-bearing value.
REDACTION_MARKER = "***REDACTED***"

#: The key names whose values must be redacted.
CREDENTIAL_KEY_PATTERN = (
    "header|auth|token|secret|password|credential|signature|cookie"
)


def _command_files() -> list[Path]:
    return sorted(COMMAND_DIR.glob("*.md")) if COMMAND_DIR.is_dir() else []


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_command_surface_is_present() -> None:
    """ANTI-VACUITY: the gate must be reading the files it claims to read.

    A ratchet pointed at an empty directory asserts nothing at all.
    """
    files = _command_files()
    assert files, (
        f"no slash commands found under {_rel(COMMAND_DIR)} -- this ratchet is "
        "watching nothing"
    )
    names = {path.name for path in files}
    for expected in ("execute.md", "nodes.md", "workflows.md", "suggest.md"):
        assert expected in names, (
            f"{expected} is missing from the n8n command directory; the gates "
            f"below assume it exists (found {sorted(names)})"
        )


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def test_no_command_interpolates_arguments_into_a_raw_url_query() -> None:
    """A search term must be URL-ENCODED, not pasted into the query string.

    A workflow called ``Finance Monthly`` carries a raw space, and any ``&``,
    ``#`` or ``?`` in the name splits or truncates the query -- so the search
    silently resolves to the wrong workflow, or to none.
    """
    offenders: list[str] = []
    for path in _command_files():
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            if _RAW_QUERY_INTERPOLATION_RE.search(line):
                offenders.append(f"{_rel(path)}:{lineno}: {line.strip()[:120]}")
    assert not offenders, (
        "an n8n slash command interpolates its search term into a raw query "
        "string, so a name with a space or an & silently selects the wrong "
        "workflow:\n  "
        + "\n  ".join(offenders)
        + "\nBuild the query with curl's --get --data-urlencode instead."
    )


def test_every_workflow_listing_pages_through_every_page() -> None:
    """A listing that does not page silently truncates at 100 workflows.

    The Public REST API's default take is 100. In these commands the listing
    IS the node-type census the model is told to use, so a truncation is a
    wrong answer, not a missing detail.
    """
    offenders: list[str] = []
    for path in _command_files():
        text = _read(path)
        if "/api/v1/workflows" not in text:
            continue
        if "nextCursor" not in text:
            offenders.append(f"{_rel(path)}: never pages on nextCursor")
        if f"take={PUBLIC_TAKE}" not in text:
            offenders.append(
                f"{_rel(path)}: does not request take={PUBLIC_TAKE} (the public "
                "API cap), so it gets the default 100"
            )
    assert not offenders, (
        "an n8n slash command lists workflows without paging, so it silently "
        "ignores every workflow past the first hundred:\n  "
        + "\n  ".join(offenders)
    )


def test_the_execute_command_does_not_present_activation_as_execution() -> None:
    """Activation enables triggers; it does not create an execution.

    So the executions the command reads must be filtered by when they STARTED
    -- an older run is not this request's output -- and the command must say
    that direct execution is unsupported for a non-webhook trigger.
    """
    path = COMMAND_DIR / "execute.md"
    text = _read(path)
    assert "startedAt" in text, (
        "execute.md reads the executions without ever comparing their start "
        "time, so it can report an OLDER run as this request's output"
    )
    assert re.search(r"select\(\.startedAt\s*>", text), (
        "execute.md does not filter the executions by their start time; an "
        "older run would be reported as this request's output"
    )
    assert "not execution" in text.lower() or "activation is not execution" in text.lower(), (
        "execute.md does not state that activation is not execution, so the "
        "reader cannot tell that a non-webhook workflow was not run"
    )
    assert "unsupported" in text.lower(), (
        "execute.md does not say that direct execution is unsupported for a "
        "schedule-, manual- or queue-triggered workflow"
    )


def test_the_execute_command_restores_the_activation_state() -> None:
    """Activating a workflow arms it for ever; the command must undo that.

    Nothing else in the fleet turns a cron-triggered workflow off, so a
    command that activates and walks away enrols it into the permanently
    active set.
    """
    path = COMMAND_DIR / "execute.md"
    text = _read(path)
    assert "/deactivate" in text, (
        "execute.md activates a workflow but never deactivates it, so the "
        "workflow stays armed on every schedule for ever"
    )


def test_the_execute_command_chooses_a_webhook_candidate_deliberately() -> None:
    """Two webhook nodes must not mean two URLs and no tiebreaker.

    The candidates must be emitted with an index, and the difference between
    a test-mode webhook and a production one must be stated -- test mode lives
    at ``/webhook-test/<path>`` and needs no activation, production lives at
    ``/webhook/<path>`` and needs the workflow active.
    """
    path = COMMAND_DIR / "execute.md"
    text = _read(path)
    assert "/webhook-test/" in text, (
        "execute.md does not mention the test-mode webhook path, so the "
        "executor cannot tell a test-mode webhook from a production one"
    )
    assert re.search(r"\[\\\(\\\.name\\\)\]", text) or "index" in text.lower(), (
        "execute.md emits the webhook candidates without an index, so a "
        "workflow with two webhook nodes hands the executor two URLs and no "
        "tiebreaker"
    )


def test_the_nodes_command_redacts_credential_bearing_parameters() -> None:
    """A configured instance's parameters can carry live credentials.

    Printing the whole ``parameters`` object copies HTTP headers, webhook
    secrets and inline credentials into the chat transcript, and this command
    then asks the agent to report the configuration properties.
    """
    path = COMMAND_DIR / "nodes.md"
    text = _read(path)
    assert REDACTION_MARKER in text, (
        "nodes.md emits node parameters without redacting the credential-"
        "bearing values, so live secrets reach the chat transcript"
    )
    for pattern in CREDENTIAL_KEY_PATTERN.split("|"):
        assert pattern in text.lower(), (
            f"nodes.md does not name {pattern!r} among the keys whose values "
            "it redacts"
        )
    assert not re.search(r"\\\(\\\.parameters\s*\|\s*tostring\)", text), (
        "nodes.md still emits the raw parameters object; the redaction has to "
        "be the only path to it"
    )


def test_the_nodes_command_reads_the_installed_node_catalog() -> None:
    """An installed-but-unused node is invisible in a workflow census.

    The Public REST API exposes no node catalog, so the census can only
    report USAGE. The command must say so and point at the installed node
    definitions in the n8n image -- otherwise a first-time node (Slack, say)
    reads as absent.
    """
    path = COMMAND_DIR / "nodes.md"
    text = _read(path).lower()
    assert "n8n-nodes-base" in text, (
        "nodes.md does not point at the installed node definitions, so a node "
        "that is installed but unused in any workflow reads as absent"
    )
    assert "catalog" in text, (
        "nodes.md does not state that the Public REST API exposes no node "
        "catalog, so the census is mistaken for one"
    )
