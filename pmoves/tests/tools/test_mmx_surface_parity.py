"""The mmx CLI surface parity gate: the doc must describe the measured CLI.

WHY THIS FILE EXISTS
--------------------
``pmoves/docs/services/MMX_CLI_SURFACE.md`` catalogued the ``mmx`` command
surface from memory. It drifted: it promised ``mmx music generate`` (the
installed build has no ``music`` resource), ``mmx speech list-voices`` and
``mmx speech clone`` (both renamed), ``mmx config get`` and ``mmx search
news`` (never existed in the installed build), it omitted ``mmx agent setup``,
``mmx text repl``, ``mmx config show``, ``mmx config export-schema`` and the
``video task get`` / ``video download`` pair, and it stated npm version
``v1.0.19`` against an installed ``1.0.25``.

``pmoves/tools/mmx_surface_probe.py`` measures the surface and
``pmoves/tools/mmx_surface_parity.py`` holds the doc against that measurement.
These tests are the net for the GATE, not for the fix: they drive the shipped
tool, so a gate that stopped reading its input, stopped comparing a direction,
or stopped failing closed would show up here.

WHAT IS ASSERTED
----------------
1. each finding kind, against a synthetic doc + synthetic snapshot, through
   the real module functions;
2. FAIL CLOSED: an unparseable doc, a missing snapshot file and a malformed
   snapshot ENTRY each produce a finding rather than a pass;
3. the CLI, driven as a subprocess: non-zero exit on findings, zero exit
   against the live doc, machine-readable ``--json`` output;
4. the LIVE tree is clean, and the ORIGINAL (pre-fix) doc is red -- the drift
   was real, and the gate is what proves it;
5. the PROBE: the video model legend is not a command, a multi-word command
   (``task get``) is one command, ANSI colour codes are stripped, and the
   probe refuses to run anything that is not a help or version request.

Point 4 matters more than it looks. A test that re-types the detector's own
expression proves nothing about the detector; these drive the shipped code.

Hermetic: no network, no API key, no model call. The probe tests that need
the real binary skip when it is not installed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from pmoves.tools import mmx_surface_parity as parity
from pmoves.tools import mmx_surface_probe as probe

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "pmoves" / "docs" / "services" / "MMX_CLI_SURFACE.md"
SNAPSHOT = REPO_ROOT / "pmoves" / "configs" / "mmx_surface" / "cli_surface.json"
PARITY_TOOL = REPO_ROOT / "pmoves" / "tools" / "mmx_surface_parity.py"
PROBE_TOOL = REPO_ROOT / "pmoves" / "tools" / "mmx_surface_probe.py"

# The doc as it stood before the fix, verbatim from
# `git show origin/main:pmoves/docs/services/MMX_CLI_SURFACE.md`. It is the
# evidence that the drift was real: the gate must be RED against it.
ORIGINAL_DOC_TEXT = """# mmx-cli — surface catalog

