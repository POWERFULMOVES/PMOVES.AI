from __future__ import annotations

import logging
import math
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger("hirag.gateway.v2.gan")


@dataclass
class CandidateEvaluation:
    """Container holding the sidecar decision for a single candidate."""

    candidate_id: Optional[str]
    original_text: str
    text: str
    score: float
    model_score: float
    rule_score: float
    critique: Dict[str, Any]
    edits: int = 0
    accepted: bool = False
    rejected: bool = False
    telemetry: Dict[str, Any] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.candidate_id,
            "text": self.text,
            "original_text": self.original_text,
            "score": round(self.score, 4),
            "model_score": round(self.model_score, 4),
            "rule_score": round(self.rule_score, 4),
            "critique": self.critique,
            "edits": self.edits,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "telemetry": self.telemetry,
            "source": self.source,
        }


class GanSidecar:
    """Lightweight GAN-style gatekeeper for geometry decodes.

    The checker blends:
      * rule-based heuristics (format and policy checks), and
      * a compact logistic model over simple text features.

    The design mirrors the roadmap notes – this module runs synchronously and
    is gated by an environment flag in the FastAPI layer.
    """

    #: simple regex based policy guard – tweakable without retraining
    _BANNED_PATTERNS = [
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bTODO\b",
            r"\bLOREM\s+IPSUM\b",
            r"\bhttp://",
            r"\bhttps://",
            r"\b(?:fuck|shit|damn)\b",
        )
    ]

    def __init__(self) -> None:
        self.accept_threshold = 0.55
        self._weights = {
            "length": 1.25,
            "sentence_density": 0.9,
            "unique_ratio": 0.8,
            "uppercase_ratio": -0.6,
            "digit_ratio": -0.4,
            "punctuation_ratio": 0.35,
        }
        self._bias = -0.6

    # ------------------------------------------------------------------
    # Feature helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t for t in re.split(r"[^A-Za-z0-9']+", text) if t]

    def _feature_length(self, text: str) -> float:
        length = len(text.strip())
        return min(length / 400.0, 1.5)

    def _feature_sentence_density(self, text: str) -> float:
        sentences = max(text.count(".") + text.count("!") + text.count("?"), 1)
        words = max(len(self._tokenize(text)), 1)
        return min(sentences / words * 12.0, 1.0)

    def _feature_unique_ratio(self, text: str) -> float:
        tokens = self._tokenize(text)
        if not tokens:
            return 0.0
        return len(set(t.lower() for t in tokens)) / len(tokens)

    def _feature_uppercase_ratio(self, text: str) -> float:
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return 0.0
        upper = sum(1 for c in letters if c.isupper())
        return upper / len(letters)

    def _feature_digit_ratio(self, text: str) -> float:
        digits = sum(1 for c in text if c.isdigit())
        return digits / max(len(text), 1)

    def _feature_punctuation_ratio(self, text: str) -> float:
        punct = sum(1 for c in text if c in {",", ";", ":"})
        return punct / max(len(text), 1)

    # ------------------------------------------------------------------
    # Scoring and critique
    # ------------------------------------------------------------------
    def _logistic(self, value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def _model_predict(self, features: Dict[str, float]) -> float:
        dot = self._bias
        for name, weight in self._weights.items():
            dot += weight * features.get(name, 0.0)
        return self._logistic(dot)

    def _rule_checks(self, text: str) -> Dict[str, Any]:
        stripped = text.strip()
        tokens = self._tokenize(text)
        flagged = []
        for pattern in self._BANNED_PATTERNS:
            match = pattern.search(stripped)
            if match:
                flagged.append(match.group(0))
        format_ok = bool(stripped) and len(tokens) >= 4
        sentences = max(stripped.count(".") + stripped.count("!") + stripped.count("?"), 1)
        avg_sentence_len = len(tokens) / sentences
        if avg_sentence_len < 4:
            format_ok = False
        hint: str
        if flagged:
            hint = "Remove prohibited phrases before returning to caller."
        elif not format_ok:
            hint = "Expand the summary with clearer sentences."
        else:
            hint = "Looks good; ensure final answer keeps concise details."
        safety_penalty = min(len(flagged) * 0.25, 0.75)
        rule_score = max(0.0, 1.0 - safety_penalty)
        return {
            "format_ok": format_ok,
            "flagged_terms": flagged,
            "avg_sentence_length": round(avg_sentence_len, 2) if tokens else 0.0,
            "hint": hint,
            "safety_score": round(1.0 - safety_penalty, 3),
            "rule_score": rule_score,
        }

    def _apply_edits(self, text: str, critique: Dict[str, Any], max_edits: int) -> tuple[str, int]:
        edits = 0
        revised = text
        if max_edits <= 0:
            return revised, edits
        if critique.get("flagged_terms"):
            escaped_terms = [re.escape(term) for term in critique["flagged_terms"]]
            pattern = re.compile(r"|".join(escaped_terms), re.IGNORECASE)
            revised = pattern.sub("", revised)
            edits += 1
        if edits < max_edits and not critique.get("format_ok", True):
            revised = revised.strip()
            if revised and not revised.endswith("."):
                revised = revised + "."
            if len(self._tokenize(revised)) < 6:
                revised = revised + " Provide one clarifying detail."
            edits += 1
        return revised.strip(), edits

    def score_text(self, candidate: Dict[str, Any], *, attempt_edits: bool, max_edits: int,
                   accept_threshold: Optional[float] = None) -> CandidateEvaluation:
        candidate_id = candidate.get("id")
        text = (candidate.get("text") or "").strip()
        original_text = text
        features = {
            "length": self._feature_length(text),
            "sentence_density": self._feature_sentence_density(text),
            "unique_ratio": self._feature_unique_ratio(text),
            "uppercase_ratio": self._feature_uppercase_ratio(text),
            "digit_ratio": self._feature_digit_ratio(text),
            "punctuation_ratio": self._feature_punctuation_ratio(text),
        }
        model_score = self._model_predict(features)
        critique = self._rule_checks(text)
        rule_score = critique.get("rule_score", 0.0)
        combined = 0.65 * model_score + 0.35 * rule_score
        edits = 0
        accepted = combined >= (accept_threshold or self.accept_threshold)
        if attempt_edits and not accepted:
            revised, edits = self._apply_edits(text, critique, max_edits)
            if edits and revised != text:
                text = revised
                features = {
                    "length": self._feature_length(text),
                    "sentence_density": self._feature_sentence_density(text),
                    "unique_ratio": self._feature_unique_ratio(text),
                    "uppercase_ratio": self._feature_uppercase_ratio(text),
                    "digit_ratio": self._feature_digit_ratio(text),
                    "punctuation_ratio": self._feature_punctuation_ratio(text),
                }
                model_score = self._model_predict(features)
                critique = self._rule_checks(text)
                rule_score = critique.get("rule_score", 0.0)
                combined = 0.65 * model_score + 0.35 * rule_score
                accepted = combined >= (accept_threshold or self.accept_threshold)
        rejected = combined < (accept_threshold or self.accept_threshold)
        telemetry = {
            "features": {k: round(v, 4) for k, v in features.items()},
            "edits": edits,
        }
        return CandidateEvaluation(
            candidate_id=candidate_id,
            original_text=original_text,
            text=text,
            score=combined,
            model_score=model_score,
            rule_score=rule_score,
            critique=critique,
            edits=edits,
            accepted=accepted,
            rejected=rejected,
            telemetry=telemetry,
            source={k: candidate.get(k) for k in ("proj", "conf", "meta", "ref_id") if k in candidate},
        )

    def review_text_candidates(
        self,
        candidates: Iterable[Dict[str, Any]],
        *,
        enabled: bool,
        max_edits: int = 1,
        accept_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        candidate_list = list(candidates)
        if not candidate_list:
            return {
                "selected": None,
                "candidates": [],
                "telemetry": {
                    "enabled": enabled,
                    "decision": "empty",
                    "threshold": accept_threshold or self.accept_threshold,
                },
            }
        threshold = accept_threshold or self.accept_threshold
        evaluations: List[CandidateEvaluation] = []
        for entry in candidate_list:
            eval_result = self.score_text(
                entry,
                attempt_edits=enabled and max_edits > 0,
                max_edits=max_edits if enabled else 0,
                accept_threshold=threshold,
            )
            evaluations.append(eval_result)
        if not enabled:
            selected = evaluations[0]
            return {
                "selected": selected.as_dict(),
                "candidates": [e.as_dict() for e in evaluations],
                "telemetry": {
                    "enabled": False,
                    "decision": "bypassed",
                    "threshold": threshold,
                    "avg_score": round(statistics.fmean(e.score for e in evaluations), 4),
                    "edits": 0,
                    "accepted": sum(1 for e in evaluations if e.accepted),
                },
            }
        # Choose best candidate after scoring
        best = max(evaluations, key=lambda e: e.score)
        decision = "accepted" if best.score >= threshold else "escalated"
        telemetry = {
            "enabled": True,
            "decision": decision,
            "threshold": threshold,
            "avg_score": round(statistics.fmean(e.score for e in evaluations), 4),
            "edits": sum(e.edits for e in evaluations),
            "accepted": sum(1 for e in evaluations if e.accepted),
            "rejected": sum(1 for e in evaluations if e.rejected),
        }
        return {
            "selected": best.as_dict(),
            "candidates": [e.as_dict() for e in evaluations],
            "telemetry": telemetry,
        }


__all__ = ["GanSidecar", "CandidateEvaluation"]
