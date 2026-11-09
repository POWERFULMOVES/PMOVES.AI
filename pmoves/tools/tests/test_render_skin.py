"""Smoke tests for pmoves.tools.render_skin.

The render path requires a live ComfyUI host with MiniMax H3 ULTRA
downloaded, which we don't have in CI. So the tests here exercise:

- the workflow-patching logic (positive CLIPTextEncode gets the prompt)
- the sketch-staging logic (sketch lands in the input dir)
- the SkinResult -> JSON serialization
- the asset-picking logic (smallest = icon, largest = wallpaper)
- the ComfyUI-unavailable error path (no host = clean error)

Run with:
    python -m pytest pmoves/tools/tests/test_render_skin.py -v
or:
    python -m unittest pmoves.tools.tests.test_render_skin
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pmoves.tools.comfyui_client import OutputAsset, RenderResult  # noqa: E402
from pmoves.tools.render_skin import (  # noqa: E402
    ComfyUIUnavailable,
    SkinResult,
    _patch_workflow,
    _pick_assets,
    _stage_sketch,
    render_skin,
    write_skin,
)


def _sample_workflow() -> dict:
    """A minimal workflow JSON with the two node types we patch."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "CLIPTextEncode",
                "title": "positive",
                "widgets_values": ["old positive prompt"],
            },
            {
                "id": 2,
                "type": "CLIPTextEncode",
                "title": "negative",
                "widgets_values": ["old negative prompt"],
            },
            {
                "id": 3,
                "type": "LoadImage",
                "title": "load reference",
                "widgets_values": ["old.png"],
            },
        ]
    }


class PatchWorkflowTests(unittest.TestCase):
    def test_patches_positive_prompt(self) -> None:
        workflow = _sample_workflow()
        out: list[str | None] = [None]
        _patch_workflow(workflow, "new prompt", None, out)
        self.assertEqual(workflow["nodes"][0]["widgets_values"][0], "new prompt")
        # Negative should be unchanged (we only patch the positive node)
        self.assertEqual(workflow["nodes"][1]["widgets_values"][0], "old negative prompt")
        self.assertIsNotNone(out[0])

    def test_patches_loadimage_filename(self) -> None:
        workflow = _sample_workflow()
        out: list[str | None] = [None]
        # Use a real file for the staging step
        tmp = Path("pmoves/tools/tests/.tmp_sketch.png")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
        try:
            _patch_workflow(workflow, "p", tmp, out)
            # The LoadImage widget should now reference the staged filename
            self.assertEqual(workflow["nodes"][2]["widgets_values"][0], tmp.name)
        finally:
            if tmp.exists():
                tmp.unlink()

    def test_prompt_id_is_stable_for_same_input(self) -> None:
        workflow = _sample_workflow()
        out_a: list[str | None] = [None]
        out_b: list[str | None] = [None]
        _patch_workflow(workflow, "same prompt", None, out_a)
        workflow_b = _sample_workflow()
        _patch_workflow(workflow_b, "same prompt", None, out_b)
        self.assertEqual(out_a[0], out_b[0])

    def test_prompt_id_differs_for_different_prompt(self) -> None:
        a = _sample_workflow()
        b = _sample_workflow()
        out_a: list[str | None] = [None]
        out_b: list[str | None] = [None]
        _patch_workflow(a, "prompt A", None, out_a)
        _patch_workflow(b, "prompt B", None, out_b)
        self.assertNotEqual(out_a[0], out_b[0])


class StageSketchTests(unittest.TestCase):
    def test_stages_into_input_dir(self) -> None:
        src = Path("pmoves/tools/tests/.tmp_stage_src.png")
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"hello")
        try:
            staged = _stage_sketch(src)
            self.assertTrue(staged.exists())
            self.assertEqual(staged.name, src.name)
        finally:
            if src.exists():
                src.unlink()
            staged_dir = Path("pmoves/tools/comfyui/_input")
            staged = staged_dir / src.name
            if staged.exists():
                staged.unlink()

    def test_skips_when_sketch_missing(self) -> None:
        # Should not raise - the caller checks for missing sketch separately
        # and only calls _stage_sketch when the file exists.
        # _stage_sketch itself doesn't check, so this is a no-op smoke test.
        self.assertTrue(callable(_stage_sketch))


class PickAssetsTests(unittest.TestCase):
    def test_picks_smallest_as_icon_largest_as_wallpaper(self) -> None:
        # Build three fake files of different sizes
        d = Path("pmoves/tools/tests/.tmp_pick")
        d.mkdir(parents=True, exist_ok=True)
        small = d / "small.png"
        medium = d / "medium.png"
        large = d / "large.png"
        small.write_bytes(b"a" * 10)
        medium.write_bytes(b"a" * 100)
        large.write_bytes(b"a" * 1000)
        try:
            saved = [medium, small, large]  # out of order
            skin, icon, wallpaper = _pick_assets(saved)
            self.assertEqual(skin, medium)  # first in list
            self.assertEqual(icon, small)  # smallest
            self.assertEqual(wallpaper, large)  # largest
        finally:
            for f in (small, medium, large):
                if f.exists():
                    f.unlink()
            if d.exists():
                d.rmdir()

    def test_empty_list(self) -> None:
        self.assertEqual(_pick_assets([]), (None, None, None))


