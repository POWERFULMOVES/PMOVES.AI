"""Regression test for /transcribe_file filename collision.

Flute-Gateway hardcodes the multipart upload filename as 'audio.wav' (see
pmoves/services/flute-gateway/providers/whisper.py). When the handler chooses
the converted-output path as 'audio.wav' inside the same tmpdir, ffmpeg refuses
to overwrite its input file and exits 2, surfacing as a 500 to every Flute STT
caller.

This test drives /transcribe_file with filename='audio.wav' and verifies the
src and dst paths handed to ffmpeg are distinct.
"""

from __future__ import annotations

import os
import subprocess

from fastapi.testclient import TestClient

import server  # type: ignore[import-not-found]  # conftest puts service dir on sys.path


def _fake_transcribe(provider, audio_path, *, language, model_name, diarize):
    return {
        "text": "hello world",
        "language": language or "en",
        "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "hello world", "speaker": None}
        ],
        "word_segments": None,
        "speakers": {},
        "device": "cpu",
        "model": model_name,
    }


def test_transcribe_file_audio_wav_filename_does_not_collide(monkeypatch):
    """Reproducer for the Flute STT collision.

    When the uploaded filename equals the handler's chosen output filename
    ('audio.wav'), the two paths sit inside the same tmpdir and ffmpeg's -y
    refuses self-overwrite. The handler must keep src != dst.
    """

    captured: dict[str, str] = {}

    def fake_ffmpeg_extract_audio(src: str, dst: str, sample_rate: int = 16000) -> None:
        captured["src"] = src
        captured["dst"] = dst
        if os.path.abspath(src) == os.path.abspath(dst):
            raise subprocess.CalledProcessError(
                returncode=2, cmd=["ffmpeg", "-y", "-i", src, dst]
            )
        with open(dst, "wb") as fh:
            fh.write(b"RIFF\x00\x00\x00\x00WAVEfmt ")

    monkeypatch.setattr(server, "ffmpeg_extract_audio", fake_ffmpeg_extract_audio)
    monkeypatch.setattr(server, "_transcribe_with_provider", _fake_transcribe)

    client = TestClient(server.app)
    resp = client.post(
        "/transcribe_file",
        files={"audio": ("audio.wav", b"\x00\x00\x00\x00", "audio/wav")},
    )

    assert resp.status_code == 200, resp.text
    assert captured, "ffmpeg_extract_audio was never invoked"
    assert captured["src"] != captured["dst"], (
        "src and dst paths must be distinct or ffmpeg refuses self-overwrite "
        "(Flute hardcodes filename='audio.wav' — regression guard)"
    )