**Submodule:** [Pmoves-minimax-cli](https://github.com/POWERFULMOVES/Pmoves-minimax-cli) (POWERFULMOVES fork of MiniMax-AI/cli)
**Pin:** 24875e0f04220480a7b146fc8db11ca7b0b278aa
**npm name:** `mmx-cli` (v1.0.19)
**Install path on operator nodes:** `mmx` (resolved via `bin/mmx` → `dist/mmx.mjs`)

The Mavis model cascade has two entry points: the MCP server (`pmoves-minimax-mcp`, stdio via `uvx minimax-mcp`, used by WebUI/Agent Zero) and the CLI (`mmx`, used by the sidecar lane — Pinokio on operator devices, headless scripts, and any pipeline that wants to call models without standing up a full MCP client). This doc catalogs the CLI surface.

The upstream MiniMax-AI/cli repo has its own `AGENTS.md` (5471 bytes, build/test/lint rules) and `SDK.md` (4989 bytes, programmatic API surface) and `ERRORS.md` (9996 bytes, error taxonomy). This doc is the Mavis-side summary: what the operator needs to know to drive the CLI from a sidecar or a script.

## Top-level command tree

```text
mmx
├── auth       login, logout, refresh, status
├── config     set, get
├── file       upload, list, delete
├── image      generate
├── music      generate
├── quota      show
├── search     web, news
├── speech     synthesize, list-voices, clone
├── text       chat
├── video      generate
├── vision     describe
├── help       --command <name>
└── update     self
```

| Command | Purpose | Example |
|---------|---------|---------|
| `mmx auth login` | Authenticate (api-key or OAuth) | `mmx auth login --method api-key --api-key sk-...` |
| `mmx auth status` | Show current auth + quota | `mmx auth status` |
| `mmx config set api-key` | Set the API key non-interactively | `mmx config set api-key sk-...` |
| `mmx text chat` | Single-shot chat | `mmx text chat --model MiniMax-M3 --message "hi"` |
| `mmx text chat --stream` | Streaming chat | `mmx text chat --model MiniMax-M3 --message "..." --stream` |
| `mmx image generate` | Text-to-image | `mmx image generate --model image-01 --prompt "a cat" --out-dir ./out` |
| `mmx video generate` | Text-to-video (sync) | `mmx video generate --model MiniMax-H3 --prompt "..."` |
| `mmx video generate --async` | Text-to-video (returns taskId) | `mmx video generate --prompt "..." --async` |
| `mmx speech synthesize` | TTS | `mmx speech synthesize --voice <id> --text "..." --out ./out.mp3` |
| `mmx speech list-voices` | List available voices | `mmx speech list-voices` |
| `mmx speech clone` | Voice clone from a sample | `mmx speech clone --sample ./sample.wav --name my-voice` |
| `mmx vision describe` | Image captioning | `mmx vision describe --image ./cat.png` |
| `mmx music generate` | Text-to-music | `mmx music generate --prompt "lo-fi beats" --out ./out.mp3` |
| `mmx quota show` | Show rate-limit status | `mmx quota show` |
| `mmx search web` | Web search | `mmx search web --query "..."` |
| `mmx file upload` | Upload a file (for vision, voice-clone, etc.) | `mmx file upload --path ./sample.wav` |
| `mmx update` | Self-update | `mmx update` |

## SDK surface (programmatic)

The CLI is also a library: `import { MiniMaxSDK } from 'mmx-cli/sdk'`. The SDK mirrors the top-level commands but returns parsed results instead of printing them.

```typescript
import { MiniMaxSDK } from 'mmx-cli/sdk';

const sdk = new MiniMaxSDK({
  apiKey: 'sk-xxxxx',         // optional if mmx config set
  region: 'global',           // or 'cn'
});

// Text
const response = await sdk.text.chat({
  model: 'MiniMax-M3',
  messages: [{ role: 'user', content: 'Hello!' }],
  max_tokens: 4096,
});

// Image
const result = await sdk.image.generate({
  model: 'image-01',
  prompt: 'A cat in a spacesuit',
  width: 1024,
  height: 1024,
  n: 1,
});

// Video (sync — waits)
const video = await sdk.video.generate({
  model: 'MiniMax-Hailuo-2.3',
  prompt: 'Ocean waves at sunset',
});

// Video (H3 — V2 with request defaults)
const h3Video = await sdk.video.generate({
  model: 'MiniMax-H3',
  prompt: 'Ocean waves at sunset',
});

// Video (async — returns taskId)
const { taskId } = await sdk.video.generate({
  prompt: 'A robot painting',
  async: true,
});
```

The SDK is the right entry point when the sidecar needs to chain model calls (e.g. caption an image, generate a video from the caption, transcribe the audio). The CLI is the right entry point for one-shot human-in-the-loop use.

## Errors (the operator-relevant subset)

The full ERRORS.md has 70+ error scenarios. The five you'll hit most often:

| Command | Scenario | Message |
|---------|----------|---------|
| `auth login` | `--method api-key` without `--api-key` | `--api-key is required when using --method api-key.` |
| `auth login` | API key validation failed | `API key validation failed.` |
| `text chat` | No `--message` in non-interactive mode | `Missing required argument: --message` |
| `text chat` | Stream disconnected mid-response | `Stream disconnected before response completed.` |
| `image generate` | All images rejected | `Image generation failed: all images were rejected (content policy or model error).` |

For all other errors, see `Pmoves-minimax-cli/ERRORS.md`. The error handling is layered: `errors/codes.ts` (machine codes) → `errors/handler.ts` (formatting) → `errors/api.ts` (HTTP-to-error mapping). Scripts that consume the CLI should match on the error code, not the message.

## Sidecar lane (Pinokio)

The Mavis model cascade calls the CLI from Pinokio apps on operator devices (Pixel phones, Tab Ultras, etc., all on the Tailscale tailnet). The pattern:

1. **Sidecar checks for `mmx` on `$PATH`.** If absent, the app surfaces an actionable error: "Install `mmx-cli` via `npm install -g mmx-cli` or Pinokio's `pmoves-minimax-cli` install recipe."
2. **Sidecar runs `mmx auth login --method api-key --api-key "$MINIMAX_API_KEY"` non-interactively** at app start if the env var is set. This populates `~/.mmx/config.json` with the per-device key.
3. **Sidecar runs `mmx quota show`** at app start to surface rate-limit status to the user.
4. **Sidecar issues one-shot CLI calls** for each model operation. The CLI writes to a temp directory under `MMX_TMP_DIR` (defaults to `$TMPDIR/mmx-$$`); the sidecar watches the directory and ingests results as they appear.

The CLI is the sidecar's preferred entry point because (a) it doesn't need an MCP client, (b) the per-device `~/.mmx/config.json` is a stable place to keep the API key, and (c) the `mmx` binary is a small dependency that ships in the Pinokio app's portable bundle.

## Why not always call the MCP?

The MCP server and the CLI cover the same model surface. The split is **who's calling**:

- **MCP (stdio via `uvx minimax-mcp`):** WebUI, Agent Zero, any tool-aware agent. The MCP is the right surface when the caller is already an MCP client and wants tool-discovery + schema-validated calls.
- **CLI (`mmx`):** sidecar apps, headless scripts, CI jobs, anything that's not an MCP client. The CLI is the right surface when the caller is "just a process that wants to call a model."

If a sidecar app grows an MCP-aware component (e.g. a future Pinokio app that ships Claude Code), the right move is to switch the sidecar to the MCP. For now, the CLI is the lighter path.

## Reference

- Submodule: `Pmoves-minimax-cli/` (PMOVES fork of MiniMax-AI/cli)
- Submodule pin: `24875e0f04220480a7b146fc8db11ca7b0b278aa`
- Upstream CLI repo: https://github.com/MiniMax-AI/cli
- Upstream AGENTS.md: `Pmoves-minimax-cli/AGENTS.md` (build/test/lint)
- Upstream SDK.md: `Pmoves-minimax-cli/SDK.md` (programmatic API)
- Upstream ERRORS.md: `Pmoves-minimax-cli/ERRORS.md` (full error catalog)
- npm package: https://www.npmjs.com/package/mmx-cli
- Mavis model cascade context: `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` → `services.minimax.cli`
"""


def _snapshot_payload() -> dict:
    """A synthetic snapshot with three resources."""
    return {
        "schema": "pmoves.mmx-cli-surface/v1",
        "mmx_version": "1.0.25",
        "resources": {
            "auth": ["login", "status"],
            "text": ["chat", "repl"],
            "update": [],
        },
        "global_flags": ["--help", "--output"],
    }


def _doc_text(
    resources: dict[str, list[str]] | None = None,
    version: str = "1.0.25",
    flags: list[str] | None = None,
    tree: dict[str, list[str]] | None = None,
    rows: list[tuple[str, str]] | None = None,
    with_surface: bool = True,
) -> str:
    """Build a synthetic doc carrying a machine-readable surface.

    The doc is the INPUT to the gate. It is written here so the gate has
    something to read; the assertions are all made against what the gate
    says about it.
    """
    resources = resources if resources is not None else {
        "auth": ["login", "status"],
        "text": ["chat", "repl"],
        "update": [],
    }
    flags = flags if flags is not None else ["--help", "--output"]
    tree = tree if tree is not None else resources
    rows = rows if rows is not None else [
        (resource, command) for resource, commands in resources.items() for command in commands
    ]

    tree_lines = ["mmx"]
    for resource, commands in tree.items():
        listed = ", ".join(commands)
        tree_lines.append(f"├── {resource}    {listed}")
    table_rows = "\n".join(
        f"| `mmx {resource} {command}` | does a thing | `mmx {resource} {command}` |"
        for resource, command in rows
    )
    flag_lines = "\n".join(f"- `{flag}` — a global flag" for flag in flags)
    block = json.dumps(
        {"mmx_version": version, "resources": resources, "global_flags": flags},
        indent=2,
        sort_keys=True,
    )

    surface = ""
    if with_surface:
        surface = (
            "\n## Machine-checkable surface\n\n```json\n" + block + "\n```\n"
        )

    return (
        "# mmx-cli — surface catalog\n\n"
        f"**npm name:** `mmx-cli` (v{version})\n\n"
        "## Top-level command tree\n\n```text\n"
        + "\n".join(tree_lines)
        + "\n```\n\n"
        "| Command | Purpose | Example |\n"
        "|---------|---------|---------|\n"
        + table_rows
        + "\n\n## Global flags\n\n"
        + flag_lines
        + "\n"
        + surface
    )


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_gate(doc_path: Path, snapshot_path: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(PARITY_TOOL),
            "--check",
            "--doc",
            str(doc_path),
            "--snapshot",
            str(snapshot_path),
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _kinds(report: dict) -> set[str]:
    return {finding["kind"] for finding in report["findings"]}


# --------------------------------------------------------------------------
# the gate: one test per finding kind
# --------------------------------------------------------------------------


def test_a_documented_command_the_cli_lacks_is_reported(tmp_path: Path) -> None:
    """DOCUMENTED_MISSING: the doc promises a command the CLI does not have."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(resources={"text": ["chat", "repl"]}, tree={"text": ["chat", "repl"]}),
        encoding="utf-8",
    )
    payload = _snapshot_payload()
    payload["resources"]["text"] = ["chat"]
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    assert "DOCUMENTED_MISSING" in _kinds(report)
    missing = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "DOCUMENTED_MISSING"
        and finding.get("scope") == "command"
        and finding.get("command") == "repl"
    ]
    assert missing, report["findings"]


