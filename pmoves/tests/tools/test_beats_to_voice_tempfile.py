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
    """Listen mode never reads the WAV, so it must delete it -- but only ours."""

    def _synthesize_to_temp(self, payload: bytes = b"RIFFfake-wav-bytes"):
        """Produce a synthesis result the way the pipeline actually does."""
        with patch.object(
            beats_to_voice.urllib.request, "urlopen",
            return_value=_FakeResponse(payload),
        ):
            return beats_to_voice.synthesize_prosodic(PROFILE)

    def test_removes_the_synthesized_file(self):
        result = self._synthesize_to_temp()
        path = result["output"]
        self.assertTrue(os.path.exists(path))
        results = {"stages": {"voice": {"synthesis": result}}}
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
        result = self._synthesize_to_temp()
        os.unlink(result["output"])
        results = {"stages": {"voice": {"synthesis": result}}}
        beats_to_voice._discard_synthesized_audio(results)

    def test_refuses_a_path_this_process_did_not_create(self):
        """A non-audio Flute response is echoed verbatim, so `output` is untrusted.

        Without an ownership check, a gateway answering
        ``{"output": "/home/service/data.db"}`` gets that file deleted by the
        listen loop.
        """
        fd, victim = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(victim) and os.unlink(victim))

        results = {"stages": {"voice": {"synthesis": {"output": victim}}}}
        beats_to_voice._discard_synthesized_audio(results)
        self.assertTrue(
            os.path.exists(victim),
            "cleanup deleted a path the process never created",
        )

    def test_non_dict_synthesis_is_a_no_op(self):
        """A JSON body need not even be an object; chained .get() would raise."""
        for synthesis in ([], "error", 7, None):
            results = {"stages": {"voice": {"synthesis": synthesis}}}
            beats_to_voice._discard_synthesized_audio(results)

    def test_second_discard_is_a_no_op(self):
        """Ownership is consumed, so a repeated result cannot delete a reused name."""
        result = self._synthesize_to_temp()
        results = {"stages": {"voice": {"synthesis": result}}}
        beats_to_voice._discard_synthesized_audio(results)
        Path(result["output"]).write_bytes(b"someone else's file now")
        self.addCleanup(
            lambda: os.path.exists(result["output"]) and os.unlink(result["output"])
        )
        beats_to_voice._discard_synthesized_audio(results)
        self.assertTrue(os.path.exists(result["output"]))


class TestWriteFailureCleansUp(unittest.TestCase):
    """mkstemp creates the file before the write; a failed write must not orphan it."""

    def test_failed_write_removes_the_tempfile(self):
        created = []
        real_mkstemp = tempfile.mkstemp

        def _tracking_mkstemp(*args, **kwargs):
            fd, path = real_mkstemp(*args, **kwargs)
            created.append(path)
            return fd, path

        def _boom(*args, **kwargs):
            raise OSError(28, "No space left on device")

        with patch.object(
            beats_to_voice.urllib.request, "urlopen",
            return_value=_FakeResponse(b"RIFFfake"),
        ), patch.object(beats_to_voice.tempfile, "mkstemp", _tracking_mkstemp), \
                patch.object(beats_to_voice.os, "fdopen", _boom):
            result = beats_to_voice.synthesize_prosodic(PROFILE)

        self.assertIsNone(result, "a failed write must not report success")
        self.assertEqual(len(created), 1, "expected exactly one mkstemp call")
        self.assertFalse(
            os.path.exists(created[0]),
            "the partially-written tempfile was left behind",
        )
        self.assertNotIn(created[0], beats_to_voice._OWNED_TEMPFILES)


if __name__ == "__main__":
    unittest.main()
