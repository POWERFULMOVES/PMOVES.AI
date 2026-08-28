import os
import pytest

pytestmark = pytest.mark.requires_ui

RUN = os.getenv("CREATOR_UI_TEST") == "1"


@pytest.mark.skipif(not RUN, reason="set CREATOR_UI_TEST=1 on the 4090 with ComfyUI up")
def test_live_run_produces_artifact_and_harvests_api_prompt():
    """Acceptance: a live operator run on the 4090 returns status=ok, a real
    artifact path, and a NON-null api_prompt (the harvested POST /prompt graph).
    Driven by the comfy-operate-image skill via chrome-devtools MCP."""
    from operator_helpers import assemble_result  # noqa: F401  (the agent calls this)
    pytest.skip("manual: run via the comfy-operate-image skill, assert result.api_prompt is not None")


@pytest.mark.skipif(not RUN, reason="set CREATOR_UI_TEST=1")
def test_harvested_api_prompt_replays_headless():
    """Acceptance: POSTing the harvested api_prompt back to /prompt yields an
    equivalent artifact (proves the byproduct is a real headless recipe)."""
    pytest.skip("manual: POST harvested api_prompt to /prompt; assert an image returns")