def test_a_documented_resource_the_cli_lacks_is_reported(tmp_path: Path) -> None:
    """DOCUMENTED_MISSING, at resource granularity."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(resources={"music": ["generate"]}, tree={"music": ["generate"]}),
        encoding="utf-8",
    )
    snapshot = _write(tmp_path / "snap.json", _snapshot_payload())

    report = parity.check(doc, snapshot)

    missing = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "DOCUMENTED_MISSING"
        and finding.get("scope") == "resource"
        and finding.get("resource") == "music"
    ]
    assert missing, report["findings"]


def test_a_snapshot_command_the_doc_never_mentions_is_reported(tmp_path: Path) -> None:
    """UNDOCUMENTED: the CLI has something the doc never mentions.

    Both granularities matter: a command the doc left out of a resource it
    does document, and a whole resource the doc never mentions.
    """
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(resources={"text": ["chat"]}, tree={"text": ["chat"]}),
        encoding="utf-8",
    )
    payload = _snapshot_payload()
    payload["resources"]["video"] = ["generate"]
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    assert "UNDOCUMENTED" in _kinds(report)
    undocumented = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "UNDOCUMENTED"
        and finding.get("scope") == "command"
        and finding.get("command") == "repl"
    ]
    assert undocumented, report["findings"]
    whole_resource = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "UNDOCUMENTED"
        and finding.get("scope") == "resource"
        and finding.get("resource") == "video"
    ]
    assert whole_resource, report["findings"]


def test_a_global_flag_the_doc_omits_is_reported(tmp_path: Path) -> None:
    """UNDOCUMENTED, at global-flag granularity."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(), encoding="utf-8")
    payload = _snapshot_payload()
    payload["global_flags"] = ["--help", "--output", "--quiet"]
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    flagged = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "UNDOCUMENTED"
        and finding.get("scope") == "global_flag"
        and finding.get("flag") == "--quiet"
    ]
    assert flagged, report["findings"]


