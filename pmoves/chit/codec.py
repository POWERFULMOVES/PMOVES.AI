"""
CHIT Codec Module (Backward Compatibility Wrapper)

This module re-exports functions from pmoves.chit for backward compatibility
with existing code that imports from pmoves.chit.codec.

New code should import directly from pmoves.chit.
"""

from pmoves.chit import (
    # Core CGP types
    CGPPoint,
    CGPPayload,
    CHIT_CGP_VERSION,
    # Encoding/Decoding
    encode_secret_map,
    decode_secret_map,
    # File I/O
    load_cgp,
    save_cgp,
    # Multi-target output
    write_to_tier_envs,
    write_github_secrets,
    write_docker_secrets,
    apply_manifest_v2,
)

__all__ = [
    # Core CGP types
    "CGPPoint",
    "CGPPayload",
    "CHIT_CGP_VERSION",
    # Encoding/Decoding
    "encode_secret_map",
    "decode_secret_map",
    # File I/O
    "load_cgp",
    "save_cgp",
    # Multi-target output
    "write_to_tier_envs",
    "write_github_secrets",
    "write_docker_secrets",
    "apply_manifest_v2",
]
