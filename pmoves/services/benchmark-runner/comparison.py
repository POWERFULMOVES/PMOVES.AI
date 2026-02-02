"""Benchmark comparison and regression analysis.

Provides tools to compare benchmark results across runs,
detect performance regressions, and generate reports.
"""

import dataclasses
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RegressionMetric:
    """A detected regression or improvement."""

    metric_name: str  # e.g., "tokens_per_second"
    baseline_value: float
    current_value: float
    percent_change: float
    is_regression: bool  # True if performance degraded
    threshold_exceeded: bool  # True if change exceeds warning threshold


@dataclasses.dataclass
class ComparisonReport:
    """Report comparing two benchmark results."""

    baseline_id: str
    current_id: str
    model_name: str
    timestamp: datetime

    # Performance comparison
    tps_change: Optional[RegressionMetric] = None
    ttft_change: Optional[RegressionMetric] = None
    tpot_change: Optional[RegressionMetric] = None

    # Memory comparison
    vram_change: Optional[RegressionMetric] = None

    # Overall assessment
    has_regression: bool = False
    has_improvement: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "baseline_id": self.baseline_id,
            "current_id": self.current_id,
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "changes": {
                "tokens_per_second": self._metric_to_dict(self.tps_change),
                "time_to_first_token_ms": self._metric_to_dict(self.ttft_change),
                "time_per_output_token_ms": self._metric_to_dict(self.tpot_change),
                "vram_used_mb": self._metric_to_dict(self.vram_change),
            },
            "summary": {
                "has_regression": self.has_regression,
                "has_improvement": self.has_improvement,
            },
        }

    @staticmethod
    def _metric_to_dict(metric: Optional[RegressionMetric]) -> Optional[Dict]:
        if metric is None:
            return None
        return {
            "baseline": metric.baseline_value,
            "current": metric.current_value,
            "percent_change": round(metric.percent_change, 2),
            "is_regression": metric.is_regression,
            "threshold_exceeded": metric.threshold_exceeded,
        }