def test_a_version_mismatch_is_reported(tmp_path: Path) -> None:
    """VERSION_DRIFT, from both the JSON block and the prose version line."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(version="1.0.19"), encoding="utf-8")
    snapshot = _write(tmp_path / "snap.json", _snapshot_payload())

    report = parity.check(doc, snapshot)

    drift = [finding for finding in report["findings"] if finding["kind"] == "VERSION_DRIFT"]
    assert drift, report["findings"]
    scopes = {finding["scope"] for finding in drift}
    assert "json" in scopes, drift
    assert "prose" in scopes, drift


def test_a_doc_without_the_machine_readable_block_is_a_parse_error(tmp_path: Path) -> None:
    """PARSE_ERROR: an unparseable doc is never treated as clean."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(with_surface=False), encoding="utf-8")
    snapshot = _write(tmp_path / "snap.json", _snapshot_payload())

    report = parity.check(doc, snapshot)

    assert "PARSE_ERROR" in _kinds(report)
    assert not report["ok"]


def test_a_missing_snapshot_file_is_an_instrument_error(tmp_path: Path) -> None:
    """INSTRUMENT_ERROR, at file granularity: the gate cannot measure."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(), encoding="utf-8")

    report = parity.check(doc, tmp_path / "does-not-exist.json")

    assert "INSTRUMENT_ERROR" in _kinds(report)
    assert not report["ok"]


def test_a_malformed_snapshot_entry_is_an_instrument_error(tmp_path: Path) -> None:
    """INSTRUMENT_ERROR, at entry granularity: a bad command list is not a skip."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(), encoding="utf-8")
    payload = _snapshot_payload()
    payload["resources"]["text"] = "chat"
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    assert "INSTRUMENT_ERROR" in _kinds(report)
    assert not report["ok"]


