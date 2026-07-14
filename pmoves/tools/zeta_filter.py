"""
Zeta-Inspired Spectral Filter for CGP Spectrum Processing

Python implementation of the TypeScript zeta-filter.ts module.

Uses first N non-trivial Riemann zeta zeros (γ_n ≈ 14.13, 21.02, 25.01, ...)
to create frequency-domain filtering weights for CGP spectrum arrays.

Mathematical basis:
- Each zero γ_n corresponds to a "harmonic" frequency on the critical line Re(s) = 1/2
- Weights derived from 1/log(γ_n) decay patterns, mimicking prime distribution
- Creates scale-invariant filtering across hierarchical data

Usage:
    from pmoves.tools.zeta_filter import ZetaInspiredFilter

    filter = ZetaInspiredFilter(num_zeros=10)
    spectrum = [0.8, 0.6, 0.3, 0.1]
    filtered = filter.filter_spectrum(spectrum)

    # Analyze spectrum
    analysis = filter.analyze_spectrum(spectrum)
    print(f"Dominant index: {analysis['dominant_index']}")
    print(f"Entropy: {analysis['entropy']}")
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# First 20 non-trivial Riemann zeta zeros (imaginary parts only)
# These are the first zeros on the critical line Re(s) = 1/2
# Each γ_n represents ζ(1/2 + iγ_n) = 0
ZETA_ZEROS = [
    14.134725141734693790,  # γ_1
    21.022039638771554993,  # γ_2
    25.010857580145688763,  # γ_3
    30.424876125859513210,  # γ_4
    32.935061587739189691,  # γ_5
    37.586178158825671257,  # γ_6
    40.918719012147495187,  # γ_7
    43.327073280914999519,  # γ_8
    48.005150881167159727,  # γ_9
    49.773832477672302181,  # γ_10
    52.970321477714460644,  # γ_11
    56.446247697063394804,  # γ_12
    59.347044002602353079,  # γ_13
    60.831778524609809844,  # γ_14
    65.112544048081606660,  # γ_15
    67.079810529494173714,  # γ_16
    69.546401711173979252,  # γ_17
    72.067157674481907582,  # γ_18
    75.704690699083933168,  # γ_19
    77.144840068874805373,  # γ_20
]


@dataclass
class ZetaFilterConfig:
    """Configuration options for ZetaInspiredFilter"""
    num_zeros: int = 10
    decay_factor: float = 0.9
    normalize_output: bool = True


@dataclass
class SpectralAnalysis:
    """Result of spectral analysis"""
    filtered: List[float]
    dominant_index: int
    concentration: float
    entropy: float


class ZetaInspiredFilter:
    """
    Zeta-Inspired Spectral Filter

    Applies frequency-domain filtering using Riemann zeta zeros as weights.
    Useful for analyzing CGP spectrum arrays with natural harmonic structure.
    """

    def __init__(
        self,
        num_zeros: int = 10,
        decay_factor: float = 0.9,
        normalize_output: bool = True
    ):
        """
        Create a new ZetaInspiredFilter

        Args:
            num_zeros: Number of zeta zeros to use (1-20, default: 10)
            decay_factor: Exponential decay factor for higher zeros (0-1, default: 0.9)
            normalize_output: Normalize output spectrum to [0,1] (default: true)
        """
        self.config = ZetaFilterConfig(
            num_zeros=max(1, min(num_zeros, 20)),
            decay_factor=max(0.01, min(decay_factor, 1.0)),
            normalize_output=normalize_output
        )

        self.weights = self._compute_weights()
        self.normalized_weights = self._normalize_weights(self.weights)

    def _compute_weights(self) -> List[float]:
        """
        Compute filter weights from zeta zeros

        Weight formula: w_n = decay^n / log(γ_n)
        This creates a decay pattern that emphasizes lower harmonics
        while respecting the logarithmic spacing of zeta zeros.
        """
        zeros = ZETA_ZEROS[:self.config.num_zeros]
        weights = []
        for i, gamma in enumerate(zeros):
            weight = (self.config.decay_factor ** i) / math.log(gamma)
            weights.append(weight)
        return weights

    def _normalize_weights(self, weights: List[float]) -> List[float]:
        """Normalize weights to sum to 1"""
        total = sum(weights)
        if total > 0:
            return [w / total for w in weights]
        return weights

    def get_weights(self) -> List[float]:
        """Get the raw filter weights"""
        return self.weights.copy()

    def get_normalized_weights(self) -> List[float]:
        """Get the normalized filter weights (sum to 1)"""
        return self.normalized_weights.copy()

    def get_zeta_zeros(self) -> List[float]:
        """Get the zeta zeros being used"""
        return ZETA_ZEROS[:self.config.num_zeros]

    def filter_spectrum(self, spectrum: List[float]) -> List[float]:
        """
        Apply zeta-inspired filter to CGP spectrum array

        Uses circular convolution with zeta-weighted kernel.
        Each output value is a weighted sum of neighboring inputs.

        Args:
            spectrum: Input spectrum values (typically [0,1])

        Returns:
            Filtered spectrum with harmonic weighting
        """
        if not spectrum:
            return []
        if len(spectrum) == 1:
            return spectrum.copy()

        filtered = [0.0] * len(spectrum)

        for i in range(len(spectrum)):
            weighted = 0.0
            for k, weight in enumerate(self.normalized_weights):
                if k < len(spectrum):
                    idx = (i + k) % len(spectrum)
                    weighted += spectrum[idx] * weight
            filtered[i] = weighted

        if self.config.normalize_output:
            max_val = max(filtered)
            if max_val > 0:
                filtered = [v / max_val for v in filtered]

        return filtered

    def weighted_average(self, spectrum: List[float]) -> float:
        """
        Apply weighted average filter (non-circular)

        Computes a single weighted average of the entire spectrum,
        useful for dimensionality reduction.

        Args:
            spectrum: Input spectrum values

        Returns:
            Single weighted average value
        """
        if not spectrum:
            return 0.0

        weighted = 0.0
        total_weight = 0.0

        for i, val in enumerate(spectrum):
            weight = self.normalized_weights[i] if i < len(self.normalized_weights) else 0
            weighted += val * weight
            total_weight += weight

        return weighted / total_weight if total_weight > 0 else 0.0

    def spectral_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Compute zeta-weighted similarity between two spectra

        Uses cosine similarity in the zeta-filtered space.
        Values closer to 1 indicate more similar spectra.

        Args:
            a: First spectrum
            b: Second spectrum

        Returns:
            Similarity score in [0,1]
        """
        if not a or not b:
            return 0.0
        if len(a) != len(b):
            return 0.0

        filtered_a = self.filter_spectrum(a)
        filtered_b = self.filter_spectrum(b)

        # Cosine similarity in zeta-weighted space
        dot = sum(fa * fb for fa, fb in zip(filtered_a, filtered_b))
        norm_a = math.sqrt(sum(fa ** 2 for fa in filtered_a))
        norm_b = math.sqrt(sum(fb ** 2 for fb in filtered_b))

        if norm_a <= 0 or norm_b <= 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def spectral_distance(self, a: List[float], b: List[float]) -> float:
        """
        Compute spectral distance (1 - similarity)

        Args:
            a: First spectrum
            b: Second spectrum

        Returns:
            Distance in [0,1]
        """
        return 1.0 - self.spectral_similarity(a, b)

    def analyze_spectrum(self, spectrum: List[float]) -> Dict[str, Any]:
        """
        Perform full spectral analysis on a spectrum

        Returns filtered spectrum plus derived metrics:
        - dominant_index: index of maximum filtered value
        - concentration: Gini-like measure (0 = uniform, 1 = concentrated)
        - entropy: Shannon entropy of filtered distribution

        Args:
            spectrum: Input spectrum

        Returns:
            SpectralAnalysis object as dict
        """
        filtered = self.filter_spectrum(spectrum)

        if not filtered:
            return {
                "filtered": [],
                "dominant_index": -1,
                "concentration": 0.0,
                "entropy": 0.0,
            }

        # Find dominant index
        max_val = filtered[0]
        dominant_index = 0
        for i, val in enumerate(filtered):
            if val > max_val:
                max_val = val
                dominant_index = i

        # Compute concentration (Gini coefficient approximation)
        sorted_filtered = sorted(filtered)
        n = len(sorted_filtered)
        gini_num = 0.0
        total = sum(sorted_filtered)

        if total > 0:
            for i, val in enumerate(sorted_filtered):
                gini_num += (2 * (i + 1) - n - 1) * val
            concentration = max(0.0, min(1.0, gini_num / (n * total)))
        else:
            concentration = 0.0

        # Compute entropy
        entropy = 0.0
        if total > 0:
            for val in filtered:
                p = val / total
                if p > 0:
                    entropy -= p * math.log2(p)

        return {
            "filtered": filtered,
            "dominant_index": dominant_index,
            "concentration": concentration,
            "entropy": entropy,
        }

    def multi_scale_filter(
        self,
        spectrum: List[float],
        scales: List[int] = None
    ) -> Dict[int, List[float]]:
        """
        Apply multi-scale filtering

        Generates filtered spectra at multiple scales (using different
        numbers of zeta zeros) and returns all results.

        Args:
            spectrum: Input spectrum
            scales: Array of numZeros values to use (default: [3, 5, 10])

        Returns:
            Dict mapping scale -> filtered spectrum
        """
        if scales is None:
            scales = [3, 5, 10]

        results = {}
        for scale in scales:
            temp_filter = ZetaInspiredFilter(
                num_zeros=min(scale, 20),
                decay_factor=self.config.decay_factor,
                normalize_output=self.config.normalize_output
            )
            results[scale] = temp_filter.filter_spectrum(spectrum)

        return results

    def compute_resonance(self, spectrum: List[float]) -> float:
        """
        Compute resonance with zeta zeros

        Measures how well the spectrum length aligns with zeta zero spacing.
        Higher values indicate the spectrum has natural harmonic structure.

        Args:
            spectrum: Input spectrum

        Returns:
            Resonance score in [0,1]
        """
        if len(spectrum) < 2:
            return 0.0

        zeros = self.get_zeta_zeros()
        resonance = 0.0

        for gamma in zeros:
            # Check if spectrum length is harmonically related to gamma
            ratio = len(spectrum) / gamma
            nearest_int = round(ratio)
            if nearest_int > 0:
                deviation = abs(ratio - nearest_int) / nearest_int
                resonance += math.exp(-deviation * 10)  # Exponential penalty

        return min(1.0, resonance / len(zeros))


