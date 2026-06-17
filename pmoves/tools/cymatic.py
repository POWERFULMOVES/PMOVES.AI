"""Cymatic grounding for WS-A -- deterministic "sound -> geometry".

Cymatics (Chladni figures / sonic geometry) is the artistic statement of the
WS-A thesis: audio frequency content maps to geometric structure. Everything
here is a SIGNAL fact (FFT / librosa), not the health or esoteric claims that
folklore attaches to certain frequencies. We DETECT a 528 Hz peak; we do not
endorse what anyone says it does. Tool can tool; the model can interpret.

Three pieces:
  * harmonicity_symmetry  -- "more harmony = more symmetry" as real metrics
  * named_frequency_tags  -- FFT peak detection near culturally-named frequencies
  * cymatic_glyph         -- spectrum-derived Chladni nodal pattern as SVG
                             (the visual bridge the website renders)
"""
from __future__ import annotations

import math

import numpy as np

# Culturally-named frequencies (Hz). Detection is scientific (FFT peak); the
# names are cultural labels only. A couple are real physics (schumann, gamma);
# the solfeggio/a432 set are cultural -- we tag presence, we make no claims.
NAMED_FREQUENCIES: dict[float, str] = {
    7.83: "schumann",      # Earth-ionosphere cavity resonance (geophysics)
    40.0: "gamma",         # gamma-band (neuroscience)
    136.1: "om",
    174.0: "solfeggio_174",
    285.0: "solfeggio_285",
    396.0: "solfeggio_396",
    417.0: "solfeggio_417",
    432.0: "a432",         # alternative concert pitch
    528.0: "solfeggio_528",
    639.0: "solfeggio_639",
    741.0: "solfeggio_741",
    852.0: "solfeggio_852",
    963.0: "solfeggio_963",
}

# n-fold rotational candidates that evenly divide the 12 pitch classes, with the
# chroma circular-shift that tests that fold's self-similarity.
_FOLD_SHIFT: dict[int, int] = {2: 6, 3: 4, 4: 3, 6: 2, 12: 1}


def harmonicity_symmetry(y: "np.ndarray", sr: int) -> dict:
    """Real metrics behind 'more harmony = more symmetry'.

    - harmonic_ratio: harmonic energy fraction (librosa HPSS)
    - tonality: 1 - spectral flatness (noise -> 0, tonal -> 1)
    - n_fold / rotational_symmetry: dominant rotational self-similarity of the
      12 pitch classes (chord/scale symmetry)
    - symmetry: composite [0, 1]
    """
    import librosa

    y = np.asarray(y, dtype="float32")
    if y.size == 0:
        return {"harmonic_ratio": 0.0, "tonality": 0.0, "n_fold": 1,
                "rotational_symmetry": 0.0, "symmetry": 0.0}

    y_h, y_p = librosa.effects.hpss(y)
    eh = float(np.sum(y_h.astype("float64") ** 2))
    ep = float(np.sum(y_p.astype("float64") ** 2))
    harmonic_ratio = eh / (eh + ep + 1e-12)

    flatness = float(librosa.feature.spectral_flatness(y=y).mean())
    tonality = max(0.0, min(1.0, 1.0 - flatness))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    c = chroma - chroma.mean()
    denom = float(np.dot(c, c)) + 1e-12
    sims = {n: float(np.dot(c, np.roll(c, shift)) / denom)
            for n, shift in _FOLD_SHIFT.items()}
    n_fold = max(sims, key=sims.get)
    rot = max(0.0, sims[n_fold])

    symmetry = (harmonic_ratio + tonality + rot) / 3.0
    return {
        "harmonic_ratio": round(harmonic_ratio, 6),
        "tonality": round(tonality, 6),
        "n_fold": int(n_fold),
        "rotational_symmetry": round(rot, 6),
        "symmetry": round(symmetry, 6),
    }


