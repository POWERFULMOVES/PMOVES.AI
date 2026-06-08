import numpy as np

from pmoves.tools.cymatic import (
    cymatic_features,
    cymatic_glyph,
    glyph_params_from_features,
    harmonicity_symmetry,
    named_frequency_tags,
)

SR = 22050


def _tone(freq, seconds=1.0, sr=SR, harmonics=(1.0,)):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = np.zeros_like(t)
    for i, amp in enumerate(harmonics, start=1):
        y += amp * np.sin(2 * np.pi * freq * i * t)
    return (y / np.max(np.abs(y))).astype("float32")


def test_harmonicity_symmetry_range_and_keys():
    feat = harmonicity_symmetry(_tone(220.0, harmonics=(1.0, 0.5, 0.25)), SR)
    for k in ("harmonic_ratio", "tonality", "n_fold", "rotational_symmetry", "symmetry"):
        assert k in feat
    assert 0.0 <= feat["symmetry"] <= 1.0
    assert 0.0 <= feat["harmonic_ratio"] <= 1.0
    assert feat["n_fold"] in (2, 3, 4, 6, 12)


def test_harmonic_tone_more_harmonic_than_noise():
    harmonic = harmonicity_symmetry(_tone(220.0, harmonics=(1.0, 0.5, 0.25)), SR)
    rng = np.random.default_rng(0)
    noise = harmonicity_symmetry(rng.standard_normal(SR).astype("float32"), SR)
    # a tonal harmonic stack should read as more tonal than white noise
    assert harmonic["tonality"] > noise["tonality"]


def test_harmonicity_symmetry_empty_safe():
    feat = harmonicity_symmetry(np.zeros(0, dtype="float32"), SR)
    assert feat["symmetry"] == 0.0 and feat["n_fold"] == 1


def test_named_frequency_detects_528():
    tags = named_frequency_tags(_tone(528.0), SR)
    names = {t["name"] for t in tags}
    assert "solfeggio_528" in names
    top = next(t for t in tags if t["name"] == "solfeggio_528")
    assert abs(top["peak_hz"] - 528.0) < 5.0
    assert 0.0 < top["magnitude"] <= 1.0


def test_named_frequency_silence_empty():
    assert named_frequency_tags(np.zeros(SR, dtype="float32"), SR) == []
    assert named_frequency_tags(np.zeros(1, dtype="float32"), SR) == []


def test_cymatic_features_shape():
    feat = cymatic_features(_tone(432.0), SR)
    assert "symmetry" in feat and "named_frequencies" in feat
    assert isinstance(feat["named_frequencies"], list)
    assert any(t["name"] == "a432" for t in feat["named_frequencies"])


def test_cymatic_glyph_structure_and_determinism():
    g1 = cymatic_glyph(n_fold=5, m_radial=3, dominant_hz=528.0)
    g2 = cymatic_glyph(n_fold=5, m_radial=3, dominant_hz=528.0)
    assert g1 == g2  # deterministic
    assert g1["svg"].startswith("<svg") and g1["svg"].rstrip().endswith("</svg>")
    assert g1["svg"].count("<line") == 5          # n_fold nodal diameters
    assert g1["svg"].count("<circle") == 1 + 3    # bounding + m_radial nodal circles
    assert g1["n_fold"] == 5 and g1["m_radial"] == 3


def test_cymatic_glyph_clamps_degenerate():
    g = cymatic_glyph(n_fold=0, m_radial=0)
    assert g["n_fold"] == 1 and g["m_radial"] == 1
    assert g["svg"].count("<line") == 1


def test_glyph_params_from_features():
    feat = {"n_fold": 4, "onset_rate": 2.6, "named_frequencies": [{"peak_hz": 528.0}]}
    p = glyph_params_from_features(feat)
    assert p["n_fold"] == 4
    assert 1 <= p["m_radial"] <= 8
    assert p["dominant_hz"] == 528.0


def test_reproducible_features():
    y = _tone(330.0, harmonics=(1.0, 0.4))
    assert cymatic_features(y, SR) == cymatic_features(y, SR)