def test_a_stale_command_tree_is_reported(tmp_path: Path) -> None:
    """The tree is scraped too: a stale tree is a finding even with a good JSON block."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(tree={"auth": ["login", "status"], "music": ["generate"]}),
        encoding="utf-8",
    )
    snapshot = _write(tmp_path / "snap.json", _snapshot_payload())

    report = parity.check(doc, snapshot)

    stale = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "DOCUMENTED_MISSING"
        and finding.get("scope") == "resource"
        and finding.get("resource") == "music"
    ]
    assert stale, report["findings"]


def test_a_stale_command_table_is_reported(tmp_path: Path) -> None:
    """The command table is scraped too."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(rows=[("text", "chat"), ("text", "repl"), ("speech", "clone")]),
        encoding="utf-8",
    )
    payload = _snapshot_payload()
    payload["resources"]["speech"] = ["voices"]
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    stale = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "DOCUMENTED_MISSING"
        and finding.get("scope") == "command"
        and finding.get("command") == "clone"
    ]
    assert stale, report["findings"]


# --------------------------------------------------------------------------
# the CLI
# --------------------------------------------------------------------------


def test_the_cli_exits_non_zero_when_findings_exist(tmp_path: Path) -> None:
    """A gate that finds drift must not exit zero."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(version="1.0.19"), encoding="utf-8")
    snapshot = _write(tmp_path / "snap.json", _snapshot_payload())

    proc = _run_gate(doc, snapshot)

    assert proc.returncode != 0, proc.stdout


def test_the_cli_exits_zero_against_the_live_doc_and_snapshot() -> None:
    """The committed doc and the committed snapshot agree."""
    proc = _run_gate(DOC, SNAPSHOT)

    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_json_report_is_machine_readable(tmp_path: Path) -> None:
    """--json emits a report a machine can read."""
    doc = tmp_path / "doc.md"
    doc.write_text(_doc_text(version="1.0.19"), encoding="utf-8")
    snapshot = _write(tmp_path / "snap.json", _snapshot_payload())

    proc = _run_gate(doc, snapshot, "--json")

    payload = json.loads(proc.stdout)
    assert payload["findings"]
    assert payload["ok"] is False
    assert payload["finding_count"] == len(payload["findings"])
    assert proc.returncode != 0


# --------------------------------------------------------------------------
# the live tree and the original doc
# --------------------------------------------------------------------------


def test_the_live_doc_and_snapshot_agree() -> None:
    """The committed pair is clean, through the module."""
    report = parity.check(DOC, SNAPSHOT)

    assert report["ok"], report["findings"]
    assert report["doc_version"] == report["snapshot_version"]


def test_the_original_doc_is_red() -> None:
    """The drift was real: the pre-fix doc fails the gate."""
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "original.md"
        doc.write_text(ORIGINAL_DOC_TEXT, encoding="utf-8")
        report = parity.check(doc, SNAPSHOT)

    assert not report["ok"]
    kinds = _kinds(report)
    assert "DOCUMENTED_MISSING" in kinds
    assert "UNDOCUMENTED" in kinds
    assert "VERSION_DRIFT" in kinds
    assert "PARSE_ERROR" in kinds

    details = {finding["detail"] for finding in report["findings"]}
    assert any("'music'" in detail for detail in details), details
    assert any("speech list-voices" in detail for detail in details), details
    assert any("speech clone" in detail for detail in details), details
    assert any("search news" in detail for detail in details), details
    assert any("config get" in detail for detail in details), details
    assert any("text repl" in detail for detail in details), details
    assert any("agent" in detail for detail in details), details
    assert any("1.0.19" in detail for detail in details), details


# --------------------------------------------------------------------------
# the prose nets: the second net must actually catch something
# --------------------------------------------------------------------------


def test_the_live_docs_prose_global_flag_list_is_scraped() -> None:
    """The prose net must catch the LIVE doc's global-flag list.

    The live doc introduces its list with a sentence -- "These are accepted
    by every command:" sits between the heading and the bullets -- so a
    scanner that stops at the first non-bullet scrapes NOTHING from the real
    doc, and the flags are policed by the JSON block alone. The expected set
    is computed from the source of truth (the measured snapshot), never
    re-typed here.
    """
    doc_text = DOC.read_text(encoding="utf-8")
    prose_flags = parity.extract_prose_global_flags(doc_text)
    measured = set(json.loads(SNAPSHOT.read_text(encoding="utf-8"))["global_flags"])

    assert prose_flags, "the prose global-flag list scraped nothing from the live doc"
    assert prose_flags == measured, (
        f"the doc's prose flag list is {sorted(prose_flags)}, "
        f"the measured CLI has {sorted(measured)}"
    )


def test_the_prose_flag_scraper_keeps_scanning_past_a_prose_line() -> None:
    """A sentence before the list is not the end of the list.

    The scan ends at the next HEADING: a flag list that follows a sentence
    is still scraped, and a list in a LATER section is not.
    """
    doc_text = (
        "# catalog\n\n"
        "## Global flags\n\n"
        "These are accepted by every command:\n\n"
        "- `--alpha` — first\n"
        "- `--beta` — second\n\n"
        "## Another section\n\n"
        "- `--gamma` — not a global flag\n"
    )

    assert parity.extract_prose_global_flags(doc_text) == {"--alpha", "--beta"}


def test_a_stale_over_claiming_table_row_is_reported(tmp_path: Path) -> None:
    """A table row that names a command the CLI no longer has is VISIBLE.

    The CLI renamed `video task get` to `video task`. The doc's table still
    says `mmx video task get`. Resolving that row against the known commands
    lands on `video task` -- and the dead over-claim used to vanish into the
    live surface with no trace at all. It must be reported instead.
    """
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(
            resources={"video": ["task"]},
            tree={"video": ["task"]},
            rows=[("video", "task get")],
        ),
        encoding="utf-8",
    )
    payload = {
        "mmx_version": "1.0.25",
        "resources": {"video": ["task"]},
        "global_flags": ["--help", "--output"],
    }
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    over_claims = [
        finding
        for finding in report["findings"]
        if finding["kind"] == "DOCUMENTED_MISSING"
        and finding.get("scope") == "command"
        and finding.get("command") == "task get"
    ]
    assert over_claims, report["findings"]


def test_a_table_row_with_flags_still_resolves_to_the_full_command(tmp_path: Path) -> None:
    """Flags on a known command are not an over-claim.

    `mmx video task get --limit 5` claims the command `video task get`; the
    flags are the invocation's, not the command's, so the row resolves to the
    full command and the gate stays quiet.
    """
    doc = tmp_path / "doc.md"
    doc.write_text(
        _doc_text(
            resources={"video": ["task get"]},
            tree={"video": ["task get"]},
            rows=[("video", "task get --limit 5")],
        ),
        encoding="utf-8",
    )
    payload = {
        "mmx_version": "1.0.25",
        "resources": {"video": ["task get"]},
        "global_flags": ["--help", "--output"],
    }
    snapshot = _write(tmp_path / "snap.json", payload)

    report = parity.check(doc, snapshot)

    assert report["ok"], report["findings"]


# --------------------------------------------------------------------------
# the probe
# --------------------------------------------------------------------------

VIDEO_HELP = """
Usage: mmx video <command> [flags]

