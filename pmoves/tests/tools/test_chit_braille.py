"""Tests for pmoves.tools.chit_braille — the CHIT/CGP braille motif renderer.

Braille cells are one byte each (U+2800 + byte), which is what makes them the
terminal-native illustration layer for CHIT provenance: the digest IS the
picture. These tests pin the contracts the fleet depends on: lossless byte
mapping, deterministic motifs (same identity = same motif on every node),
context-motif stability for PMOVES-ORCH banners, and content-sensitive CGP
strips (a changed packet changes the picture).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "chit_braille", Path(__file__).resolve().parents[2] / "tools" / "chit_braille.py"
)
chit_braille = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(chit_braille)


def test_from_bytes_is_lossless_one_cell_per_byte():
    data = bytes([0, 1, 0x28, 0xFF])
    cells = chit_braille.from_bytes(data)
    assert len(cells) == 4
    assert [ord(c) - chit_braille.BRAILLE_BASE for c in cells] == [0, 1, 0x28, 0xFF]


def test_from_bytes_covers_full_byte_range():
    cells = chit_braille.from_bytes(bytes(range(256)))
    assert len(cells) == 256
    assert ord(min(cells)) == chit_braille.BRAILLE_BASE
    assert ord(max(cells)) == chit_braille.BRAILLE_MAX


def test_agent_motif_is_deterministic_per_identity():
    a1 = chit_braille.agent_motif("spark-crush")
    a2 = chit_braille.agent_motif("spark-crush")
    assert a1 == a2
    other = chit_braille.agent_motif("crush")
    assert a1 != other


def test_agent_motif_shapes_and_never_blank():
    motif = chit_braille.agent_motif("spark-crush", rows=2, cols=4)
    lines = motif.split("\n")
    assert len(lines) == 2
    assert all(len(line) == 4 for line in lines)
    # every cell carries at least the forced minimum dot pattern (no blanks)
    assert all(ord(c) > chit_braille.BRAILLE_BASE for line in lines for c in line)


def test_orch_motif_stable_for_same_context_differs_across():
    assert chit_braille.orch_motif("cipher fleet restore") == chit_braille.orch_motif(
        "cipher fleet restore"
    )
    assert chit_braille.orch_motif("cipher fleet restore") != chit_braille.orch_motif(
        "room: fordham community"
    )


def test_cgp_strip_is_content_sensitive(tmp_path):
    packet_a = tmp_path / "a.cgp.json"
    packet_b = tmp_path / "b.cgp.json"
    packet_a.write_text(json.dumps({"points": [1, 2, 3]}), encoding="utf-8")
    packet_b.write_text(json.dumps({"points": [1, 2, 4]}), encoding="utf-8")
    strip_a = chit_braille.cgp_strip(packet_a)
    strip_b = chit_braille.cgp_strip(packet_b)
    assert len(strip_a) == len(strip_b) == 16
    assert strip_a != strip_b


def test_cli_renders_agent_card():
    from unittest import mock

    argv = ["agent", "spark-crush"]
    with mock.patch.object(chit_braille.sys, "argv", ["chit_braille", *argv]):
        rc = chit_braille.main(argv)
    assert rc == 0


def test_cli_context_without_dimensions_uses_defaults():
    rc = chit_braille.main(["context", "room: fordham community"])
    assert rc == 0
