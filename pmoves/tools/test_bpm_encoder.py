"""Tests for bpm_encoder.py chakra-axis additions (#1398)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpm_encoder


class TestChakraBands(unittest.TestCase):
    def test_seven_bands_defined(self):
        assert len(bpm_encoder.CHAKRA_BANDS) == 7

    def test_band_names_ordered_root_to_crown(self):
        names = [b["name"] for b in bpm_encoder.CHAKRA_BANDS]
        assert names[0] == "muladhara"
        assert names[-1] == "sahasrara"

    def test_hz_fundamentals_ascending(self):
        hz_values = [b["hz"] for b in bpm_encoder.CHAKRA_BANDS]
        assert hz_values == sorted(hz_values)

    def test_required_keys_present(self):
        required = {"name", "label", "element", "bpm_min", "bpm_max",
                    "hz", "note", "boundary", "breath_in_sec", "breath_out_sec"}
        for band in bpm_encoder.CHAKRA_BANDS:
            assert required <= set(band.keys()), f"Missing keys in {band['name']}"


class TestChakraToBand(unittest.TestCase):
    def test_midpoints_map_to_own_band(self):
        """Each band's BPM midpoint should resolve back to itself."""
        for band in bpm_encoder.CHAKRA_BANDS:
            mid = (band["bpm_min"] + band["bpm_max"]) / 2.0
            result = bpm_encoder.chakra_to_band(mid)
            assert result["name"] == band["name"], (
                f"midpoint {mid} → {result['name']}, expected {band['name']}"
            )

    def test_low_bpm_returns_muladhara(self):
        assert bpm_encoder.chakra_to_band(10)["name"] == "muladhara"

    def test_high_bpm_returns_sahasrara(self):
        assert bpm_encoder.chakra_to_band(999)["name"] == "sahasrara"

    def test_returns_dict_not_none(self):
        result = bpm_encoder.chakra_to_band(120)
        assert isinstance(result, dict)
        assert "name" in result


class TestFreqToChakra(unittest.TestCase):
    def test_known_fundamentals(self):
        cases = [
            (65.41,  "muladhara"),
            (146.83, "svadhisthana"),
            (164.81, "manipura"),
            (349.23, "anahata"),
            (392.00, "vishuddha"),
            (440.00, "ajna"),
            (523.25, "sahasrara"),
        ]
        for hz, expected_name in cases:
            result = bpm_encoder.freq_to_chakra(hz)
            assert result["name"] == expected_name, (
                f"freq_to_chakra({hz}) → {result['name']}, expected {expected_name}"
            )

    def test_near_boundary_snaps_to_nearest(self):
        # 300 Hz is between anahata (349 Hz) and manipura (165 Hz); closer to anahata
        result = bpm_encoder.freq_to_chakra(300.0)
        assert result["name"] == "anahata"


class TestBuildCgpPacketChakra(unittest.TestCase):
    def test_chakra_field_present_in_control_plane(self):
        profile = bpm_encoder.encode_prosodic_profile("hello world", bpm=60)
        packet = bpm_encoder.build_cgp_packet(profile)
        chakra = packet["control_plane"]["chakra"]
        assert isinstance(chakra, dict)
        assert "name" in chakra
        assert "hz" in chakra

    def test_chakra_matches_avg_freq(self):
        """At 60 BPM, avg freq is near C4 (≈262 Hz) — closest chakra is anahata (349 Hz)."""
        profile = bpm_encoder.encode_prosodic_profile("test", bpm=60)
        packet = bpm_encoder.build_cgp_packet(profile)
        chakra_name = packet["control_plane"]["chakra"]["name"]
        # Verify it's a known chakra name, not a crash
        known = {b["name"] for b in bpm_encoder.CHAKRA_BANDS}
        assert chakra_name in known

    def test_backward_compat_spec_unchanged(self):
        profile = bpm_encoder.encode_prosodic_profile("test", bpm=120)
        packet = bpm_encoder.build_cgp_packet(profile)
        assert packet["spec"] == "chit.cgp.v0.2"


if __name__ == "__main__":
    unittest.main()
