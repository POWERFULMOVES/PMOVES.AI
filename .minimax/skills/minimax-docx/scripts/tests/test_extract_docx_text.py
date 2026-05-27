"""Self-contained tests for ``extract_docx_text.py``.

These tests build small synthetic DOCX files in memory and assert that the
content-truth extractor surfaces the side channels (hyperlinks, footnotes,
endnotes, comments, track changes, text boxes, headers/footers, table
structure) without silently dropping them.

Run from the repo root:

    python3 -m unittest packages/daemon/skills/minimax-docx/scripts/tests/test_extract_docx_text.py

The tests are stdlib-only.  They do **not** require ``python-docx``,
``pandoc``, or ``dotnet`` — only the Python standard library.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = HERE.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import extract_docx_text as ext  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic DOCX builder
# ---------------------------------------------------------------------------


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
  <Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>
  <Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rIdFn" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
  <Relationship Id="rIdEn" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes" Target="endnotes.xml"/>
  <Relationship Id="rIdCm" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>
  <Relationship Id="rIdHd" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFt" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rIdLink1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com/page" TargetMode="External"/>
  <Relationship Id="rIdLink2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com/two" TargetMode="External"/>
</Relationships>"""

_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}">
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style>
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>"""

_FOOTNOTES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="{W}">
  <w:footnote w:id="0" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="1" w:type="continuationSeparator"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>
  <w:footnote w:id="2"><w:p><w:r><w:t>Footnote body for note 2.</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="3"><w:p><w:r><w:t>Footnote with </w:t></w:r><w:r><w:t>multi-run text.</w:t></w:r></w:p></w:footnote>
</w:footnotes>"""

_ENDNOTES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:endnotes xmlns:w="{W}">
  <w:endnote w:id="0" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:endnote>
  <w:endnote w:id="1" w:type="continuationSeparator"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:endnote>
  <w:endnote w:id="5"><w:p><w:r><w:t>Endnote body.</w:t></w:r></w:p></w:endnote>
</w:endnotes>"""

_COMMENTS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="{W}">
  <w:comment w:id="0" w:author="Alice" w:date="2025-04-01T10:00:00Z"><w:p><w:r><w:t>Please clarify.</w:t></w:r></w:p></w:comment>
  <w:comment w:id="1" w:author="Bob" w:date="2025-04-02T11:00:00Z"><w:p><w:r><w:t>Looks good.</w:t></w:r></w:p></w:comment>
</w:comments>"""

_HEADER = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>Page header.</w:t></w:r></w:p></w:hdr>"""

_FOOTER = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{W}"><w:p><w:r><w:t>Page footer.</w:t></w:r></w:p></w:ftr>"""

_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>The Title</w:t></w:r></w:p>
    <w:p><w:r><w:t>An ordinary paragraph with </w:t></w:r><w:hyperlink r:id="rIdLink1"><w:r><w:t>a link</w:t></w:r></w:hyperlink><w:r><w:t> in the middle.</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t>Paragraph with </w:t></w:r>
      <w:r><w:footnoteReference w:id="2"/></w:r>
      <w:r><w:t> footnote and </w:t></w:r>
      <w:r><w:endnoteReference w:id="5"/></w:r>
      <w:r><w:t> endnote.</w:t></w:r>
    </w:p>
    <w:p>
      <w:commentRangeStart w:id="0"/>
      <w:r><w:t>Annotated sentence.</w:t></w:r>
      <w:commentRangeEnd w:id="0"/>
      <w:r><w:commentReference w:id="0"/></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>Before. </w:t></w:r>
      <w:ins w:id="100" w:author="Reviewer" w:date="2025-01-01T00:00:00Z"><w:r><w:t>Inserted phrase. </w:t></w:r></w:ins>
      <w:del w:id="101" w:author="Reviewer" w:date="2025-01-01T00:00:00Z"><w:r><w:delText>Deleted phrase. </w:delText></w:r></w:del>
      <w:r><w:t>After.</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tblPr/>
      <w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="2000"/></w:tblGrid>
      <w:tr>
        <w:tc><w:tcPr/><w:p><w:r><w:t>R1C1</w:t></w:r></w:p></w:tc>
        <w:tc><w:tcPr/><w:p><w:r><w:t>R1C2 with </w:t></w:r><w:hyperlink r:id="rIdLink2"><w:r><w:t>cell link</w:t></w:r></w:hyperlink></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:tcPr/><w:p><w:r><w:t>R2C1</w:t></w:r></w:p></w:tc>
        <w:tc><w:tcPr/><w:p><w:r><w:t>R2C2</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p>
      <w:r>
        <w:pict>
          <v:shape id="_x0000_s1026" type="#_x0000_t202" style="width:100pt;height:50pt">
            <v:textbox><w:txbxContent><w:p><w:r><w:t>Inside the textbox.</w:t></w:r></w:p></w:txbxContent></v:textbox>
          </v:shape>
        </w:pict>
      </w:r>
    </w:p>
    <w:sectPr>
      <w:headerReference w:type="default" r:id="rIdHd"/>
      <w:footerReference w:type="default" r:id="rIdFt"/>
    </w:sectPr>
  </w:body>