# Convenience functions

def filter_spectrum(
    spectrum: List[float],
    num_zeros: int = 10,
    decay_factor: float = 0.9
) -> List[float]:
    """
    Convenience function to filter a spectrum

    Args:
        spectrum: Input spectrum values
        num_zeros: Number of zeta zeros to use
        decay_factor: Decay factor for higher zeros

    Returns:
        Filtered spectrum
    """
    filter_obj = ZetaInspiredFilter(
        num_zeros=num_zeros,
        decay_factor=decay_factor
    )
    return filter_obj.filter_spectrum(spectrum)


def analyze_spectrum(
    spectrum: List[float],
    num_zeros: int = 10
) -> Dict[str, Any]:
    """
    Convenience function to analyze a spectrum

    Args:
        spectrum: Input spectrum values
        num_zeros: Number of zeta zeros to use

    Returns:
        Spectral analysis dict with filtered, dominant_index, concentration, entropy
    """
    filter_obj = ZetaInspiredFilter(num_zeros=num_zeros)
    return filter_obj.analyze_spectrum(spectrum)


def spectral_similarity(
    a: List[float],
    b: List[float],
    num_zeros: int = 10
) -> float:
    """
    Convenience function to compute spectral similarity

    Args:
        a: First spectrum
        b: Second spectrum
        num_zeros: Number of zeta zeros to use

    Returns:
        Similarity score in [0,1]
    """
    filter_obj = ZetaInspiredFilter(num_zeros=num_zeros)
    return filter_obj.spectral_similarity(a, b)


