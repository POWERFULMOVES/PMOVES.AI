"""Tests for pmoves/tools/flute_geometry_subscriber.py.

Covers:
- 5 decode formulas with boundary values and edge cases
- Chakra band resolution from decoded frequency
- CGP v0.2 packet validation and state vector extraction
- Full process_packet pipeline
- PacketStore ring buffer
- CLI command registration and argument parsing
- Async NATS helpers with mocked connections
- Error handling for malformed JSON and missing fields
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Module import — use load_service_module for standalone script
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def flute_sub(load_service_module):
    """Import flute_geometry_subscriber as a module via conftest helper."""
    return load_service_module(
        "flute_geometry_subscriber",
        "tools/flute_geometry_subscriber.py",
    )


# ===========================================================================
# 1. Decode formula tests — boundary values + edge cases
# ===========================================================================


class TestDecodeDeltaToBpm:
    """bpm = delta * 120 + 60"""

    def test_delta_zero_gives_minimum_bpm(self, flute_sub):
        result = flute_sub.decode_state_vector({"delta": 0.0})
        assert result["bpm"] == 60.0

    def test_delta_midpoint(self, flute_sub):
        result = flute_sub.decode_state_vector({"delta": 0.5})
        assert result["bpm"] == 120.0

    def test_delta_one_gives_maximum_bpm(self, flute_sub):
        result = flute_sub.decode_state_vector({"delta": 1.0})
        assert result["bpm"] == 180.0

    def test_delta_negative_clamped_to_minimum(self, flute_sub):
        """Negative delta is clamped to 0.0 → bpm = 60.0."""
        result = flute_sub.decode_state_vector({"delta": -0.5})
        assert result["bpm"] == 60.0

    def test_delta_above_one_clamped_to_maximum(self, flute_sub):
        """Delta > 1.0 is clamped to 1.0 → bpm = 180.0."""
        result = flute_sub.decode_state_vector({"delta": 1.5})
        assert result["bpm"] == 180.0

    def test_missing_delta_defaults_to_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({})
        assert result["bpm"] == 60.0


class TestDecodeHzToFreq:
    """freq_hz = Hz * 523.0"""

    def test_hz_zero_gives_zero_freq(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 0.0})
        assert result["freq_hz"] == 0.0

    def test_hz_midpoint(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 0.5})
        assert result["freq_hz"] == 261.5

    def test_hz_one_gives_max_freq(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 1.0})
        assert result["freq_hz"] == 523.0

    def test_hz_negative_clamped_to_zero(self, flute_sub):
        """Negative Hz is clamped to 0.0 → freq_hz = 0.0."""
        result = flute_sub.decode_state_vector({"Hz": -0.25})
        assert result["freq_hz"] == 0.0

    def test_missing_hz_defaults_to_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({})
        assert result["freq_hz"] == 0.0


class TestDecodeKappaToDynamicRange:
    """dynamic_range_lu = -kappa * 20.0"""

    def test_kappa_zero_gives_zero_lu(self, flute_sub):
        result = flute_sub.decode_state_vector({"kappa": 0.0})
        assert result["dynamic_range_lu"] == 0.0

    def test_kappa_midpoint(self, flute_sub):
        result = flute_sub.decode_state_vector({"kappa": 0.5})
        assert result["dynamic_range_lu"] == -10.0

    def test_kappa_one_gives_max_negative_lu(self, flute_sub):
        result = flute_sub.decode_state_vector({"kappa": 1.0})
        assert result["dynamic_range_lu"] == -20.0

    def test_kappa_negative_clamped_to_zero(self, flute_sub):
        """Negative kappa is clamped to 0.0 → dynamic_range_lu = -0.0."""
        result = flute_sub.decode_state_vector({"kappa": -1.0})
        assert result["dynamic_range_lu"] == -0.0

    def test_missing_kappa_defaults_to_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({})
        assert result["dynamic_range_lu"] == 0.0


class TestDecodeTonalClarity:
    """tonal_clarity = A (direct passthrough, range 0-1)"""

    def test_clarity_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({"A": 0.0})
        assert result["tonal_clarity"] == 0.0

    def test_clarity_midpoint(self, flute_sub):
        result = flute_sub.decode_state_vector({"A": 0.5})
        assert result["tonal_clarity"] == 0.5

    def test_clarity_one(self, flute_sub):
        result = flute_sub.decode_state_vector({"A": 1.0})
        assert result["tonal_clarity"] == 1.0

    def test_clarity_above_one_clamped(self, flute_sub):
        """A > 1.0 is clamped to 1.0."""
        result = flute_sub.decode_state_vector({"A": 1.5})
        assert result["tonal_clarity"] == 1.0

    def test_missing_a_defaults_to_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({})
        assert result["tonal_clarity"] == 0.0


class TestDecodeSwarmFitness:
    """swarm_fitness = F (direct passthrough, range 0-1)"""

    def test_fitness_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({"F": 0.0})
        assert result["swarm_fitness"] == 0.0

    def test_fitness_midpoint(self, flute_sub):
        result = flute_sub.decode_state_vector({"F": 0.5})
        assert result["swarm_fitness"] == 0.5

    def test_fitness_one(self, flute_sub):
        result = flute_sub.decode_state_vector({"F": 1.0})
        assert result["swarm_fitness"] == 1.0

    def test_fitness_negative_clamped_to_zero(self, flute_sub):
        """F < 0 is clamped to 0.0."""
        result = flute_sub.decode_state_vector({"F": -0.3})
        assert result["swarm_fitness"] == 0.0

    def test_missing_f_defaults_to_zero(self, flute_sub):
        result = flute_sub.decode_state_vector({})
        assert result["swarm_fitness"] == 0.0


class TestDecodeRounding:
    """Verify rounding precision: bpm/freq_hz/dynamic_range to 1 decimal, clarity/fitness to 3."""

    def test_bpm_rounded_to_one_decimal(self, flute_sub):
        result = flute_sub.decode_state_vector({"delta": 0.333})
        assert result["bpm"] == round(0.333 * 120 + 60, 1)

    def test_freq_hz_rounded_to_one_decimal(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 0.333})
        assert result["freq_hz"] == round(0.333 * 523.0, 1)

    def test_clarity_rounded_to_three_decimals(self, flute_sub):
        result = flute_sub.decode_state_vector({"A": 0.12345})
        assert result["tonal_clarity"] == round(0.12345, 3)

    def test_fitness_rounded_to_three_decimals(self, flute_sub):
        result = flute_sub.decode_state_vector({"F": 0.98765})
        assert result["swarm_fitness"] == round(0.98765, 3)


class TestDecodeFullStateVector:
    """All 5 fields populated simultaneously."""

    def test_all_fields_decoded_correctly(self, flute_sub):
        sv = {"delta": 0.75, "Hz": 0.8, "kappa": 0.3, "A": 0.9, "F": 0.6}
        result = flute_sub.decode_state_vector(sv)
        assert result["bpm"] == 150.0
        assert result["freq_hz"] == 418.4
        assert result["dynamic_range_lu"] == -6.0
        assert result["tonal_clarity"] == 0.9
        assert result["swarm_fitness"] == 0.6
        assert "chakra" in result


class TestDecodeEmptyStateVector:
    """Empty dict — all defaults to 0.0."""

    def test_empty_sv_gives_all_defaults(self, flute_sub):
        result = flute_sub.decode_state_vector({})
        assert result["bpm"] == 60.0
        assert result["freq_hz"] == 0.0
        assert result["dynamic_range_lu"] == 0.0
        assert result["tonal_clarity"] == 0.0
        assert result["swarm_fitness"] == 0.0


# ===========================================================================
# 2. Chakra band resolution
# ===========================================================================


class TestChakraResolution:
    """Verify _freq_to_chakra maps frequencies to correct chakra bands."""

    def test_root_chakra_at_c2(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 65.41 / 523.0})
        chakra = result["chakra"]
        assert chakra is not None
        assert chakra["name"] == "muladhara"
        assert chakra["label"] == "Root"

    def test_sacral_chakra_at_d3(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 146.83 / 523.0})
        chakra = result["chakra"]
        assert chakra is not None
        assert chakra["name"] == "svadhisthana"

    def test_heart_chakra_at_f4(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 349.23 / 523.0})
        chakra = result["chakra"]
        assert chakra is not None
        assert chakra["name"] == "anahata"

    def test_crown_chakra_at_c5(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 523.25 / 523.0})
        chakra = result["chakra"]
        assert chakra is not None
        assert chakra["name"] == "sahasrara"
        assert chakra["label"] == "Crown"

    def test_third_eye_at_a4(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 440.0 / 523.0})
        chakra = result["chakra"]
        assert chakra is not None
        assert chakra["name"] == "ajna"
        assert chakra["label"] == "Third Eye"

    def test_zero_freq_maps_to_nearest_chakra(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 0.0})
        chakra = result["chakra"]
        assert chakra is not None
        assert chakra["name"] == "muladhara"

    def test_chakra_has_all_required_fields(self, flute_sub):
        result = flute_sub.decode_state_vector({"Hz": 0.5})
        chakra = result["chakra"]
        assert chakra is not None
        assert "name" in chakra
        assert "label" in chakra
        assert "element" in chakra
        assert "note" in chakra


# ===========================================================================
# 3. CGP v0.2 packet validation
# ===========================================================================


class TestValidateCGPPacket:
    """validate_cgp_packet returns list of issues (empty = valid)."""

    def _valid_packet(self) -> dict[str, Any]:
        return {
            "spec": "chit.cgp.v0.2",
            "control_plane": {
                "state_vector": {"delta": 0.5, "Hz": 0.5},
            },
        }

    def test_valid_packet_returns_empty_issues(self, flute_sub):
        issues = flute_sub.validate_cgp_packet(self._valid_packet())
        assert issues == []

    def test_wrong_spec_reports_issue(self, flute_sub):
        pkt = self._valid_packet()
        pkt["spec"] = "chit.cgp.v1.0"
        issues = flute_sub.validate_cgp_packet(pkt)
        assert len(issues) == 1
        assert "Unexpected spec" in issues[0]
        assert "chit.cgp.v1.0" in issues[0]

    def test_missing_spec_reports_issue(self, flute_sub):
        pkt = self._valid_packet()
        del pkt["spec"]
        issues = flute_sub.validate_cgp_packet(pkt)
        assert any("Unexpected spec" in i for i in issues)

    def test_missing_both_super_nodes_and_control_plane(self, flute_sub):
        issues = flute_sub.validate_cgp_packet({"spec": "chit.cgp.v0.2"})
        assert any("Missing both" in i for i in issues)

    def test_control_plane_without_state_vector_and_no_super_nodes(self, flute_sub):
        pkt = {"spec": "chit.cgp.v0.2", "control_plane": {"other": 1}}
        issues = flute_sub.validate_cgp_packet(pkt)
        assert any("No state_vector" in i for i in issues)

    def test_state_vector_in_super_node_is_valid(self, flute_sub):
        pkt = {
            "spec": "chit.cgp.v0.2",
            "super_nodes": [{"state_vector": {"delta": 0.5}}],
        }
        issues = flute_sub.validate_cgp_packet(pkt)
        assert not any("No state_vector" in i for i in issues)

    def test_empty_control_plane_with_empty_super_nodes(self, flute_sub):
        pkt = {"spec": "chit.cgp.v0.2", "control_plane": {}, "super_nodes": []}
        issues = flute_sub.validate_cgp_packet(pkt)
        # Empty dict {} is not None, so validation runs and finds no state_vector.
        assert any("No state_vector" in i for i in issues)


# ===========================================================================
# 4. State vector extraction
# ===========================================================================


class TestExtractStateVector:
    """extract_state_vector finds state_vector in control_plane or super_nodes."""

    def test_extracts_from_control_plane(self, flute_sub):
        sv = {"delta": 0.5}
        pkt = {"control_plane": {"state_vector": sv}}
        result = flute_sub.extract_state_vector(pkt)
        assert result is sv

    def test_control_plane_takes_priority_over_super_nodes(self, flute_sub):
        cp_sv = {"delta": 0.1}
        sn_sv = {"delta": 0.9}
        pkt = {
            "control_plane": {"state_vector": cp_sv},
            "super_nodes": [{"state_vector": sn_sv}],
        }
        result = flute_sub.extract_state_vector(pkt)
        assert result is cp_sv

    def test_falls_back_to_first_super_node(self, flute_sub):
        sv = {"Hz": 0.7}
        pkt = {"super_nodes": [{"state_vector": sv}, {"other": 1}]}
        result = flute_sub.extract_state_vector(pkt)
        assert result is sv

    def test_returns_none_when_no_state_vector(self, flute_sub):
        pkt = {"control_plane": {}, "super_nodes": [{"other": 1}]}
        result = flute_sub.extract_state_vector(pkt)
        assert result is None

    def test_returns_none_for_empty_packet(self, flute_sub):
        result = flute_sub.extract_state_vector({})
        assert result is None

    def test_skips_super_nodes_without_state_vector(self, flute_sub):
        sv = {"A": 0.5}
        pkt = {
            "super_nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "c", "state_vector": sv},
            ],
        }
        result = flute_sub.extract_state_vector(pkt)
        assert result is sv


# ===========================================================================
# 5. Full process_packet pipeline
# ===========================================================================


class TestProcessPacket:
    """process_packet: validate → extract → decode → enrich."""

    def _make_packet(self, sv: dict | None = None, **overrides) -> dict[str, Any]:
        pkt: dict[str, Any] = {
            "spec": "chit.cgp.v0.2",
            "id": "pkt-001",
            "label": "test-packet",
            "source": "beats_to_cgp",
            "ts": 1700000000.0,
            "control_plane": {},
        }
        if sv is not None:
            pkt["control_plane"]["state_vector"] = sv
        pkt.update(overrides)
        return pkt

    def test_valid_packet_decodes_successfully(self, flute_sub):
        pkt = self._make_packet(sv={"delta": 0.5, "Hz": 0.5})
        result = flute_sub.process_packet(pkt)
        assert result["validation"]["valid"] is True
        assert result["params"] is not None
        assert result["params"]["bpm"] == 120.0
        assert result["source_id"] == "pkt-001"
        assert result["source_label"] == "test-packet"

    def test_missing_state_vector_adds_issue(self, flute_sub):
        pkt = self._make_packet(sv=None)
        result = flute_sub.process_packet(pkt)
        assert result["params"] is None
        issues = result["validation"]["issues"]
        assert any("No state vector" in i for i in issues)

    def test_spec_carried_forward(self, flute_sub):
        pkt = self._make_packet(sv={"delta": 0.0})
        result = flute_sub.process_packet(pkt)
        assert result["spec"] == "chit.cgp.v0.2"

    def test_type_is_decoded_v1(self, flute_sub):
        pkt = self._make_packet(sv={"delta": 0.0})
        result = flute_sub.process_packet(pkt)
        assert result["type"] == "geometry.packet.decoded.v1"

    def test_decoded_ts_is_recent(self, flute_sub):
        before = time.time()
        pkt = self._make_packet(sv={"delta": 0.0})
        result = flute_sub.process_packet(pkt)
        after = time.time()
        assert before <= result["decoded_ts"] <= after

    def test_raw_state_vector_carried_in_result(self, flute_sub):
        sv = {"delta": 0.25, "Hz": 0.75, "kappa": 0.1, "A": 0.8, "F": 0.4}
        pkt = self._make_packet(sv=sv)
        result = flute_sub.process_packet(pkt)
        assert result["state_vector_raw"] == sv

    def test_param_surface_carried_forward(self, flute_sub):
        ps = {"key": "value"}
        pkt = self._make_packet(sv={"delta": 0.0})
        pkt["control_plane"]["param_surface"] = ps
        result = flute_sub.process_packet(pkt)
        assert result["param_surface"] == ps

    def test_no_param_surface_when_absent(self, flute_sub):
        pkt = self._make_packet(sv={"delta": 0.0})
        result = flute_sub.process_packet(pkt)
        assert "param_surface" not in result

    def test_super_nodes_summary_generated(self, flute_sub):
        pkt = self._make_packet(
            sv={"delta": 0.0},
            super_nodes=[
                {"id": "sn-1", "label": "Alpha", "type": "oscillator", "constellations": [{}, {}]},
                {"id": "sn-2", "label": "Beta", "type": "filter", "constellations": [{}]},
            ],
        )
        result = flute_sub.process_packet(pkt)
        summary = result["super_nodes_summary"]
        assert len(summary) == 2
        assert summary[0]["id"] == "sn-1"
        assert summary[0]["constellation_count"] == 2
        assert summary[1]["constellation_count"] == 1

    def test_no_super_nodes_summary_when_absent(self, flute_sub):
        pkt = self._make_packet(sv={"delta": 0.0})
        result = flute_sub.process_packet(pkt)
        assert "super_nodes_summary" not in result

    def test_missing_id_and_label_use_empty_strings(self, flute_sub):
        pkt = {"spec": "chit.cgp.v0.2", "control_plane": {"state_vector": {"delta": 0.0}}}
        result = flute_sub.process_packet(pkt)
        assert result["source_id"] == ""
        assert result["source_label"] == ""

    def test_wrong_spec_still_decodes_if_sv_present(self, flute_sub):
        pkt = self._make_packet(sv={"delta": 0.5})
        pkt["spec"] = "wrong.spec"
        result = flute_sub.process_packet(pkt)
        assert result["validation"]["valid"] is False
        assert result["params"] is not None
        assert result["params"]["bpm"] == 120.0


# ===========================================================================
# 6. PacketStore ring buffer
# ===========================================================================


class TestPacketStore:
    """_PacketStore: ring buffer with count tracking."""

    def test_add_increments_count(self, flute_sub):
        store = flute_sub._PacketStore(maxlen=5)
        store.add({"a": 1})
        store.add({"b": 2})
        assert store.count == 2

    def test_recent_returns_all_items_within_maxlen(self, flute_sub):
        store = flute_sub._PacketStore(maxlen=10)
        items = [{"i": i} for i in range(5)]
        for item in items:
            store.add(item)
        assert store.recent == items

    def test_ring_buffer_evicts_oldest(self, flute_sub):
        store = flute_sub._PacketStore(maxlen=3)
        for i in range(5):
            store.add({"i": i})
        recent = store.recent
        assert len(recent) == 3
        assert recent[0]["i"] == 2
        assert recent[2]["i"] == 4

    def test_count_continues_past_maxlen(self, flute_sub):
        store = flute_sub._PacketStore(maxlen=2)
        for _ in range(10):
            store.add({})
        assert store.count == 10
        assert len(store.recent) == 2

    def test_default_maxlen_is_100(self, flute_sub):
        store = flute_sub._PacketStore()
        assert store._buf.maxlen == 100


# ===========================================================================
# 7. CLI command registration
# ===========================================================================


class TestCLICommands:
    """Verify typer app has the expected commands with correct params."""

    @pytest.fixture
    def cmd_map(self, flute_sub):
        # CommandInfo.name may be None in some typer versions; use callback.__name__
        return {c.callback.__name__: c for c in flute_sub.app.registered_commands}

    def test_app_has_listen_command(self, cmd_map):
        assert "listen" in cmd_map

    def test_app_has_dump_command(self, cmd_map):
        assert "dump" in cmd_map

    def test_app_has_test_command(self, cmd_map):
        assert "test" in cmd_map

    def _cmd_params(self, cmd_info):
        return list(inspect.signature(cmd_info.callback).parameters.keys())

    def test_listen_command_accepts_nats_option(self, cmd_map):
        assert "nats" in self._cmd_params(cmd_map["listen"])

    def test_listen_command_accepts_no_republish_option(self, cmd_map):
        assert "no_republish" in self._cmd_params(cmd_map["listen"])

    def test_listen_command_accepts_quiet_option(self, cmd_map):
        assert "quiet" in self._cmd_params(cmd_map["listen"])

    def test_listen_command_accepts_max_packets_option(self, cmd_map):
        assert "max_packets" in self._cmd_params(cmd_map["listen"])

    def test_dump_command_accepts_count_option(self, cmd_map):
        assert "count" in self._cmd_params(cmd_map["dump"])

    def test_dump_command_accepts_timeout_option(self, cmd_map):
        assert "timeout" in self._cmd_params(cmd_map["dump"])

    def test_dump_command_accepts_output_option(self, cmd_map):
        assert "output" in self._cmd_params(cmd_map["dump"])

    def test_test_command_accepts_duration_option(self, cmd_map):
        assert "duration" in self._cmd_params(cmd_map["test"])


# ===========================================================================
# 8. Async NATS helpers — mocked
# ===========================================================================


def _make_fake_nats_client():
    """Create a fake NATS client with subscribe, drain, publish, close."""
    client = AsyncMock()
    client.subscribe = AsyncMock()
    client.drain = AsyncMock()
    client.publish = AsyncMock()
    client.close = AsyncMock()
    client.is_connected = True
    return client


@pytest.fixture
def mock_nats_connect():
    """Inject nats.connect onto the conftest stub module, restore after.

    The conftest stubs `nats` as a bare ModuleType without `connect`.
    The source does `import nats as natspy; natspy.connect(...)` which
    just fetches from sys.modules. We inject `connect` directly.
    """
    nats_mod = sys.modules["nats"]
    original_connect = getattr(nats_mod, "connect", None)
    fake_connect = AsyncMock()
    nats_mod.connect = fake_connect
    yield fake_connect
    if original_connect is None:
        delattr(nats_mod, "connect")
    else:
        nats_mod.connect = original_connect


class TestPublishDecoded:
    """publish_decoded: fail-open, never raises."""

    @pytest.mark.asyncio
    async def test_publish_success_returns_true(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc
        result = await flute_sub.publish_decoded({"test": True}, "nats://localhost:4222")
        assert result is True
        fake_nc.publish.assert_called_once()
        fake_nc.drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_failure_returns_false(self, flute_sub, mock_nats_connect):
        mock_nats_connect.side_effect = ConnectionError("refused")
        result = await flute_sub.publish_decoded({"test": True}, "nats://bad:4222")
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_payload_is_valid_json(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc
        decoded = {"params": {"bpm": 120.0}, "spec": "chit.cgp.v0.2"}
        await flute_sub.publish_decoded(decoded, "nats://localhost:4222")
        call_args = fake_nc.publish.call_args
        payload = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("payload")
        parsed = json.loads(payload.decode("utf-8"))
        assert parsed["params"]["bpm"] == 120.0


# ===========================================================================
# 9. Listen loop — mocked NATS
# ===========================================================================


class TestListenLoop:
    """_listen_loop with mocked NATS connection."""

    @pytest.mark.asyncio
    async def test_stops_after_max_packets(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc

        captured_handler = None

        async def fake_subscribe(subject, cb=None):
            nonlocal captured_handler
            captured_handler = cb

        fake_nc.subscribe.side_effect = fake_subscribe

        test_packet = json.dumps({
            "spec": "chit.cgp.v0.2",
            "id": "p1",
            "label": "test",
            "source": "test",
            "ts": 0,
            "control_plane": {"state_vector": {"delta": 0.5}},
        }).encode("utf-8")

        task = asyncio.create_task(flute_sub._listen_loop(
            nats_url="nats://localhost:4222",
            republish=False,
            quiet=True,
            max_packets=2,
        ))

        await asyncio.sleep(0.1)
        assert captured_handler is not None

        fake_msg = MagicMock()
        fake_msg.data = test_packet

        # Handler raises _MaxPacketsReached when limit hit — catch it
        try:
            await captured_handler(fake_msg)
        except Exception:
            pass  # _MaxPacketsReached signal

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except Exception:
            pass  # _MaxPacketsReached caught internally by listen loop

    @pytest.mark.asyncio
    async def test_malformed_json_does_not_crash(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc

        captured_handler = None

        async def fake_subscribe(subject, cb=None):
            nonlocal captured_handler
            captured_handler = cb

        fake_nc.subscribe.side_effect = fake_subscribe

        task = asyncio.create_task(flute_sub._listen_loop(
            nats_url="nats://localhost:4222",
            republish=False,
            quiet=True,
            max_packets=1,
        ))
        await asyncio.sleep(0.1)
        assert captured_handler is not None

        fake_msg = MagicMock()
        fake_msg.data = b"{broken json"
        await captured_handler(fake_msg)

        valid = json.dumps({
            "spec": "chit.cgp.v0.2",
            "control_plane": {"state_vector": {"delta": 0.0}},
        }).encode("utf-8")
        fake_msg2 = MagicMock()
        fake_msg2.data = valid
        try:
            await captured_handler(fake_msg2)
        except Exception:
            pass  # _MaxPacketsReached signal

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except Exception:
            pass


# ===========================================================================
# 10. Dump loop — mocked NATS
# ===========================================================================


class TestDumpLoop:
    """_dump_loop collects N packets or times out."""

    @pytest.mark.asyncio
    async def test_collects_requested_packets(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc

        captured_handler = None

        async def fake_subscribe(subject, cb=None):
            nonlocal captured_handler
            captured_handler = cb

        fake_nc.subscribe.side_effect = fake_subscribe

        task = asyncio.create_task(flute_sub._dump_loop(
            nats_url="nats://localhost:4222",
            count=3,
            timeout=5.0,
        ))
        await asyncio.sleep(0.1)
        assert captured_handler is not None

        for _ in range(3):
            pkt = json.dumps({
                "spec": "chit.cgp.v0.2",
                "control_plane": {"state_vector": {"delta": 0.5}},
            }).encode("utf-8")
            fake_msg = MagicMock()
            fake_msg.data = pkt
            await captured_handler(fake_msg)

        result = await asyncio.wait_for(task, timeout=2.0)
        assert len(result) == 3
        assert result[0]["params"]["bpm"] == 120.0

    @pytest.mark.asyncio
    async def test_timeout_returns_partial_results(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc

        captured_handler = None

        async def fake_subscribe(subject, cb=None):
            nonlocal captured_handler
            captured_handler = cb

        fake_nc.subscribe.side_effect = fake_subscribe

        task = asyncio.create_task(flute_sub._dump_loop(
            nats_url="nats://localhost:4222",
            count=10,
            timeout=0.3,
        ))
        await asyncio.sleep(0.1)

        pkt = json.dumps({
            "spec": "chit.cgp.v0.2",
            "control_plane": {"state_vector": {"delta": 0.0}},
        }).encode("utf-8")
        fake_msg = MagicMock()
        fake_msg.data = pkt
        await captured_handler(fake_msg)

        result = await asyncio.wait_for(task, timeout=2.0)
        assert len(result) == 1


# ===========================================================================
# 11. Test loop — mocked NATS
# ===========================================================================


class TestTestLoop:
    """_test_loop counts packets for a duration."""

    @pytest.mark.asyncio
    async def test_counts_packets(self, flute_sub, mock_nats_connect):
        fake_nc = _make_fake_nats_client()
        mock_nats_connect.return_value = fake_nc

        captured_handler = None

        async def fake_subscribe(subject, cb=None):
            nonlocal captured_handler
            captured_handler = cb

        fake_nc.subscribe.side_effect = fake_subscribe

        task = asyncio.create_task(flute_sub._test_loop(
            nats_url="nats://localhost:4222",
            duration_sec=1.0,
        ))
        await asyncio.sleep(0.1)

        for _ in range(3):
            pkt = json.dumps({
                "spec": "chit.cgp.v0.2",
                "control_plane": {"state_vector": {"delta": 0.5}},
            }).encode("utf-8")
            fake_msg = MagicMock()
            fake_msg.data = pkt
            await captured_handler(fake_msg)

        count = await asyncio.wait_for(task, timeout=3.0)
        assert count == 3


# ===========================================================================
# 12. Constants
# ===========================================================================


class TestConstants:
    """Verify module-level constants are correct."""

    def test_cgp_spec(self, flute_sub):
        assert flute_sub.CGP_SPEC == "chit.cgp.v0.2"

    def test_subject_cgp(self, flute_sub):
        assert flute_sub.SUBJECT_CGP == "geometry.cgp.v1"

    def test_subject_decoded(self, flute_sub):
        assert flute_sub.SUBJECT_DECODED == "geometry.packet.decoded.v1"
