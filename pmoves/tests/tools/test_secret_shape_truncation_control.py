"""Failing-before control: a truncated provider key on a label with NO manifest rule.

This file imports only symbols that predate pmoves/config/secret_shapes.yaml
(Entry, Target, build_outputs), so it runs unchanged against the old funnel --
and there it fails BEHAVIOURALLY: the truncated value is delivered. Under the
new funnel it is withheld.

The shape is E2B_API_KEY's: delivered missing its leading characters, so it no
longer starts with the vendor prefix, and a presence check passes it. Here it
is HF_TOKEN, which chit_manifest_register.REGISTRY registers with no shape at
all. The value is FABRICATED: 'f_' + FAKE + zeros.
"""

from tools.secrets_sync import Entry, Target, build_outputs

FILE = "env.tier-llm"
WELL_FORMED = "hf_FAKE" + "0" * 30
TRUNCATED = WELL_FORMED[1:]  # leading 'h' lost in delivery


def _entry():
    # No min_length, no prefix: the label carries no manifest rule.
    return Entry(
        id="hf_token",
        label="HF_TOKEN",
        required=False,
        targets=[Target(file=FILE, key="HF_TOKEN")],
    )


def test_positive_control_a_well_formed_value_is_delivered():
    outputs, _ = build_outputs({"HF_TOKEN": WELL_FORMED}, [_entry()], strict=False)
    assert outputs[FILE]["HF_TOKEN"] == WELL_FORMED


def test_a_truncated_key_on_an_unruled_label_is_withheld():
    outputs, _ = build_outputs({"HF_TOKEN": TRUNCATED}, [_entry()], strict=False)
    assert "HF_TOKEN" not in outputs.get(FILE, {}), (
        "truncated HF_TOKEN was DELIVERED -- a presence check passed it"
    )
