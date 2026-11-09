"""Smoke tests for pmoves.tools.comfyui_client.

Mock-based: no actual ComfyUI host required. Run with:

    python -m pytest pmoves/tools/tests/test_comfyui_client.py -v

or:

    python -m unittest pmoves.tools.tests.test_comfyui_client

The tests cover the four public-method surface (health, submit, wait, download)
plus the history-entry parser (which is the place most likely to break when
ComfyUI's output format changes between versions).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

# Make pmoves.tools importable when running from the repo root
_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pmoves.tools.comfyui_client import (  # noqa: E402
    ComfyUIClient,
    ComfyUIError,
    OutputAsset,
    RenderResult,
    _apply_overrides,
)


def _fake_response(body: bytes | dict, status: int = 200) -> mock.MagicMock:
    """Build a context-manager mock that mimics urllib.request.urlopen."""
    payload = json.dumps(body).encode("utf-8") if isinstance(body, dict) else body
    cm = mock.MagicMock()
    cm.__enter__.return_value.read.return_value = payload
    cm.__enter__.return_value.status = status
    return cm


class HealthTests(unittest.TestCase):
    def test_health_ok(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188")
        with mock.patch("urllib.request.urlopen", return_value=_fake_response({"system": {}})):
            self.assertTrue(client.health())

    def test_health_unreachable(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188")
        with mock.patch("urllib.request.urlopen", side_effect=ComfyUIError("connection refused")):
            self.assertFalse(client.health())


class SubmitTests(unittest.TestCase):
    def test_submit_returns_prompt_id(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188")
        with mock.patch(
            "urllib.request.urlopen",
            return_value=_fake_response({"prompt_id": "abc-123"}),
        ):
            prompt_id = client.submit({"nodes": []})
        self.assertEqual(prompt_id, "abc-123")

    def test_submit_missing_prompt_id_raises(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188")
        with mock.patch(
            "urllib.request.urlopen",
            return_value=_fake_response({"error": "bad workflow"}),
        ):
            with self.assertRaises(ComfyUIError) as ctx:
                client.submit({"nodes": []})
        self.assertIn("missing prompt_id", str(ctx.exception))


class WaitTests(unittest.TestCase):
    def test_wait_success(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188", timeout_s=10, poll_s=0.01)
        history_payload = {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "out_00001.png", "subfolder": "", "type": "output"},
                    ]
                }
            },
            "status": {"completed": True, "messages": []},
        }
        # First history() call returns None (rendering), second returns the entry
        responses = [_fake_response({}), _fake_response({prompt_id: history_payload} if False else {"abc-123": history_payload})]
        with mock.patch("urllib.request.urlopen", side_effect=responses):
            result = client.wait("abc-123")
        self.assertIsInstance(result, RenderResult)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.assets), 1)
        self.assertEqual(result.assets[0].filename, "out_00001.png")

    def test_wait_error(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188", timeout_s=10, poll_s=0.01)
        history_payload = {
            "outputs": {},
            "status": {
                "completed": False,
                "errored": True,
                "messages": [["execution_error", {"exception_message": "boom"}]],
            },
        }
        with mock.patch(
            "urllib.request.urlopen",
            return_value=_fake_response({"abc-123": history_payload}),
        ):
            result = client.wait("abc-123")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.assets, [])

    def test_wait_timeout(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188", timeout_s=0.05, poll_s=0.01)
        with mock.patch("urllib.request.urlopen", return_value=_fake_response({})):
            with self.assertRaises(ComfyUIError) as ctx:
                client.wait("abc-123")
        self.assertIn("did not complete", str(ctx.exception))


class DownloadTests(unittest.TestCase):
    def test_download_writes_bytes(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188")
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"hello" * 10
        with mock.patch("urllib.request.urlopen", return_value=_fake_response(png_bytes)):
            dest = Path("pmoves/tools/tests/.tmp_test_download.png")
            try:
                written = client.download(OutputAsset("a.png", "", "output"), dest)
                self.assertEqual(written.read_bytes(), png_bytes)
            finally:
                if dest.exists():
                    dest.unlink()


class BuildResultTests(unittest.TestCase):
    def test_parses_images_gifs_videos_audio(self) -> None:
        client = ComfyUIClient(base_url="http://test:8188")
        entry = {
            "outputs": {
                "10": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]},
                "11": {"gifs": [{"filename": "b.gif", "subfolder": "x", "type": "output"}]},
                "12": {"videos": [{"filename": "c.mp4", "subfolder": "", "type": "output"}]},
                "13": {"audio": [{"filename": "d.wav", "subfolder": "", "type": "output"}]},
            },
            "status": {"completed": True, "messages": []},
        }
        result = client._build_result("xyz", entry)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.assets), 4)
        filenames = sorted(a.filename for a in result.assets)
        self.assertEqual(filenames, ["a.png", "b.gif", "c.mp4", "d.wav"])


class ApplyOverridesTests(unittest.TestCase):
    def test_text_override(self) -> None:
        workflow = {
            "nodes": [
                {"type": "CLIPTextEncode", "title": "positive", "widgets_values": ["old text"]},
            ]
        }
        _apply_overrides(workflow, {"text": "new text"})
        self.assertEqual(workflow["nodes"][0]["widgets_values"][0], "new text")

    def test_image_override(self) -> None:
        workflow = {
            "nodes": [
                {"type": "LoadImage", "title": "load", "widgets_values": ["old.png"]},
            ]
        }
        _apply_overrides(workflow, {"image": "new.png"})
        self.assertEqual(workflow["nodes"][0]["widgets_values"][0], "new.png")


class EnvDefaultsTests(unittest.TestCase):
    def test_env_overrides(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                "PMOVES_COMFYUI_URL": "http://custom:9000",
                "PMOVES_COMFYUI_TIMEOUT_S": "120",
                "PMOVES_COMFYUI_POLL_S": "5",
            },
        ):
            client = ComfyUIClient()
        self.assertEqual(client.base_url, "http://custom:9000")
        self.assertEqual(client.timeout_s, 120)
        self.assertEqual(client.poll_s, 5.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
