import json
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
# Exposed knobs the work-order knobs{} may carry for this workflow.
WORKORDER_KNOBS = {"prompt", "seed", "input_image"}


def test_every_exposed_knob_has_a_teaching_sentence():
    glossary = json.loads((SKILL / "knobs.json").read_text(encoding="utf-8"))["exposed_knobs"]
    for knob in WORKORDER_KNOBS:
        assert knob in glossary, f"knob {knob!r} has no teaching sentence"
        assert glossary[knob].strip(), f"knob {knob!r} has an empty sentence"


def test_skill_has_frontmatter_name():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "name: comfy-operate-image" in text