def named_frequency_tags(y: "np.ndarray", sr: int, tol_cents: float = 60.0,
                         top_k: int = 6, min_magnitude: float = 0.05) -> list[dict]:
    """FFT peak detection near each named frequency. Scientific, no claims."""
    y = np.asarray(y, dtype="float64")
    if y.size < 2:
        return []
    spec = np.abs(np.fft.rfft(y * np.hanning(y.size)))
    freqs = np.fft.rfftfreq(y.size, d=1.0 / sr)
    peak = float(spec.max())
    if peak <= 0:
        return []
    spec = spec / peak
    tags: list[dict] = []
    for f0, name in NAMED_FREQUENCIES.items():
        lo = f0 * 2 ** (-tol_cents / 1200.0)
        hi = f0 * 2 ** (tol_cents / 1200.0)
        band = (freqs >= lo) & (freqs <= hi)
        if not band.any():
            continue
        mag = float(spec[band].max())
        if mag >= min_magnitude:
            pk = float(freqs[band][int(np.argmax(spec[band]))])
            tags.append({"name": name, "target_hz": f0,
                         "peak_hz": round(pk, 3), "magnitude": round(mag, 4)})
    tags.sort(key=lambda t: t["magnitude"], reverse=True)
    return tags[:top_k]


def cymatic_features(y: "np.ndarray", sr: int) -> dict:
    """All cymatic signal features, for fusion into the CGP point meta.

    Includes onset_rate + spectral_centroid so the spec call site
    ``cymatic_glyph(**glyph_params_from_features(point.meta.cymatic))`` reads
    them directly off ``point.meta.cymatic`` (they would otherwise be absent and
    every production glyph would degrade to m_radial=1, dominant_hz=0).
    """
    import librosa

    feat = harmonicity_symmetry(y, sr)
    feat["named_frequencies"] = named_frequency_tags(y, sr)

    ya = np.asarray(y, dtype="float32")
    ya = np.nan_to_num(ya, nan=0.0, posinf=0.0, neginf=0.0)
    if ya.size == 0 or not np.any(ya):
        feat["onset_rate"] = 0.0
        feat["spectral_centroid"] = 0.0
        return feat
    duration = max(ya.size / sr, 1e-6)
    try:
        onsets = librosa.onset.onset_detect(y=ya, sr=sr, units="time")
        feat["onset_rate"] = round(len(onsets) / duration, 6)
    except Exception:
        feat["onset_rate"] = 0.0
    try:
        centroid = float(librosa.feature.spectral_centroid(y=ya, sr=sr).mean())
        feat["spectral_centroid"] = round(float(
            np.nan_to_num(centroid, nan=0.0, posinf=0.0, neginf=0.0)), 4)
    except Exception:
        feat["spectral_centroid"] = 0.0
    return feat


def glyph_params_from_features(feat: dict) -> dict:
    """Map cymatic/librosa features to glyph parameters (deterministic)."""
    n_fold = int(feat.get("n_fold", 3) or 3)
    # radial nodes from onset density (busier -> more rings), clamped 1..8
    onset = float(feat.get("onset_rate", 0.0) or 0.0)
    m_radial = max(1, min(8, 1 + int(round(onset))))
    named = feat.get("named_frequencies") or []
    dominant_hz = float(named[0]["peak_hz"]) if named else float(
        feat.get("spectral_centroid", 0.0) or 0.0)
    return {"n_fold": n_fold, "m_radial": m_radial, "dominant_hz": dominant_hz}


def cymatic_glyph(n_fold: int, m_radial: int, dominant_hz: float = 0.0,
                  size: int = 256) -> dict:
    """Deterministic Chladni-style glyph for a circular membrane mode.

    n_fold nodal diameters (angular nodes) + m_radial nodal circles -- the
    nodal structure of a circular plate mode, the same radial-harmonic look the
    cymatics video shows. Pure geometry, no deps. Returns SVG string + params;
    the website (Z890) renders it (currentColor inherits the theme).
    """
    n = max(1, int(n_fold))
    m = max(1, int(m_radial))
    cx = cy = size / 2.0
    radius = size * 0.46
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'role="img" aria-label="cymatic glyph n={n} m={m}">',
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="none" '
        f'stroke="currentColor" stroke-width="1.5" opacity="0.45"/>',
    ]
    for k in range(1, m + 1):  # nodal circles
        rk = radius * k / (m + 1)
        out.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{rk:.2f}" '
                   f'fill="none" stroke="currentColor" stroke-width="1" opacity="0.7"/>')
    for k in range(n):  # nodal diameters
        ang = math.pi * k / n
        dx = radius * math.cos(ang)
        dy = radius * math.sin(ang)
        out.append(f'<line x1="{cx - dx:.2f}" y1="{cy - dy:.2f}" '
                   f'x2="{cx + dx:.2f}" y2="{cy + dy:.2f}" '
                   f'stroke="currentColor" stroke-width="1" opacity="0.7"/>')
    out.append("</svg>")
    return {"svg": "".join(out), "n_fold": n, "m_radial": m,
            "dominant_hz": round(float(dominant_hz), 3)}
