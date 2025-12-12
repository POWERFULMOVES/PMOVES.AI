"""
Unit tests for consciousness_build.py

Tests the Kuhn consciousness taxonomy builder including:
- JSON taxonomy loading and parsing
- Chunk generation from categories, subcategories, theories
- HTML stripping and text normalization
- JSONL output formatting
"""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from consciousness_build import (
    Chunk,
    strip_html,
    load_full_taxonomy,
    collect_taxonomy_chunks,
    collect_chunks,
    write_jsonl,
    write_schema,
    build_query if hasattr(__import__('consciousness_build'), 'build_query') else None,
)


class TestStripHtml:
    """Tests for HTML stripping function."""

    def test_strip_simple_tags(self):
        """Remove basic HTML tags."""
        html = "<p>Hello <b>world</b></p>"
        result = strip_html(html)
        assert "Hello" in result
        assert "world" in result
        assert "<p>" not in result
        assert "<b>" not in result

    def test_strip_script_tags(self):
        """Remove script elements entirely."""
        html = "<p>Before</p><script>alert('bad')</script><p>After</p>"
        result = strip_html(html)
        assert "Before" in result
        assert "After" in result
        assert "alert" not in result
        assert "<script>" not in result

    def test_strip_style_tags(self):
        """Remove style elements entirely."""
        html = "<style>.foo { color: red; }</style><div>Content</div>"
        result = strip_html(html)
        assert "Content" in result
        assert "color" not in result

    def test_preserve_text_content(self):
        """Preserve meaningful text content."""
        html = "<div><h1>Title</h1><p>Paragraph text</p></div>"
        result = strip_html(html)
        assert "Title" in result
        assert "Paragraph text" in result

    def test_handle_br_tags(self):
        """Convert br tags to newlines."""
        html = "Line 1<br/>Line 2<br>Line 3"
        result = strip_html(html)
        assert "Line 1" in result
        assert "Line 2" in result

    def test_empty_input(self):
        """Handle empty input gracefully."""
        assert strip_html("") == ""

    def test_no_html(self):
        """Plain text passes through unchanged."""
        text = "Plain text content"
        result = strip_html(text)
        assert text.strip() == result.strip()


