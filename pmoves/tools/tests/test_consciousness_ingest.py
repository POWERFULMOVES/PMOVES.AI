"""
Unit tests for consciousness_ingest.py

Tests the YouTube ingestion helper including:
- JSONL chunk reading
- Query building from chunks
- Video mapping load/save
- PMOVES.YT API interaction (mocked)
"""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from consciousness_ingest import (
    Chunk,
    read_chunks,
    build_query,
    load_video_map,
    save_video_map,
)


class TestReadChunks:
    """Tests for JSONL chunk reading."""

    def test_read_valid_chunks(self):
        """Read valid JSONL chunks file."""
        chunks_data = [
            {"id": "chunk-1", "title": "Theory One", "category": "cat1", "content": "Content 1"},
            {"id": "chunk-2", "title": "Theory Two", "category": "cat2", "content": "Content 2"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for chunk in chunks_data:
                f.write(json.dumps(chunk) + "\n")
            f.flush()

            result = read_chunks(Path(f.name))

        assert len(result) == 2
        assert result[0].chunk_id == "chunk-1"
        assert result[0].title == "Theory One"
        assert result[1].chunk_id == "chunk-2"

    def test_read_chunks_with_empty_lines(self):
        """Skip empty lines in JSONL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": "chunk-1", "title": "Theory", "category": "cat", "content": "c"}\n')
            f.write('\n')  # empty line
            f.write('{"id": "chunk-2", "title": "Theory 2", "category": "cat", "content": "c"}\n')
            f.flush()

            result = read_chunks(Path(f.name))

        assert len(result) == 2

    def test_read_chunks_missing_fields(self):
        """Handle chunks with missing optional fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": "chunk-1"}\n')  # minimal fields
            f.flush()

            result = read_chunks(Path(f.name))

        assert len(result) == 1
        assert result[0].chunk_id == "chunk-1"
        assert result[0].title == "Untitled"  # default value
        assert result[0].category == "general"  # default value


class TestBuildQuery:
    """Tests for search query generation."""

    def test_build_query_simple(self):
        """Build query from chunk title."""
        chunk = Chunk(
            chunk_id="test",
            title="Integrated Information Theory",
            category="computational",
            content="Theory content"
        )

        query = build_query(chunk)

        assert "Integrated Information Theory" in query
        assert "interview" in query

    def test_build_query_includes_category(self):
        """Query includes category when not in title."""
        chunk = Chunk(
            chunk_id="test",
            title="IIT 3.0",
            category="neuroscience",
            content="Content"
        )

        query = build_query(chunk)

        assert "IIT 3.0" in query
        assert "neuroscience" in query

    def test_build_query_category_in_title(self):
        """Don't duplicate category if already in title."""
        chunk = Chunk(
            chunk_id="test",
            title="Quantum consciousness theory",
            category="quantum",
            content="Content"
        )

        query = build_query(chunk)

        # Category "quantum" is already in title "Quantum consciousness"
        # so it should just add "interview"
        assert "Quantum consciousness theory" in query


class TestVideoMapIO:
    """Tests for video mapping load/save."""

    def test_load_video_map_existing(self):
        """Load existing video mapping."""
        mapping_data = [
            {"chunk_id": "c1", "video_id": "v1", "video_url": "https://yt/v1"},
            {"chunk_id": "c2", "video_id": "v2", "video_url": "https://yt/v2"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(mapping_data, f)
            f.flush()

            result = load_video_map(Path(f.name))

        assert "c1" in result
        assert "c2" in result
        assert result["c1"]["video_id"] == "v1"

    def test_load_video_map_missing(self):
        """Return empty dict for missing file."""
        result = load_video_map(Path("/nonexistent/path.json"))
        assert result == {}

    def test_load_video_map_invalid_json(self):
        """Return empty dict for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            f.flush()

            result = load_video_map(Path(f.name))

        assert result == {}

    def test_save_video_map(self):
        """Save video mapping to file."""
        mapping = {
            "chunk-1": {
                "chunk_id": "chunk-1",
                "video_id": "video-1",
                "video_url": "https://youtube.com/watch?v=video-1"
            },
            "chunk-2": {
                "chunk_id": "chunk-2",
                "video_id": "video-2",
                "video_url": "https://youtube.com/watch?v=video-2"
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "mapping.json"
            save_video_map(output_path, mapping)

            assert output_path.exists()

            loaded = json.loads(output_path.read_text())
            assert len(loaded) == 2
            # Should be sorted by chunk_id
            assert loaded[0]["chunk_id"] == "chunk-1"
            assert loaded[1]["chunk_id"] == "chunk-2"


class TestChunkDataclass:
    """Tests for ingest Chunk dataclass."""

    def test_chunk_creation(self):
        """Create a Chunk instance."""
        chunk = Chunk(
            chunk_id="test-123",
            title="Test Theory",
            category="consciousness",
            content="Theory description"
        )

        assert chunk.chunk_id == "test-123"
        assert chunk.title == "Test Theory"
        assert chunk.category == "consciousness"
        assert chunk.content == "Theory description"


class TestIngestVideoMocked:
    """Tests for video ingestion with mocked HTTP."""

    @mock.patch('consciousness_ingest.requests')
    def test_ingest_video_dry_run(self, mock_requests):
        """Dry run doesn't call API."""
        from consciousness_ingest import ingest_video

        video_info = {
            "id": "test-vid",
            "url": "https://youtube.com/watch?v=test-vid",
            "title": "Test Video"
        }
        chunk = Chunk("c1", "Theory", "cat", "content")

        ingest_video("http://localhost:8077", video_info, "test.namespace", chunk, dry_run=True)

        # Should not call API in dry run mode
        mock_requests.post.assert_not_called()

    @mock.patch('consciousness_ingest.requests')
    def test_ingest_video_calls_api(self, mock_requests):
        """Real run calls API endpoints."""
        from consciousness_ingest import ingest_video

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        video_info = {
            "id": "test-vid",
            "url": "https://youtube.com/watch?v=test-vid",
            "title": "Test Video"
        }
        chunk = Chunk("c1", "Theory", "cat", "content")

        ingest_video("http://localhost:8077", video_info, "test.namespace", chunk, dry_run=False)

        # Should call both /yt/ingest and /yt/emit
        assert mock_requests.post.call_count == 2


class TestHealthCheck:
    """Tests for health check function."""

    @mock.patch('consciousness_ingest.requests')
    def test_ensure_health_success(self, mock_requests):
        """Health check passes on 200."""
        from consciousness_ingest import ensure_health

        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_requests.get.return_value = mock_response

        # Should not raise
        ensure_health("http://localhost:8077")

        mock_requests.get.assert_called_once()

    @mock.patch('consciousness_ingest.requests')
    def test_ensure_health_failure(self, mock_requests):
        """Health check raises on failure."""
        from consciousness_ingest import ensure_health

        mock_requests.get.side_effect = Exception("Connection refused")

        with pytest.raises(RuntimeError, match="health check failed"):
            ensure_health("http://localhost:8077")