</w:document>"""


def build_synthetic_docx(target: Path) -> None:
    parts = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _ROOT_RELS,
        "word/_rels/document.xml.rels": _DOC_RELS,
        "word/document.xml": _DOCUMENT,
        "word/styles.xml": _STYLES,
        "word/footnotes.xml": _FOOTNOTES,
        "word/endnotes.xml": _ENDNOTES,
        "word/comments.xml": _COMMENTS,
        "word/header1.xml": _HEADER,
        "word/footer1.xml": _FOOTER,
    }
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in parts.items():
            zf.writestr(name, content)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class ExtractContentTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.docx = Path(cls.tmp.name) / "synthetic.docx"
        build_synthetic_docx(cls.docx)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    # --- text mode -------------------------------------------------------

    def test_text_default_includes_hyperlink_target(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("a link (\u2192 https://example.com/page)", rendered)

    def test_text_default_inlines_footnote_marker_and_section(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("[fn:2]", rendered)
        self.assertIn("FOOTNOTES", rendered)
        self.assertIn("Footnote body for note 2.", rendered)

    def test_text_default_inlines_endnote_marker_and_section(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("[en:5]", rendered)
        self.assertIn("ENDNOTES", rendered)
        self.assertIn("Endnote body.", rendered)

    def test_text_default_inlines_comment_marker_and_section(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("[cmt:0]", rendered)
        self.assertIn("COMMENTS", rendered)
        self.assertIn("Alice", rendered)
        self.assertIn("Please clarify.", rendered)

    def test_text_default_emits_table_rows_separately(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        # each row on its own line, not concatenated into a single garbage string
        self.assertIn("R1C1 |", rendered)
        self.assertIn("R2C1 |", rendered)
        # cell-level hyperlink target preserved
        self.assertIn("cell link (\u2192 https://example.com/two)", rendered)

    def test_text_default_lists_textbox_text(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("TEXT BOXES", rendered)
        self.assertIn("Inside the textbox.", rendered)

    def test_text_default_omits_headers_footers(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertNotIn("Page header.", rendered)
        self.assertNotIn("Page footer.", rendered)

    def test_text_with_headers_footers_attribution(self):
        opts = ext.Options(fmt="text", include_headers=True, include_footers=True)
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("HEADERS", rendered)
        self.assertIn("section=0 role=default", rendered)
        self.assertIn("Page header.", rendered)
        self.assertIn("FOOTERS", rendered)
        self.assertIn("Page footer.", rendered)

    # --- revision policy -------------------------------------------------

    def test_revisions_accept_drops_deletions(self):
        opts = ext.Options(fmt="text")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertNotIn("Deleted phrase.", rendered)
        self.assertIn("Inserted phrase.", rendered)
        # warning reports the drop loudly
        self.assertTrue(any("dropped" in w and "del" in w for w in result.warnings))

    def test_revisions_reject_drops_insertions(self):
        opts = ext.Options(fmt="text", revisions="reject")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertNotIn("Inserted phrase.", rendered)
        # deleted text comes back via <w:delText>
        self.assertIn("Deleted phrase.", rendered)
        self.assertTrue(any("dropped" in w and "ins" in w for w in result.warnings))

    def test_revisions_raw_keeps_both(self):
        opts = ext.Options(fmt="text", revisions="raw")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_text(result, opts)
        self.assertIn("Inserted phrase.", rendered)
        self.assertIn("Deleted phrase.", rendered)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.revisions["rawInsertions"], 1)
        self.assertEqual(result.revisions["rawDeletions"], 1)
        self.assertEqual(result.revisions["retainedInsertions"], 1)
        self.assertEqual(result.revisions["retainedDeletions"], 1)

    # --- json mode -------------------------------------------------------

    def test_json_payload_has_full_content_truth(self):
        opts = ext.Options(fmt="json", include_headers=True, include_footers=True)
        result = ext.extract(self.docx, opts)
        payload = json.loads(ext.render_json(result, opts, self.docx))

        self.assertEqual(payload["file"], str(self.docx))

        # body order: heading, hyperlink p, footnote/endnote p, comment p,
        # revisions p, table, textbox p
        kinds = [b["kind"] for b in payload["body"]]
        self.assertEqual(kinds[0], "paragraph")
        self.assertEqual(payload["body"][0]["style"], "Heading1")
        self.assertEqual(payload["body"][0]["styleName"], "heading 1")
        self.assertIn("table", kinds)

        # hyperlinks gathered globally
        targets = sorted(h["target"] for h in payload["hyperlinks"])
        self.assertEqual(
            targets, ["https://example.com/page", "https://example.com/two"]
        )

        # footnotes / endnotes / comments present
        self.assertEqual(len(payload["footnotes"]), 2)
        self.assertEqual(payload["footnotes"][0]["id"], "2")
        self.assertIn("multi-run text", payload["footnotes"][1]["text"])
        self.assertEqual(payload["endnotes"][0]["id"], "5")
        self.assertEqual(payload["comments"][0]["author"], "Alice")

        # textbox + headers + footers reported
        self.assertEqual(payload["textboxes"][0]["text"], "Inside the textbox.")
        self.assertEqual(payload["headers"][0]["text"], "Page header.")
        self.assertEqual(payload["footers"][0]["text"], "Page footer.")
        self.assertEqual(payload["headers"][0]["role"], "default")

        # table is structured rows-of-cells-of-paragraphs, not a flat string
        table_block = next(b for b in payload["body"] if b["kind"] == "table")
        self.assertEqual(len(table_block["rows"]), 2)
        self.assertEqual(len(table_block["rows"][0]), 2)
        self.assertEqual(table_block["rows"][0][0][0]["text"], "R1C1")
        self.assertIn("cell link", table_block["rows"][0][1][0]["text"])

    # --- explicit drop warnings -----------------------------------------

    def test_dropping_footnotes_emits_warning(self):
        opts = ext.Options(fmt="text", include_footnotes=False)
        result = ext.extract(self.docx, opts)
        # body still has [fn:2] reference -> warning fires
        self.assertTrue(
            any("footnote references in body were ignored" in w for w in result.warnings)
        )

    def test_dropping_comments_emits_warning(self):
        opts = ext.Options(fmt="text", include_comments=False)
        result = ext.extract(self.docx, opts)
        self.assertTrue(
            any("comment references in body were ignored" in w for w in result.warnings)
        )

    # --- markdown mode ---------------------------------------------------

    def test_markdown_renders_heading_and_table(self):
        opts = ext.Options(fmt="markdown")
        result = ext.extract(self.docx, opts)
        rendered = ext.render_markdown(result, opts)
        self.assertIn("# The Title", rendered)
        self.assertIn("| R1C1 |", rendered)
        self.assertIn("## Footnotes", rendered)
        self.assertIn("## Comments", rendered)


class CliEntrypoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.docx = Path(cls.tmp.name) / "cli.docx"
        build_synthetic_docx(cls.docx)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _run(self, *args: str) -> str:
        captured = io.StringIO()
        old_stdout, sys.stdout = sys.stdout, captured
        try:
            ext.main([str(self.docx), *args])
        finally:
            sys.stdout = old_stdout
        return captured.getvalue()

    def test_cli_text_default(self):
        out = self._run()
        self.assertIn("The Title", out)
        self.assertIn("https://example.com/page", out)

    def test_cli_json_payload_parses(self):
        out = self._run("--format", "json")
        payload = json.loads(out)
        self.assertIn("body", payload)
        self.assertEqual(payload["options"]["format"], "json")


if __name__ == "__main__":
    unittest.main()
