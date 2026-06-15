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


def test_glyph_params_driven_by_real_cymatic_features():
    """Contract: per spec the production call site is
    cymatic_glyph(**glyph_params_from_features(point.meta.cymatic)), where
    point.meta.cymatic == cymatic_features(...) output. So cymatic_features MUST
    emit the keys glyph_params_from_features reads (onset_rate, spectral_centroid
    / named_frequencies). Drive the params off REAL features, not a hand dict."""
    # a clean harmonic tone -> a named-frequency / centroid peak should drive
    # dominant_hz > 0 (currently degrades to 0 because the key is absent).
    feat_tone = cymatic_features(_tone(528.0), SR)
    p_tone = glyph_params_from_features(feat_tone)
    assert p_tone["dominant_hz"] > 0.0, f"dominant_hz stuck at 0: {feat_tone.keys()}"

    # m_radial must respond to onset density rather than being hard-stuck at 1.
    # A percussive/onset-rich signal should yield more radial rings than a single
    # sustained tone (which has ~one onset).
    rng = np.random.default_rng(0)
    t = np.linspace(0, 2.0, int(SR * 2.0), endpoint=False)
    # bursts of noise every 100 ms -> many onsets
    busy = np.zeros_like(t)
    for start in np.arange(0, 2.0, 0.1):
        i = int(start * SR)
        busy[i:i + int(0.02 * SR)] = rng.standard_normal(int(0.02 * SR))
    busy = (busy / (np.max(np.abs(busy)) + 1e-9)).astype("float32")

    # calm: a single short click near the start, otherwise silence -> ~1 onset.
    calm = np.zeros_like(t)
    calm[:int(0.02 * SR)] = rng.standard_normal(int(0.02 * SR))
    calm = (calm / (np.max(np.abs(calm)) + 1e-9)).astype("float32")

    feat_busy = cymatic_features(busy, SR)
    feat_calm = cymatic_features(calm, SR)
    # the contract keys must now be present on real cymatic_features output
    assert "onset_rate" in feat_busy and "spectral_centroid" in feat_busy
    assert feat_busy["onset_rate"] > feat_calm["onset_rate"], (
        f"onset_rate not reflecting density: busy={feat_busy['onset_rate']} "
        f"calm={feat_calm['onset_rate']}")
    m_busy = glyph_params_from_features(feat_busy)["m_radial"]
    m_calm = glyph_params_from_features(feat_calm)["m_radial"]
    assert m_busy > m_calm, f"m_radial not driven by onset density: busy={m_busy} calm={m_calm}"


def test_reproducible_features():
    y = _tone(330.0, harmonics=(1.0, 0.4))
    assert cymatic_features(y, SR) == cymatic_features(y, SR)
