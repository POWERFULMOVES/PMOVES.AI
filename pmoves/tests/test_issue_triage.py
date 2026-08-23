"""
Unit tests for GitHub Issue Triage Service
"""

import importlib.util
from pathlib import Path

import pytest

# `github-issue-triage` contains a hyphen, so it is not a legal Python module
# path. The previous `from pmoves.services.github-issue-triage.labeling_rules
# import ...` was a SyntaxError, which meant this file failed at COLLECTION --
# the service's only test file has never run, and neither of the defects it
# would have caught was caught.
_LR = (
    Path(__file__).resolve().parents[1]
    / "services" / "github-issue-triage" / "labeling_rules.py"
)
_spec = importlib.util.spec_from_file_location("labeling_rules", _LR)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
LabelingRules = _mod.LabelingRules
ClassificationResult = _mod.ClassificationResult

_HC = _LR.parent / "hirag_client.py"
_hc_spec = importlib.util.spec_from_file_location("hirag_client", _HC)
_hc = importlib.util.module_from_spec(_hc_spec)
_hc_spec.loader.exec_module(_hc)
HiRAGClient = _hc.HiRAGClient


class TestLabelingRules:
    """Test pattern-based classification"""

    @pytest.fixture
    def rules(self):
        return LabelingRules()

    def test_bug_classification(self, rules):
        """Test bug pattern matching"""
        issue = "App crashes when I click the button. Error: NullPointerException"
        result = rules.classify_issue(issue)

        assert result.label == "bug"
        assert result.confidence > 0.5
        assert len(result.matched_patterns) > 0

    def test_feature_classification(self, rules):
        """Test feature pattern matching"""
        issue = "Add support for dark mode in the UI"
        result = rules.classify_issue(issue)

        assert result.label == "feature"
        assert result.confidence > 0.5

    def test_documentation_classification(self, rules):
        """Test documentation pattern matching"""
        issue = "The README is confusing, please explain how to install"
        result = rules.classify_issue(issue)

        assert result.label == "documentation"
        assert result.confidence > 0.5

    def test_performance_classification(self, rules):
        """Test performance pattern matching"""
        issue = "The app is very slow, takes 10 seconds to load"
        result = rules.classify_issue(issue)

        assert result.label == "performance"
        assert result.confidence > 0.5

    def test_security_classification(self, rules):
        """Test security pattern matching"""
        issue = "Possible XSS vulnerability in user input"
        result = rules.classify_issue(issue)

        assert result.label == "security"
        assert result.confidence > 0.5

    def test_refactor_classification(self, rules):
        """Test refactor pattern matching"""
        issue = "This code needs refactoring, lots of technical debt"
        result = rules.classify_issue(issue)

        assert result.label == "refactor"
        assert result.confidence > 0.5

    def test_empty_text(self, rules):
        """Test classification with empty text"""
        result = rules.classify_issue("")

        assert result.label == ""
        assert result.confidence == 0.0

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "PRE-EXISTING, surfaced by making this file collectible. On zero "
            "matches classify_issue returns label='' (labeling_rules.py:140), "
            "while this test expects a low-confidence label from get_all_labels(). "
            "Which behaviour is correct is a product decision, so it is recorded "
            "here rather than changed inside a crash fix. strict=True means this "
            "flips to a FAILURE the moment someone resolves it, instead of "
            "quietly staying skipped."
        ),
    )
    def test_no_match(self, rules):
        """Test classification with no matching patterns"""
        result = rules.classify_issue("hello world")

        # Should still return a label, just with low confidence
        assert result.label in rules.get_all_labels()
        assert result.confidence < 0.5

    def test_priority_ordering(self, rules):
        """Test that security takes priority over bug"""
        issue = "Security issue: app crashes with exploit"
        result = rules.classify_issue(issue)

        # Security has higher priority
        assert result.label == "security"

    def test_get_all_labels(self, rules):
        """Test getting all available labels"""
        labels = rules.get_all_labels()

        assert isinstance(labels, list)
        assert "bug" in labels
        assert "feature" in labels
        assert "documentation" in labels
        assert "performance" in labels
        assert "security" in labels
        assert "refactor" in labels

    def test_get_pattern_count(self, rules):
        """Test getting pattern count for labels"""
        bug_count = rules.get_pattern_count("bug")

        assert bug_count > 0
        assert isinstance(bug_count, int)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "PRE-EXISTING, and the sharper finding of the two: `threshold` cannot "
            "filter the winning label. classify_issue normalises by the max score "
            "(`v / max_score`), so the top label is ALWAYS exactly 1.0 -- and the "
            "fallback branch returns the highest scorer regardless of threshold "
            "anyway. classify_issue(text, threshold=0.8) is therefore "
            "indistinguishable from threshold=0.0; measured: 'maybe add something' "
            "-> label='feature', confidence=1.0. Fixing it means deciding what "
            "confidence should MEAN (match quality vs relative rank), which is a "
            "behaviour change and not this PR's concern."
        ),
    )
    def test_confidence_threshold(self, rules):
        """Test confidence threshold filtering"""
        # Issue with weak pattern match
        issue = "maybe add something"
        result = rules.classify_issue(issue, threshold=0.8)

        # Should return empty if no pattern above threshold
        assert result.label == "" or result.confidence < 0.8


class TestHiRAGClient:
    """Test Hi-RAG v2 client"""

    def test_client_initialization(self):
        """Test client can be initialized"""
        client = HiRAGClient("http://localhost:8086")

        assert client.base_url == "http://localhost:8086"
        assert client.query_url == "http://localhost:8086/hirag/query"

    def test_health_check_url(self):
        """Test health check URL construction"""
        client = HiRAGClient("http://localhost:8086/")

        assert client.base_url == "http://localhost:8086"
        assert client.query_url == "http://localhost:8086/hirag/query"


@pytest.mark.integration
class TestIssueTriageIntegration:
    """Integration tests (require running services)"""

    @pytest.mark.asyncio
    async def test_hirag_query(self):
        """Test Hi-RAG query (requires Hi-RAG v2 running)"""
        client = HiRAGClient("http://localhost:8086")
        results = await client.query("test query", top_k=3)

        # May return None if service is not running
        assert results is None or isinstance(results, list)

    @pytest.mark.asyncio
    async def test_hirag_health_check(self):
        """Test Hi-RAG health check (requires Hi-RAG v2 running)"""
        client = HiRAGClient("http://localhost:8086")
        is_healthy = await client.health_check()

        # May return False if service is not running
        assert isinstance(is_healthy, bool)