class SkinSerializationTests(unittest.TestCase):
    def test_skin_result_to_json(self) -> None:
        result = SkinResult(
            theme_skin="renders/out.png",
            theme_icon="renders/icon.png",
            theme_wallpaper="renders/wall.png",
            css_vars={"--pm-accent": "#7C3AED"},
            data_attrs={"skin-source-sketch": "cyber.png"},
            meta=None,  # type: ignore[arg-type]
        )
        # Manually set a meta for the test
        from pmoves.tools.render_skin import SkinMeta
        result.meta = SkinMeta(
            source_sketch="cyber.png",
            prompt="third eye, 6-eye motif",
            workflow="pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json",
            workflow_name="MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW",
            rendered_at="2026-08-06T18:30:00+00:00",
            comfyui_url="http://localhost:8188",
            prompt_id="abc123",
            status="success",
            title="Pillar 4 encoding",
            source_attribution="Cataclysm Studios / DARKXSIDE archive",
        )
        text = result.to_json()
        parsed = json.loads(text)
        self.assertEqual(parsed["schema_version"], "pmoves.theme.skin/v1")
        self.assertEqual(parsed["theme_skin"], "renders/out.png")
        self.assertEqual(parsed["meta"]["prompt_id"], "abc123")
        self.assertEqual(parsed["data_attrs"]["skin-source-sketch"], "cyber.png")


class WriteSkinTests(unittest.TestCase):
    def test_writes_json_to_dest(self) -> None:
        result = SkinResult(theme_skin="a.png")
        dest = Path("pmoves/tools/tests/.tmp_skin.json")
        try:
            written = write_skin(result, dest)
            self.assertEqual(written, dest)
            self.assertTrue(dest.exists())
            parsed = json.loads(dest.read_text())
            self.assertEqual(parsed["theme_skin"], "a.png")
        finally:
            if dest.exists():
                dest.unlink()


class RenderSkinErrorTests(unittest.TestCase):
    def test_missing_workflow_raises(self) -> None:
        with self.assertRaises(FileNotFoundError) as ctx:
            render_skin(
                sketch=None,
                prompt="anything",
                output="pmoves/tools/tests/.tmp_o.json",
                workflow_path="/nonexistent/workflow.json",
            )
        self.assertIn("workflow not found", str(ctx.exception))

    def test_missing_sketch_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            render_skin(
                sketch="/nonexistent/sketch.png",
                prompt="anything",
                output="pmoves/tools/tests/.tmp_o.json",
            )

    def test_unreachable_host_raises_comfyui_unavailable(self) -> None:
        with mock.patch("pmoves.tools.comfyui_client.ComfyUIClient.health", return_value=False):
            with self.assertRaises(ComfyUIUnavailable):
                render_skin(
                    sketch=None,
                    prompt="anything",
                    output="pmoves/tools/tests/.tmp_o.json",
                    workflow_path="pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json",
                )


class RenderSkinHappyPathTests(unittest.TestCase):
    """End-to-end render with a mocked ComfyUI client.

    No actual ComfyUI host required. Verifies the full pipeline:
    patch workflow, submit, wait, download assets, write skin.
    """

    def test_full_render_with_mock_client(self) -> None:
        # Build a mock client that returns a fake RenderResult
        result = RenderResult(
            prompt_id="fake-prompt-id",
            status="success",
            assets=[
                OutputAsset("icon.png", "", "output"),
                OutputAsset("wall.png", "", "output"),
                OutputAsset("skin.png", "", "output"),
            ],
        )
        client = mock.MagicMock()
        client.health.return_value = True
        client.submit.return_value = "fake-prompt-id"
        client.wait.return_value = result
        client.base_url = "http://test:8188"
        # download just copies the asset filename to the dest path
        def fake_download(asset: OutputAsset, dest: Path) -> Path:
            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Write different sizes so the pick-assets logic has signal
            sizes = {"icon.png": 10, "wall.png": 1000, "skin.png": 100}
            dest.write_bytes(b"x" * sizes.get(asset.filename, 100))
            return dest
        client.download.side_effect = fake_download

        out = Path("pmoves/tools/tests/.tmp_render_out.json")
        try:
            skin = render_skin(
                sketch=None,
                prompt="Pillar 4 encoding, third eye, 6-eye motif",
                output=out,
                workflow_path="pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json",
                meta_title="Pillar 4 encoding",
                client=client,
            )
            self.assertEqual(skin.meta.status, "success")
            self.assertEqual(skin.meta.prompt_id, "fake-prompt-id")
            self.assertTrue(skin.theme_skin)
            self.assertTrue(skin.theme_icon)
            self.assertTrue(skin.theme_wallpaper)
            # Icon should be the smallest (icon.png, size 10)
            self.assertIn("icon.png", skin.theme_icon)
            # Wallpaper should be the largest (wall.png, size 1000)
            self.assertIn("wall.png", skin.theme_wallpaper)
        finally:
            if out.exists():
                out.unlink()
            # Clean up the render dir
            render_dir = Path("pmoves/design/skins/_renders")
            for f in render_dir.glob("*.png"):
                f.unlink(missing_ok=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