# Multi-scale analysis for CGP optimization

def optimize_spectrum_scale(
    spectrum: List[float],
    scales: List[int] = [3, 5, 7, 10, 15, 20]
) -> Dict[str, Any]:
    """
    Find the optimal zeta filter scale for a given spectrum

    Evaluates the spectrum at multiple scales and returns metrics
    to help determine the best filtering scale.

    Args:
        spectrum: Input spectrum to optimize
        scales: Scales to evaluate (num_zeros values)

    Returns:
        Dict with scale recommendations and metrics
    """
    results = {}
    filter_base = ZetaInspiredFilter()

    for scale in scales:
        temp_filter = ZetaInspiredFilter(num_zeros=scale)
        analysis = temp_filter.analyze_spectrum(spectrum)
        results[scale] = {
            "entropy": analysis["entropy"],
            "concentration": analysis["concentration"],
            "dominant_index": analysis["dominant_index"],
            "resonance": temp_filter.compute_resonance(spectrum),
        }

    # Find best scale based on combined score
    best_scale = None
    best_score = -1

    for scale, metrics in results.items():
        # Combine metrics (higher entropy + higher resonance = better)
        score = metrics["entropy"] + metrics["resonance"]
        if score > best_score:
            best_score = score
            best_scale = scale

    return {
        "best_scale": best_scale,
        "best_score": best_score,
        "all_scales": results,
    }


__all__ = [
    "ZetaInspiredFilter",
    "ZetaFilterConfig",
    "SpectralAnalysis",
    "ZETA_ZEROS",
    "filter_spectrum",
    "analyze_spectrum",
    "spectral_similarity",
    "optimize_spectrum_scale",
]
