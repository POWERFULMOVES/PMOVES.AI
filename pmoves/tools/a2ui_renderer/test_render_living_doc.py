#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
test_render_living_doc.py — smoke + unit tests for render_living_doc.py

Lane 2228 (2026-08-02): proves the script is correct without needing the real
a2ui-renderer running. Uses a local http.server mock to exercise the full
HTTP path on a 127.0.0.1 ephemeral port.

Tests:
  - parse_markdown_to_provenance: 4-section cap, title from H1, fallback to
    filename, merkle_root determinism, weighted_terms limit
  - load_renderable_registry: 5 entries pulled out of a real registry file,
    malformed entries skipped
  - render_one dry-run: writes a valid JSON file with no HTTP traffic
  - render_one full path: posts to mock /render/provenance, downloads the
    mocked file, returns ok=True with all expected fields
  - render_registry: iterates the registry, returns per-entry results

Run:  python pmoves/tools/a2ui_renderer/test_render_living_doc.py
CI:   add to pmoves/skills/tests/ discovery if the operator wants it under pytest
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse

# Force UTF-8 on stdout/stderr (Windows charmap default would break the
# `✓` markers in render_living_doc.py's success output).
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# Make the script importable when running this file directly.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))  # pmoves/tools -> pmoves
# Actually the script is in pmoves/tools/a2ui_renderer/render_living_doc.py
# so from THIS file: HERE = pmoves/tools/a2ui_renderer, parent = pmoves/tools.
# We need pmoves/tools on sys.path so `from a2ui_renderer.render_living_doc ...` works.
sys.path = [str(HERE.parent)] + sys.path

from a2ui_renderer import render_living_doc as rld  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MD = """# CHIT Visual Tour Walkthrough

A first-principles walkthrough of the CHIT attestation chain. This doc is
the canonical entry point for new operators and is the primary source for
the a2ui-renderer living-doc export.

The CHIT lane is a non-negotiable trust primitive: every PMOVES agent signs
its outbound traffic, every cross-agent message is merklized, and every
claim is reconstructed by an offline verifier before action.

## Context

The attestation chain was built to survive operator absence. Each claim
references the prior merkle root, the agent's glyph signature, and the
NATS subject that carried it. The chain is replayable end-to-end.

## Operators

The two primary operators are DARKXSIDE (PMOVES.AI founder) and Mavis
(the local Mavis agent). Both sign with ed25519 and both publish via
the nats_event_bus. Both audit the chain weekly.

## See also

- [CHIT spec](pmoves/docs/PMOVESCHIT/README.md)
- [AGNOTE trail](pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md)
- [a2ui-renderer source](pmoves/services/a2ui-renderer/src/index.ts)
"""


SAMPLE_REGISTRY = """# Living docs registry (Lane 2228 example fragment)
tracked:
  - id: existing-thing
    freshness_days: 30
    severity: P2
    description: "Already-tracked entry (not rendered)"

renderable:
  - id: chit-visual-tour-walkthrough
    source_doc: pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md
    output_key: chit-visual-tour
    format: mp4
    ttl_days: 14

  - id: agnote-active-claims
    source_doc: pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
    output_key: agnote-active-claims
    format: mp4
    ttl_days: 3

  - id: chit-tour-public
    source_doc: pmoves/docs/handoffs/chit-tour-public-edge.md
    output_key: chit-tour-public-edge
    format: mp4
    ttl_days: 30
"""


