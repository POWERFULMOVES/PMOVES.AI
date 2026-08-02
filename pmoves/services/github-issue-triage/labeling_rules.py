"""
Labeling Rules for Issue Triage

Pattern-based classification for GitHub issues when semantic search
is unavailable or as a fallback mechanism.

Categories:
  - bug: Defects, errors, crashes, broken functionality
  - feature: New features, enhancements, additions
  - documentation: Documentation issues, README, guides
  - performance: Performance-related issues
  - security: Security vulnerabilities
  - refactor: Code quality, refactoring requests
"""

import re
from typing import List
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    """Result of pattern-based classification"""
    label: str
    confidence: float
    reasoning: str
    matched_patterns: List[str]


class LabelingRules:
    """
    Pattern-based issue classification using regex and keyword matching
    """

    # Bug patterns - defects, errors, crashes
    BUG_PATTERNS = [
        r'\b(bug|broken|crash|error|fail|issue|problem|wrong|incorrect|not work|doesn\'t work|fix|patch)\b',
        r'\b(exception|traceback|stack trace|panic|fatal|segfault|undefined|null pointer)\b',
        r'\b(regression|broke|stopped working|used to work|no longer)\b',
        r'\b(missing|absent|removed|deleted|disappeared)\b.*\b(but should|expected|should be)\b',
    ]

    # Feature patterns - new features, enhancements
    FEATURE_PATTERNS = [
        r'\b(add|implement|new|introduce|support|feature|enhancement|request)\b',
        r'\b(would like|wish for|it would be (great|nice|useful|helpful))\b',
        r'\b(can we|could we|please add|is it possible to)\b',
        r'\b(ability to|option to|way to)\b.*(add|create|make|do)\b',
    ]

    # Documentation patterns
    DOCUMENTATION_PATTERNS = [
        r'\b(docs?|documentation|readme|guide|tutorial|example|comment)\b',
        r'\b(clarify|explain|describe|document|how to|how do i)\b',
        r'\b(confusing|unclear|ambiguous|missing doc)\b',
        r'\b(typo|spelling|grammar|formatting)\b.*\b(docs?|readme|comment)\b',
    ]

    # Performance patterns
    PERFORMANCE_PATTERNS = [
        r'\b(slow|sluggish|lag|latency|delay|timeout|performance)\b',
        r'\b(optimize|optimization|speed up|faster|improve performance)\b',
        r'\b(memory leak|high memory|memory usage|cpu usage|resource)\b',
        r'\b(scale|scalability|bottleneck|efficient|inefficient)\b',
    ]

    # Security patterns
    SECURITY_PATTERNS = [
        r'\b(security|vulnerability|exploit|xss|csrf|injection)\b',
        r'\b(authentication|authorization|permission|access control)\b',
        r'\b(encrypt|decrypt|hash|salt|credential|password leak)\b',
        r'\b(sanitize|validate|escape|security hole)\b',
    ]

    # Refactor patterns
    REFACTOR_PATTERNS = [
        r'\b(refactor|clean up|restructure|reorganize|rework)\b',
        r'\b(code smell|technical debt|maintainability|readability)\b',
        r'\b(deprecate|remove unused|simplify|consolidate)\b',
        r'\b(better code quality|improve code|code style)\b',
    ]

    def __init__(self):
        """Compile regex patterns for performance"""
        self._compiled_patterns = {
            'bug': [re.compile(p, re.IGNORECASE) for p in self.BUG_PATTERNS],
            'feature': [re.compile(p, re.IGNORECASE) for p in self.FEATURE_PATTERNS],
            'documentation': [re.compile(p, re.IGNORECASE) for p in self.DOCUMENTATION_PATTERNS],
            'performance': [re.compile(p, re.IGNORECASE) for p in self.PERFORMANCE_PATTERNS],
            'security': [re.compile(p, re.IGNORECASE) for p in self.SECURITY_PATTERNS],
            'refactor': [re.compile(p, re.IGNORECASE) for p in self.REFACTOR_PATTERNS],
        }

        # Priority order (higher priority checked first)
        self._priority = ['security', 'bug', 'feature', 'performance', 'documentation', 'refactor']

    def classify_issue(self, issue_text: str, threshold: float = 0.5) -> ClassificationResult:
        """
        Classify issue using pattern matching

        Args:
            issue_text: Issue title and body text
            threshold: Minimum confidence threshold

        Returns:
            ClassificationResult with label and confidence
        """
        if not issue_text:
            return ClassificationResult(
                label='',
                confidence=0.0,
                reasoning='No text provided',
                matched_patterns=[]
            )

        issue_text.lower()

        # Score each category
        scores = {}
        matched_patterns = {}

        for label, patterns in self._compiled_patterns.items():
            score = 0
            matches = []

            for pattern in patterns:
                pattern_matches = pattern.findall(issue_text)
                if pattern_matches:
                    score += len(pattern_matches)
                    matches.extend([m for m in pattern_matches])

            if score > 0:
                scores[label] = score
                matched_patterns[label] = matches

        # Normalize scores (0-1 range)
        if not scores:
            return ClassificationResult(
                label='',
                confidence=0.0,
                reasoning='No patterns matched',
                matched_patterns=[]
            )

        max_score = max(scores.values())
        normalized_scores = {k: v / max_score for k, v in scores.items()}

        # Select highest priority label above threshold
        for label in self._priority:
            if label in normalized_scores and normalized_scores[label] >= threshold:
                return ClassificationResult(
                    label=label,
                    confidence=normalized_scores[label],
                    reasoning=f"Matched {scores[label]} pattern(s) for '{label}'",
                    matched_patterns=matched_patterns[label]
                )

        # If no label above threshold, return highest scoring
        best_label = max(normalized_scores, key=normalized_scores.get)
        return ClassificationResult(
            label=best_label,
            confidence=normalized_scores[best_label],
            reasoning=f"Best match: {scores[best_label]} pattern(s) for '{best_label}'",
            matched_patterns=matched_patterns[best_label]
        )

    def get_all_labels(self) -> List[str]:
        """Get all available labels"""
        return list(self._compiled_patterns.keys())

    def get_pattern_count(self, label: str) -> int:
        """Get number of patterns for a label"""
        return len(self._compiled_patterns.get(label, []))