Commands:
  video generate  Generate a video
  V2:   MiniMax-H3 (text/image/video/audio content, 2K)
  T2V:  Hailuo-2.3
  I2V:  Hailuo-2.3 (default) / Hailuo-2.3-Fast (fast mode, requires --image)
  SEF:  Hailuo-02 (requires --image and --last-frame)
  S2V:  S2V-01 (requires --subject-image)
  video task get  Query video task status
  video download  Download a completed video by file ID
"""


def test_the_video_model_legend_is_not_parsed_as_commands() -> None:
    """``V2:``/``T2V:``/``I2V:``/``SEF:``/``S2V:`` are a model legend, not commands."""
    commands = probe.parse_commands("video", VIDEO_HELP)

    assert commands == ["download", "generate", "task get"]


def test_a_multi_word_command_is_parsed() -> None:
    """``video task get`` is one command, not two."""
    commands = probe.parse_commands("video", VIDEO_HELP)

    assert "task get" in commands
    assert "task" not in commands


def test_ansi_colour_codes_are_stripped() -> None:
    """The CLI colourises its help when it thinks it has a terminal."""
    coloured = "\x1b[31;1mResources:\x1b[0m\n  auth  \x1b[31mAuthentication\x1b[0m\n"

    assert probe.strip_ansi(coloured) == "Resources:\n  auth  Authentication\n"


def test_the_probe_fails_closed_when_the_binary_is_missing(tmp_path: Path) -> None:
    """No binary is an error, not an empty snapshot."""
    missing = tmp_path / "not-a-real-mmx"

    with pytest.raises(probe.ProbeError):
        probe.resolve_mmx(str(missing))


def test_the_probe_fails_closed_on_a_non_executable_binary(tmp_path: Path) -> None:
    """An unexecutable binary is a clean error, not a stack dump.

    POSIX: a file without the exec bit raises PermissionError. Windows: a
    file that is not a Win32 application raises OSError (WinError 193 /
    access denied). Both are OSError -- and both must become a ProbeError
    with a non-zero exit and NO traceback.
    """
    binary = tmp_path / "not-a-real-mmx.txt"
    binary.write_text("this is not a program\n", encoding="utf-8")
    if os.name != "nt":
        # POSIX has an exec bit to clear; Windows has none, and the file is
        # not an executable application either way.
        binary.chmod(0o600)

    proc = subprocess.run(
        [sys.executable, str(PROBE_TOOL), "--mmx-bin", str(binary)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    assert proc.returncode != 0, proc.stdout
    assert "Traceback" not in proc.stderr, proc.stderr
    assert "mmx-surface-probe: FAILED" in proc.stderr, proc.stderr


def test_the_probe_refuses_to_run_a_non_help_command() -> None:
    """The probe may only ask the CLI for help or its version."""
    with pytest.raises(probe.ProbeError):
        probe.run_mmx("mmx", ["text", "chat", "--message", "hello"])


def test_the_probe_fails_closed_on_an_unreadable_help_page() -> None:
    """A help page with neither a Commands: block nor a Usage: line is an error."""
    with pytest.raises(probe.ProbeError):
        probe.parse_commands("video", "nothing recognisable here\n")


def test_the_probe_snapshot_is_byte_stable(tmp_path: Path) -> None:
    """The same measurement always serialises to the same bytes."""
    snapshot = {
        "schema": "pmoves.mmx-cli-surface/v1",
        "mmx_version": "1.0.25",
        "resources": {"text": ["chat", "repl"]},
        "global_flags": ["--help"],
    }
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    probe.write_snapshot(first, snapshot)
    probe.write_snapshot(second, snapshot)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.skipif(
    shutil.which("mmx") is None and shutil.which("mmx.cmd") is None,
    reason="the mmx CLI is not installed on this host",
)
def test_the_probe_reproduces_the_committed_snapshot() -> None:
    """The committed snapshot IS what the installed CLI measures."""
    measured = probe.build_snapshot(probe.resolve_mmx())
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert measured == committed
