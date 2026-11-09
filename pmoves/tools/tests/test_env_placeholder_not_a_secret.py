"""A commented-out value in an env file must never be funneled as a credential.

env.shared.example shipped lines of the shape

    PMOVES_BRIDGE_TOKEN=   # REQUIRED - generate: openssl rand -hex 32

and ``chit_encode_secrets.load_env_file`` returned that 80-character comment as
the secret's value. Because it is non-empty, ``secrets_sync._first_usable``
accepted it, ``build_outputs`` emitted a public template string into
env.tier-worker, and the required-secret check reported the funnel as
successful -- so the bridge running with no real credential was undetectable.

Three REQUIRED keys had this shape and are not minted by brand_defaults:
PMOVES_BRIDGE_TOKEN, PMOVES_BRIDGE_API_KEY, GATE_API_KEY.
"""
from pathlib import Path

from pmoves.tools.chit_encode_secrets import load_env_file

REPO = Path(__file__).resolve().parents[3]
SHARED_EXAMPLE = REPO / "pmoves" / "env.shared.example"

# The exact line shape that shipped, kept verbatim so this test still fails if
# the loader regresses even after the template is cleaned up.
_PLACEHOLDER_LINE = (
    "PMOVES_BRIDGE_TOKEN=   # REQUIRED - generate: openssl rand -hex 32 "
    "(mirror of X-PMOVES-Bridge-Token)"
)


def test_comment_only_value_is_not_a_secret(tmp_path: Path) -> None:
    env = tmp_path / "env.shared"
    env.write_text(_PLACEHOLDER_LINE + "\nREAL_KEY=abc123\n", encoding="utf-8")

    loaded = load_env_file(env)

    # The key is still present -- it IS declared in the file -- but carries no value.
    assert "PMOVES_BRIDGE_TOKEN" in loaded
    assert loaded["PMOVES_BRIDGE_TOKEN"] == ""
    # And therefore reads as absent to every downstream `if value.strip()` check,
    # which is what makes the required-secret check able to say NO.
    assert not loaded["PMOVES_BRIDGE_TOKEN"].strip()
    assert loaded["REAL_KEY"] == "abc123"


def test_a_real_value_with_a_trailing_hash_is_left_intact() -> None:
    """Only the unambiguous case is stripped.

    A secret may legitimately contain '#'. Guessing where the value ends would
    corrupt it, so `KEY=real  # note` is deliberately preserved as-is; the
    template is the layer responsible for not emitting that shape.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        env = Path(d) / "env"
        env.write_text("A=s3cr3t#withhash\nB=value  # note\n", encoding="utf-8")
        loaded = load_env_file(env)
    assert loaded["A"] == "s3cr3t#withhash"
    assert loaded["B"] == "value  # note"


def test_shipped_template_declares_no_comment_only_values() -> None:
    """The template must not reintroduce the shape at the source."""
    offenders = []
    for lineno, raw in enumerate(
        SHARED_EXAMPLE.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if value.strip().startswith("#"):
            offenders.append(f"{SHARED_EXAMPLE.name}:{lineno} {key}")
    assert offenders == [], (
        "env file keys whose entire value is a trailing comment -- move the "
        "comment to its own line above the key: " + "; ".join(offenders)
    )