class BenchmarkComparator:
    """Compare and analyze benchmark results."""

    # Regression thresholds (percent change that triggers warning)
    DEFAULT_THRESHOLDS = {
        "tokens_per_second": -5.0,  # 5% decrease is regression
        "time_to_first_token_ms": 10.0,  # 10% increase is regression
        "time_per_output_token_ms": 10.0,  # 10% increase is regression
        "vram_used_mb": 10.0,  # 10% increase is regression
    }

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        results_dir: str = "/tmp/benchmark-results",
    ):
        """Initialize benchmark comparator.

        Args:
            thresholds: Custom regression thresholds
            results_dir: Directory containing benchmark result files
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.results_dir = Path(results_dir)

    def load_result(self, result_id: str) -> Optional[Dict]:
        """Load a benchmark result from disk.

        Args:
            result_id: Benchmark ID or filename

        Returns:
            Parsed result dict or None
        """
        # Try direct filename first
        result_file = self.results_dir / f"{result_id}.json"
        if not result_file.exists():
            # Try with just the ID prefix
            matching = list(self.results_dir.glob(f"{result_id}*.json"))
            if not matching:
                return None
            result_file = matching[0]

        try:
            return json.loads(result_file.read_text())
        except Exception as e:
            logger.error(f"Failed to load result {result_id}: {e}")
            return None

    def compare(
        self,
        baseline_id: str,
        current_id: str,
    ) -> Optional[ComparisonReport]:
        """Compare two benchmark results.

        Args:
            baseline_id: Baseline benchmark ID
            current_id: Current benchmark ID

        Returns:
            ComparisonReport or None if comparison failed
        """
        baseline = self.load_result(baseline_id)
        current = self.load_result(current_id)

        if not baseline or not current:
            logger.error(f"Could not load results for comparison")
            return None

        # Extract model name
        model_name = current.get("model_name", "unknown")

        report = ComparisonReport(
            baseline_id=baseline_id,
            current_id=current_id,
            model_name=model_name,
            timestamp=datetime.now(),
        )

        # Compare metrics
        baseline_perf = baseline.get("performance", {})
        current_perf = current.get("performance", {})

        # Throughput (higher is better)
        report.tps_change = self._compare_metric(
            "tokens_per_second",
            baseline_perf.get("tokens_per_second", 0),
            current_perf.get("tokens_per_second", 0),
            higher_is_better=True,
        )

        # TTFT (lower is better)
        report.ttft_change = self._compare_metric(
            "time_to_first_token_ms",
            baseline_perf.get("time_to_first_token_ms", 0),
            current_perf.get("time_to_first_token_ms", 0),
            higher_is_better=False,
        )

        # TPOT (lower is better)
        report.tpot_change = self._compare_metric(
            "time_per_output_token_ms",
            baseline_perf.get("time_per_output_token_ms", 0),
            current_perf.get("time_per_output_token_ms", 0),
            higher_is_better=False,
        )

        # VRAM (lower is better)
        baseline_mem = baseline.get("memory", {})
        current_mem = current.get("memory", {})
        report.vram_change = self._compare_metric(
            "vram_used_mb",
            baseline_mem.get("vram_used_mb", 0),
            current_mem.get("vram_used_mb", 0),
            higher_is_better=False,
        )

        # Determine overall regression/improvement
        report.has_regression = any(
            m.is_regression and m.threshold_exceeded
            for m in [report.tps_change, report.ttft_change, report.tpot_change, report.vram_change]
            if m is not None
        )
        report.has_improvement = any(
            not m.is_regression and abs(m.percent_change) > 1.0
            for m in [report.tps_change, report.ttft_change, report.tpot_change, report.vram_change]
            if m is not None
        )

        return report

    def _compare_metric(
        self,
        metric_name: str,
        baseline: float,
        current: float,
        higher_is_better: bool = True,
    ) -> Optional[RegressionMetric]:
        """Compare a single metric between baseline and current.

        Args:
            metric_name: Name of the metric
            baseline: Baseline value
            current: Current value
            higher_is_better: True if higher values are better

        Returns:
            RegressionMetric or None
        """
        if baseline == 0 or current == 0:
            return None

        # Calculate percent change
        percent_change = ((current - baseline) / baseline) * 100

        # Determine if this is a regression
        if higher_is_better:
            is_regression = percent_change < 0
        else:
            is_regression = percent_change > 0

        # Get threshold
        threshold = self.thresholds.get(metric_name, 0)
        threshold_exceeded = (
            (is_regression and percent_change < threshold) or
            (not is_regression and percent_change > abs(threshold))
        )

        return RegressionMetric(
            metric_name=metric_name,
            baseline_value=baseline,
            current_value=current,
            percent_change=percent_change,
            is_regression=is_regression,
            threshold_exceeded=threshold_exceeded,
        )

    def compare_batch(
        self,
        baseline_ids: List[str],
        current_ids: List[str],
    ) -> List[ComparisonReport]:
        """Compare multiple benchmark pairs.

        Args:
            baseline_ids: List of baseline benchmark IDs
            current_ids: List of current benchmark IDs

        Returns:
            List of ComparisonReports
        """
        reports = []

        for baseline_id, current_id in zip(baseline_ids, current_ids):
            report = self.compare(baseline_id, current_id)
            if report:
                reports.append(report)

        return reports

    def find_regressions(
        self,
        baseline_id: str,
        recent_results: int = 10,
    ) -> List[ComparisonReport]:
        """Find regressions compared to baseline.

        Args:
            baseline_id: Baseline benchmark ID
            recent_results: Number of recent results to check

        Returns:
            List of ComparisonReports with regressions
        """
        # Get recent benchmark files
        result_files = sorted(
            self.results_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:recent_results]

        regressions = []

        for result_file in result_files:
            result_id = result_file.stem
            if result_id == baseline_id:
                continue

            report = self.compare(baseline_id, result_id)
            if report and report.has_regression:
                regressions.append(report)

        return regressions

    def generate_trend_report(
        self,
        model_name: str,
        metric: str = "tokens_per_second",
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Generate a trend report for a specific model and metric.

        Args:
            model_name: Model name to filter by
            metric: Metric to track
            max_results: Maximum number of results to include

        Returns:
            Dict with trend data
        """
        # Load all results for the model
        results = []
        for result_file in self.results_dir.glob("*.json"):
            try:
                data = json.loads(result_file.read_text())
                if data.get("model_name") == model_name:
                    results.append(data)
            except Exception:
                continue

        # Sort by timestamp
        results.sort(key=lambda r: r.get("timestamp", ""))

        # Limit results
        results = results[-max_results:]

        # Extract metric values
        metric_path = metric.split(".")
        values = []
        timestamps = []

        for result in results:
            # Navigate nested dict
            value = result
            for key in metric_path:
                value = value.get(key, {})
                if not isinstance(value, dict):
                    break

            if isinstance(value, (int, float)):
                values.append(value)
                timestamps.append(result.get("timestamp"))

        # Calculate trend
        if len(values) < 2:
            return {"error": "Not enough data points"}

        first_value = values[0]
        last_value = values[-1]
        trend_percent = ((last_value - first_value) / first_value) * 100 if first_value else 0

        return {
            "model_name": model_name,
            "metric": metric,
            "data_points": len(values),
            "first_value": first_value,
            "last_value": last_value,
            "trend_percent": round(trend_percent, 2),
            "timestamps": timestamps,
            "values": values,
        }


def calculate_geometric_mean(values: List[float]) -> float:
    """Calculate geometric mean of values.

    Args:
        values: List of positive values

    Returns:
        Geometric mean
    """
    if not values:
        return 0.0

    import math

    product = 1.0
    for v in values:
        if v > 0:
            product *= v
        else:
            return 0.0  # Can't compute with non-positive values

    return product ** (1.0 / len(values))


def calculate_score(
    tps: float,
    ttft: float,
    vram_mb: int,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Calculate composite benchmark score.

    Args:
        tps: Tokens per second
        ttft: Time to first token (ms)
        vram_mb: VRAM usage in MB
        weights: Optional weights for each metric

    Returns:
        Composite score (higher is better)
    """
    default_weights = {
        "tps": 1.0,
        "ttft": 0.3,
        "vram": 0.2,
    }
    weights = {**default_weights, **(weights or {})}

    # Normalize metrics (rough approximations)
    tps_score = tps / 1000.0  # 1000 tps = 1.0
    ttft_score = 100.0 / max(ttft, 1.0)  # Lower is better
    vram_score = 80000.0 / max(vram_mb, 1.0)  # Lower is better

    total_score = (
        weights["tps"] * tps_score +
        weights["ttft"] * ttft_score +
        weights["vram"] * vram_score
    )

    return total_score
