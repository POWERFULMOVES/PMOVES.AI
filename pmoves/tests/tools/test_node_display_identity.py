"""The operator-facing identity is declared, not derived.

Three spellings exist for this one body: the registry key `claude_b850`
(validated against agent_registry.yaml), the signing card `b850-claude`
(required by cipher as agentId), and the name the operator wants a session to
announce. Deriving the third from either of the others is how the drift started.
"""

from pmoves.tools import node_identity


def test_knuckles_announces_the_operator_facing_name():
    """Production change that would make this fail: rendering the registry key
    (claude_b850) or the signing card (b850-claude) as the announced identity."""
    vocab = node_identity.load_vocabulary()
    node = vocab[node_identity._norm("pmoves-b850")]
    assert node.display_identity.get("claude-code") == "PMOVES-B850-CLAUDE"


def test_display_identity_does_not_disturb_the_validated_registry_key():
    """Control: the registry key must still be claude_b850, or node_identity's
    validation against agent_registry.yaml breaks."""
    vocab = node_identity.load_vocabulary()
    node = vocab[node_identity._norm("pmoves-b850")]
    assert node.default_identity.get("claude-code") == "claude_b850"


def test_a_node_without_a_display_identity_is_not_an_error():
    """Most nodes declare none; absence must be empty, not a crash."""
    vocab = node_identity.load_vocabulary()
    node = vocab[node_identity._norm("spark")]
    assert node.display_identity == {}