def _free_port() -> int:
    """Bind to port 0 to get an unused port, then close and return it."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class MarkdownParserTests(unittest.TestCase):
    def test_h1_becomes_title(self) -> None:
        doc = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        self.assertEqual(doc.title, "CHIT Visual Tour Walkthrough")

    def test_h2s_become_sections(self) -> None:
        doc = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        headings = [s.heading for s in doc.sections]
        self.assertIn("Context", headings)
        self.assertIn("Operators", headings)
        self.assertLessEqual(len(doc.sections), rld.MAX_SECTIONS)

    def test_see_also_section_becomes_provenance_refs(self) -> None:
        doc = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        labels = [r["label"] for r in doc.provenance_refs]
        self.assertTrue(any("CHIT spec" in label for label in labels), labels)
        self.assertLessEqual(len(doc.provenance_refs), rld.MAX_PROVENANCE_REFS)

    def test_weighted_terms_capped(self) -> None:
        doc = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        self.assertLessEqual(len(doc.weighted_terms), rld.MAX_WEIGHTED_TERMS)
        for term in doc.weighted_terms:
            self.assertGreaterEqual(term["weight"], 0.5)
            self.assertLessEqual(term["weight"], 1.0)
            self.assertIn("term", term)
            self.assertIn("cluster", term)

    def test_merkle_root_is_deterministic(self) -> None:
        doc1 = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        doc2 = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        self.assertEqual(doc1.merkle_root, doc2.merkle_root)
        self.assertTrue(doc1.merkle_root.startswith("mkl_"))
        self.assertEqual(len(doc1.merkle_root), 4 + 16)

    def test_shape_id_stable_per_path(self) -> None:
        doc1 = rld.parse_markdown_to_provenance(Path("a/b/x.md"), SAMPLE_MD)
        doc2 = rld.parse_markdown_to_provenance(Path("a/b/x.md"), SAMPLE_MD)
        doc3 = rld.parse_markdown_to_provenance(Path("a/b/y.md"), SAMPLE_MD)
        self.assertEqual(doc1.shape_id, doc2.shape_id)
        self.assertNotEqual(doc1.shape_id, doc3.shape_id)
        self.assertTrue(doc1.shape_id.startswith("shape.doc."))

    def test_fallback_title_from_filename(self) -> None:
        doc = rld.parse_markdown_to_provenance(
            Path("my-cool-doc.md"), "## Just an h2\n\nBody."
        )
        self.assertEqual(doc.title, "My Cool Doc")
        # H2 still produces a real section even without an H1.
        self.assertEqual(len(doc.sections), 1)
        self.assertEqual(doc.sections[0].heading, "Just an h2")

    def test_unstructured_falls_back_to_overview(self) -> None:
        # No H1, no H2 — only freeform text. We should synthesize an
        # "Overview" section so the TS service's normalize() invariant
        # (at least one section) holds.
        doc = rld.parse_markdown_to_provenance(
            Path("freeform.md"),
            "Just some paragraphs.\n\nWith no headings at all.",
        )
        self.assertEqual(len(doc.sections), 1)
        self.assertEqual(doc.sections[0].heading, "Overview")

    def test_duration_ms_in_range(self) -> None:
        doc = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        self.assertGreaterEqual(doc.duration_ms, 9000)
        self.assertLessEqual(doc.duration_ms, 24000)

    def test_to_request_body_matches_ts_schema(self) -> None:
        """The request body must use the field names the TS service expects."""
        doc = rld.parse_markdown_to_provenance(Path("x.md"), SAMPLE_MD)
        body = doc.to_request_body()
        for required in (
            "title", "subtitle", "summary", "merkle_root", "shape_id",
            "favorite_words", "weighted_terms", "sections",
            "provenance_refs", "duration_ms", "palette",
        ):
            self.assertIn(required, body)
        for section in body["sections"]:
            self.assertIn("heading", section)
            self.assertIn("body", section)


class RegistryLoaderTests(unittest.TestCase):
    def test_loads_renderable_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "reg.yaml"
            registry.write_text(SAMPLE_REGISTRY, encoding="utf-8")
            entries = rld.load_renderable_registry(registry)
        self.assertEqual(len(entries), 3)
        ids = [e["id"] for e in entries]
        self.assertIn("chit-visual-tour-walkthrough", ids)
        self.assertIn("agnote-active-claims", ids)
        self.assertIn("chit-tour-public", ids)

    def test_tracked_section_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "reg.yaml"
            registry.write_text(SAMPLE_REGISTRY, encoding="utf-8")
            entries = rld.load_renderable_registry(registry)
        for e in entries:
            self.assertNotEqual(e["id"], "existing-thing")
            self.assertIn("source_doc", e)
            self.assertIn("output_key", e)
            self.assertIn("format", e)

    def test_empty_renderable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "reg.yaml"
            registry.write_text("tracked:\n  - id: a\n", encoding="utf-8")
            entries = rld.load_renderable_registry(registry)
        self.assertEqual(entries, [])


class DryRunTests(unittest.TestCase):
    def test_dry_run_writes_json_and_skips_http(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            source = tmpdir / "doc.md"
            source.write_text(SAMPLE_MD, encoding="utf-8")
            output = tmpdir / "doc.json"
            result = rld.render_one(
                source,
                output,
                renderer_url="http://127.0.0.1:1",  # never reached
                token=None,
                fmt="mp4",
                dry_run=True,
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertTrue(output.exists())
            # The dry-run output is the request body, not a real render.
            body = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(body["title"], "CHIT Visual Tour Walkthrough")
            self.assertTrue(body["merkle_root"].startswith("mkl_"))


# ---------------------------------------------------------------------------
# Mock HTTP server (full-path tests)
# ---------------------------------------------------------------------------


class _MockRenderer:
    """Tiny in-process renderer that pretends to render and serves the result.

    Stores one render per request under /render/provenance and serves the
    bytes back at /<key> so the script can exercise the download path.
    """

    def __init__(self) -> None:
        self.port = _free_port()
        self.received: list[dict] = []
        self.served: dict[str, bytes] = {}
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:  # silence
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b""
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    self.send_response(400)
                    self.end_headers()
                    return
                outer.received.append({"path": self.path, "body": payload})
                # Echo a fake-but-realistic response.
                key = f"a2ui/provenance/{int(time.time() * 1000)}-{os.urandom(2).hex()}.mp4"
                outer.served[key] = b"FAKE_MP4_BYTES_" + os.urandom(32)
                resp = {
                    "ok": True,
                    "url": f"http://127.0.0.1:{outer.port}/{key}",
                    "format": "mp4",
                    "duration_ms": payload.get("duration_ms", 12000),
                    "composition_id": "ProvenanceLivingDoc",
                    "merkle_root": payload.get("merkle_root", "mkl_xxx"),
                    "shape_id": payload.get("shape_id", "shape.doc.xxx"),
                    "title": payload.get("title", "Untitled"),
                }
                data = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                key = parsed.path.lstrip("/")
                if key in outer.served:
                    data = outer.served[key]
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_response(404)
                    self.end_headers()

        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2.0)


class FullPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock = _MockRenderer()
        self.mock.start()

    def tearDown(self) -> None:
        self.mock.stop()

    def test_render_one_full_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            source = tmpdir / "doc.md"
            source.write_text(SAMPLE_MD, encoding="utf-8")
            output = tmpdir / "out.mp4"
            result = rld.render_one(
                source,
                output,
                renderer_url=f"http://127.0.0.1:{self.mock.port}",
                token="test-jwt",
                fmt="mp4",
            )
            self.assertTrue(result["ok"])
            self.assertGreater(result["bytes"], 0)
            self.assertTrue(output.exists())
            # Confirm the bytes match what the mock served.
            self.assertEqual(
                output.read_bytes()[:15],
                b"FAKE_MP4_BYTES_",
            )
            # The mock should have received one POST with the expected shape.
            self.assertEqual(len(self.mock.received), 1)
            sent = self.mock.received[0]["body"]
            self.assertEqual(sent["title"], "CHIT Visual Tour Walkthrough")
            self.assertTrue(sent["merkle_root"].startswith("mkl_"))

    def test_render_registry_iterates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            registry = tmpdir / "reg.yaml"
            registry.write_text(SAMPLE_REGISTRY, encoding="utf-8")
            # We have to make the source files exist for the script to find
            # them; create stubs with minimal content.
            for entry_id, source_rel in [
                ("chit-visual-tour-walkthrough", "pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md"),
                ("agnote-active-claims", "pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"),
                ("chit-tour-public", "pmoves/docs/handoffs/chit-tour-public-edge.md"),
            ]:
                src = tmpdir / source_rel
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text(SAMPLE_MD, encoding="utf-8")
            output_dir = tmpdir / "rendered"
            results = rld.render_registry(
                registry,
                output_dir,
                renderer_url=f"http://127.0.0.1:{self.mock.port}",
                token="test-jwt",
                minio_bucket="outputs",
                repo_root=tmpdir,
            )
            self.assertEqual(len(results), 3)
            for r in results:
                self.assertTrue(r.get("ok"), r)
                self.assertIn("canonical_minio_key", r)
                self.assertTrue(
                    r["canonical_minio_key"].startswith("a2ui/living-docs/")
                )
            self.assertEqual(len(self.mock.received), 3)
            # Each render should have produced a file in output_dir.
            for r in results:
                self.assertTrue(Path(r["output"]).exists())


class ErrorPathTests(unittest.TestCase):
    def test_missing_source_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                rld.render_one(
                    Path(tmp) / "missing.md",
                    Path(tmp) / "out.mp4",
                    renderer_url="http://127.0.0.1:1",
                    token=None,
                    fmt="mp4",
                )

    def test_unsupported_format_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            source = tmpdir / "x.md"
            source.write_text(SAMPLE_MD, encoding="utf-8")
            with self.assertRaises(ValueError):
                rld.render_one(
                    source,
                    tmpdir / "out.xyz",
                    renderer_url="http://127.0.0.1:1",
                    token=None,
                    fmt="xyz",  # type: ignore[arg-type]
                )


# ---------------------------------------------------------------------------
# pytest entrypoint (so this file works under `pytest` as well as `python`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