class TestLoadFullTaxonomy:
    """Tests for taxonomy JSON loading."""

    def test_load_valid_taxonomy(self):
        """Load valid taxonomy JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            taxonomy_dir = repo_root / "pmoves" / "data" / "consciousness"
            taxonomy_dir.mkdir(parents=True)

            taxonomy_data = {
                "version": "1.0",
                "categories": {
                    "test_category": {
                        "id": "test",
                        "description": "Test category description",
                        "theories": [
                            {
                                "name": "Test Theory",
                                "proponents": ["Test Author"],
                                "description": "A test theory."
                            }
                        ]
                    }
                }
            }

            taxonomy_path = taxonomy_dir / "kuhn_full_taxonomy.json"
            taxonomy_path.write_text(json.dumps(taxonomy_data))

            # Mock TAXONOMY_SUFFIX to match temp directory structure
            with mock.patch('consciousness_build.TAXONOMY_SUFFIX',
                          'pmoves/data/consciousness/kuhn_full_taxonomy.json'):
                result = load_full_taxonomy(repo_root)

            assert result.get("version") == "1.0"
            assert "categories" in result

    def test_load_missing_taxonomy(self):
        """Handle missing taxonomy file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = load_full_taxonomy(repo_root)
            assert result == {}

    def test_load_invalid_json(self):
        """Handle invalid JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            taxonomy_dir = repo_root / "pmoves" / "data" / "consciousness"
            taxonomy_dir.mkdir(parents=True)

            taxonomy_path = taxonomy_dir / "kuhn_full_taxonomy.json"
            taxonomy_path.write_text("{ invalid json }")

            with mock.patch('consciousness_build.TAXONOMY_SUFFIX',
                          'pmoves/data/consciousness/kuhn_full_taxonomy.json'):
                result = load_full_taxonomy(repo_root)

            assert result == {}


class TestCollectTaxonomyChunks:
    """Tests for chunk generation from taxonomy JSON."""

    def test_collect_chunks_from_theories(self):
        """Generate chunks from theories."""
        taxonomy = {
            "categories": {
                "integrated_information": {
                    "id": "iit",
                    "description": "Integrated Information Theory approaches",
                    "theories": [
                        {
                            "name": "IIT 3.0",
                            "proponents": ["Giulio Tononi"],
                            "description": "Consciousness is integrated information."
                        }
                    ]
                }
            }
        }

        chunks = collect_taxonomy_chunks(taxonomy)

        # Should have category chunk + theory chunk
        assert len(chunks) >= 2

        # Check category chunk exists
        cat_chunks = [c for c in chunks if "Category Overview" in c.title]
        assert len(cat_chunks) == 1

        # Check theory chunk exists
        theory_chunks = [c for c in chunks if "IIT 3.0" in c.title]
        assert len(theory_chunks) == 1
        assert "Giulio Tononi" in theory_chunks[0].content

    def test_collect_chunks_with_subcategories(self):
        """Generate chunks from subcategories."""
        taxonomy = {
            "categories": {
                "computational": {
                    "id": "comp",
                    "description": "Computational approaches",
                    "subcategories": {
                        "global_workspace": {
                            "description": "Global Workspace Theory variants",
                            "theories": [
                                {
                                    "name": "GWT",
                                    "proponents": ["Bernard Baars"],
                                    "description": "Global workspace model."
                                }
                            ]
                        }
                    }
                }
            }
        }

        chunks = collect_taxonomy_chunks(taxonomy)

        # Should have category + subcategory + theory chunks
        assert len(chunks) >= 3

        # Check subcategory chunk exists
        subcat_chunks = [c for c in chunks if "Subcategory" in c.title]
        assert len(subcat_chunks) >= 1

    def test_collect_chunks_empty_taxonomy(self):
        """Handle empty taxonomy gracefully."""
        taxonomy = {}
        chunks = collect_taxonomy_chunks(taxonomy)
        assert chunks == []

        taxonomy2 = {"categories": {}}
        chunks2 = collect_taxonomy_chunks(taxonomy2)
        assert chunks2 == []

    def test_chunk_ids_are_unique(self):
        """Verify generated chunk IDs are unique."""
        taxonomy = {
            "categories": {
                "cat1": {
                    "id": "c1",
                    "description": "Category 1",
                    "theories": [
                        {"name": "Theory A", "proponents": [], "description": "A"},
                        {"name": "Theory B", "proponents": [], "description": "B"},
                    ]
                },
                "cat2": {
                    "id": "c2",
                    "description": "Category 2",
                    "theories": [
                        {"name": "Theory C", "proponents": [], "description": "C"},
                    ]
                }
            }
        }

        chunks = collect_taxonomy_chunks(taxonomy)
        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids)), "Chunk IDs should be unique"


class TestWriteJsonl:
    """Tests for JSONL output writing."""

    def test_write_jsonl_format(self):
        """Verify JSONL format is correct."""
        chunks = [
            Chunk(
                chunk_id="test-1",
                title="Test Chunk",
                url="https://example.com",
                category="test",
                content="Test content here"
            ),
            Chunk(
                chunk_id="test-2",
                title="Another Chunk",
                url=None,
                category="test",
                content="More content"
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output" / "chunks.jsonl"
            write_jsonl(chunks, output_path)

            assert output_path.exists()

            lines = output_path.read_text().strip().split("\n")
            assert len(lines) == 2

            # Verify each line is valid JSON
            for line in lines:
                data = json.loads(line)
                assert "id" in data
                assert "title" in data
                assert "content" in data
                assert "namespace" in data
                assert data["namespace"] == "pmoves.consciousness"

    def test_write_jsonl_unicode(self):
        """Handle unicode content correctly."""
        chunks = [
            Chunk(
                chunk_id="unicode-1",
                title="Théorie quantique",
                url=None,
                category="test",
                content="Émergence de la conscience"
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "unicode.jsonl"
            write_jsonl(chunks, output_path)

            content = output_path.read_text(encoding="utf-8")
            data = json.loads(content.strip())
            assert data["title"] == "Théorie quantique"


class TestWriteSchema:
    """Tests for SQL schema generation."""

    def test_write_schema_creates_file(self):
        """Verify schema file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.sql"
            write_schema(schema_path)

            assert schema_path.exists()
            content = schema_path.read_text()

            assert "create table" in content.lower()
            assert "consciousness_theories" in content
            assert "primary key" in content.lower()


class TestCollectChunks:
    """Tests for full chunk collection including file sources."""

    def test_collect_chunks_taxonomy_only(self):
        """Collect chunks from taxonomy when no files exist."""
        taxonomy = {
            "categories": {
                "test": {
                    "id": "t",
                    "description": "Test",
                    "theories": [
                        {"name": "Theory", "proponents": [], "description": "Desc"}
                    ]
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "harvest"
            base.mkdir()

            chunks = collect_chunks(base, taxonomy)

            # Should have taxonomy chunks
            assert len(chunks) >= 2

    def test_collect_chunks_creates_placeholder_when_empty(self):
        """Create placeholder chunk when no content found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "harvest"
            base.mkdir()

            chunks = collect_chunks(base, {})

            # Should have placeholder chunk
            assert len(chunks) == 1
            assert "placeholder" in chunks[0].category


class TestChunkDataclass:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self):
        """Create a Chunk instance."""
        chunk = Chunk(
            chunk_id="test-123",
            title="Test Title",
            url="https://example.com",
            category="test-cat",
            content="Test content"
        )

        assert chunk.chunk_id == "test-123"
        assert chunk.title == "Test Title"
        assert chunk.url == "https://example.com"
        assert chunk.category == "test-cat"
        assert chunk.content == "Test content"

    def test_chunk_with_none_url(self):
        """Chunk can have None URL."""
        chunk = Chunk(
            chunk_id="test",
            title="Title",
            url=None,
            category="cat",
            content="content"
        )

        assert chunk.url is None
