"""Regression tests for beats_to_voice synthesized-audio handling.

Covers two defects surfaced by the #2511 review:

* the output path was the hard-coded POSIX literal
  ``/tmp/beats_to_voice_{int(time.time())}.wav`` -- absent on native Windows,
  collision-prone at one-second resolution, and symlink-predictable;
* listen mode published the CGP packet and never consumed the WAV, so every
  trigger left another file behind.
"""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pmoves.tools.beats_to_voice as beats_to_voice


class _FakeResponse:
    """Minimal stand-in for the urlopen context manager."""

    def __init__(self, payload: bytes):
        self.headers = {
            "content-type": "audio/wav",
            "X-Prosodic-BPM": "120",
            "X-Prosodic-Chunks": "1",
        }
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


PROFILE = {"text": "hello", "chunks": [{"text": "hello"}]}


class TestSynthesizedAudioPath(unittest.TestCase):
    """The WAV must land in a real, unique, platform-native temp file."""

    def _synthesize(self, payload: bytes = b"RIFFfake-wav-bytes"):
        with patch.object(
            beats_to_voice.urllib.request, "urlopen",
            return_value=_FakeResponse(payload),
        ):
            return beats_to_voice.synthesize_prosodic(PROFILE)

    def test_writes_the_audio_to_a_real_file(self):
        result = self._synthesize()
        self.assertIsNotNone(result)
        out = Path(result["output"])
        self.addCleanup(lambda: out.exists() and out.unlink())
        self.assertTrue(out.is_file())
        self.assertEqual(out.read_bytes(), b"RIFFfake-wav-bytes")
        self.assertEqual(result["size_bytes"], len(b"RIFFfake-wav-bytes"))

    def test_path_is_not_a_hard_coded_posix_tmp(self):
        """Must sit under the platform temp dir, so it works on Windows too."""
        result = self._synthesize()
        out = Path(result["output"])
        self.addCleanup(lambda: out.exists() and out.unlink())
        self.assertEqual(
            os.path.normcase(str(out.parent)),
            os.path.normcase(tempfile.gettempdir()),
        )

    def test_honours_the_configured_temp_dir(self):
        """tempfile respects TMPDIR/TEMP; a hard-coded literal would not."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(tempfile, "tempdir", tmpdir):
                result = self._synthesize()
            out = Path(result["output"])
            self.assertEqual(
                os.path.normcase(str(out.parent)), os.path.normcase(tmpdir)
            )

    def test_concurrent_calls_do_not_collide(self):
        """Two calls in the same second must not return the same path."""
        first = self._synthesize(b"first")
        second = self._synthesize(b"second")
        p1, p2 = Path(first["output"]), Path(second["output"])
        self.addCleanup(lambda: p1.exists() and p1.unlink())
        self.addCleanup(lambda: p2.exists() and p2.unlink())
        self.assertNotEqual(p1, p2)
        self.assertEqual(p1.read_bytes(), b"first")
        self.assertEqual(p2.read_bytes(), b"second")

    def test_module_has_no_hard_coded_tmp_literal(self):
        source = io.open(beats_to_voice.__file__, encoding="utf-8").read()
        self.assertNotIn('"/tmp/', source)
        self.assertNotIn("'/tmp/", source)


class TestDiscardSynthesizedAudio(unittest.TestCase):
    """Listen mode never reads the WAV, so it must delete it."""

    def test_removes_the_synthesized_file(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        results = {"stages": {"voice": {"synthesis": {"output": path}}}}
        beats_to_voice._discard_synthesized_audio(results)
        self.assertFalse(os.path.exists(path))

    def test_no_synthesis_stage_is_a_no_op(self):
        for results in (
            {},
            {"stages": {}},
            {"stages": {"voice": {}}},
            {"stages": {"voice": {"status": "flute_offline"}}},
        ):
            beats_to_voice._discard_synthesized_audio(results)

    def test_already_removed_file_does_not_raise(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        os.unlink(path)
        results = {"stages": {"voice": {"synthesis": {"output": path}}}}
        beats_to_voice._discard_synthesized_audio(results)


if __name__ == "__main__":
    unittest.main()
