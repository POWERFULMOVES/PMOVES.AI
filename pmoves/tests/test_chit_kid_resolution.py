"""Signing-key resolution by `kid` — pmoves/tools/chit_security.py.

WHY THIS FILE EXISTS
--------------------
`sign_cgp()` stamped a `kid` into every signature; `verify_cgp()` never read
it.  The field was write-only, so every verifier resolved one key and a
signature naming a per-agent key was still checked against the deployment key.
Per-agent identity was therefore unreachable and every CHIT signature
authenticated the deployment rather than the agent.

POSITIVE-CONTROL DESIGN — read before editing
---------------------------------------------
The tests in `TestKidBehaviour` deliberately import ONLY `sign_cgp` and
`verify_cgp`, both of which exist in the pre-fix module, and use the string
literal "chit-signing-v01" rather than the new `DEFAULT_KID` constant.  That is
not stylistic: it means this class can be *collected and executed* against the
pre-fix file, so its failures are real behavioural evidence rather than
"the symbol does not exist yet".

`TestKidResolutionAPI` covers the new surface and is skipped when that surface
is absent.  Skips in the control run are NOT evidence; only `TestKidBehaviour`
failures are.
"""
from __future__ import annotations

import copy
import json

import pytest

from pmoves.tools.chit_security import sign_cgp, verify_cgp

try:  # new surface — absent pre-fix, so guarded to keep the control runnable
    from pmoves.tools.chit_security import (  # noqa: F401
        DEFAULT_KID,
        KidResolutionError,
        SignatureStatus,
        VerifyResult,
        resolve_signing_key,
        verify_cgp_detailed,
    )

    _KID_API = True
except ImportError:  # pragma: no cover — only taken by the pre-fix control run
    _KID_API = False

_needs_api = pytest.mark.skipif(
    not _KID_API,
    reason="kid-resolution API not present (pre-fix control run; not evidence)",
)

# Test-only key material.  Never a live key; nothing here is ever printed.
DEPLOY_KEY = "deployment-key-for-tests-only"
AGENT_KEY = "agent-b850-key-for-tests-only"
OTHER_AGENT_KEY = "agent-4090-key-for-tests-only"

LEGACY_KID = "chit-signing-v01"
AGENT_KID = "agent-b850-claude"
AGENT_KID_ENV = "CHIT_SIGNING_KEY__AGENT_B850_CLAUDE"
OTHER_KID = "agent-4090-claude"
OTHER_KID_ENV = "CHIT_SIGNING_KEY__AGENT_4090_CLAUDE"

# The real shape emitted by `make -C pmoves sign-trail`, taken from a committed
# artifact (pmoves/docs/logs/graphiti_signed_latest.json) with the HMAC removed.
TRAIL_PAYLOAD = {
    "agent_id": "b850-claude",
    "display_name": "B850 Claude",
    "glyph": "⌬",
    "color": "#DC2626",
    "accent": "#F87171",
    "voice": "analytical",
    "phase": "Phase R: ACK — review-thread adjudication",
    "timestamp": "2026-09-05T18:45:41.409408+00:00",
    "resonance": ["rocm-dual-gpu", "data-tier", "dynamic-model-plane"],
    "summary": "ACK B850-CLAUDE. Signing-key resolution by kid.",
    "signing_card_id": "00000000-0000-4000-8000-000000000036",
}


@pytest.fixture(autouse=True)
def _clean_chit_env(monkeypatch):
    """Strip every ambient CHIT_* var.

    The host running these tests may well have a real `CHIT_SIGNING_KEY`
    exported.  Without this the suite would silently test the operator's
    configuration instead of the code, and could pass for the wrong reason.
    """
    import os

    for name in [n for n in os.environ if n.startswith("CHIT_")]:
        monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture
def trail():
    return copy.deepcopy(TRAIL_PAYLOAD)


class TestKidBehaviour:
    """Executable against the pre-fix module. Failures here are the evidence."""

    # -- backwards compatibility: the existing trail history must not break --

    def test_legacy_default_kid_still_verifies(self, monkeypatch, trail):
        """Every signature in the current trail carries kid=chit-signing-v01
        under the shared deployment key.  Those must verify unchanged."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail)
        assert signed["sig"]["kid"] == LEGACY_KID
        assert verify_cgp(signed) is True

    def test_legacy_default_kid_verifies_alongside_agent_keys(self, monkeypatch, trail):
        """A per-agent key existing elsewhere must not invalidate history."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        assert verify_cgp(signed) is True

    def test_payload_with_no_kid_still_verifies(self, monkeypatch, trail):
        """Legacy artifacts predating the kid stamp.  Dropping `sig.kid` does
        not disturb the MAC (the whole `sig` block is excluded from _canon),
        so this is a faithful stand-in for a pre-kid payload."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail)
        signed["sig"].pop("kid")
        assert "kid" not in signed["sig"]
        assert verify_cgp(signed) is True

    def test_tamper_still_detected(self, monkeypatch, trail):
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail)
        signed["summary"] = "tampered"
        assert verify_cgp(signed) is False

    # ---------------- per-agent identity: the actual fix -------------------

    def test_agent_kid_signs_with_agent_key(self, monkeypatch, trail):
        """PRE-FIX FAILS: sign_cgp used the deployment key regardless of kid,
        so the artifact never carried the agent's key at all."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        signed = sign_cgp(trail, kid=AGENT_KID)
        assert signed["sig"]["kid"] == AGENT_KID
        # Signed with the agent key, provably: it verifies under that key...
        assert verify_cgp(signed, passphrase=AGENT_KEY) is True
        # ...and not under the deployment key.
        assert verify_cgp(signed, passphrase=DEPLOY_KEY) is False

    def test_agent_kid_verifies_by_kid_lookup(self, monkeypatch, trail):
        """THE HEADLINE. PRE-FIX FAILS: verify resolved one key and ignored
        `kid`, so a per-agent signature verified for nobody."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        signed = sign_cgp(trail, kid=AGENT_KID)
        assert verify_cgp(signed) is True

    def test_two_kids_coexist_and_do_not_cross_verify(self, monkeypatch, trail):
        """PRE-FIX FAILS: two agents with two keys cannot both verify."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        monkeypatch.setenv(OTHER_KID_ENV, OTHER_AGENT_KEY)

        a = sign_cgp(trail, kid=AGENT_KID)
        b = sign_cgp(trail, kid=OTHER_KID)
        assert verify_cgp(a) is True
        assert verify_cgp(b) is True

        # Restamping a's kid onto b's signature must not verify: the kid names
        # a key that did not produce this MAC.
        forged = copy.deepcopy(b)
        forged["sig"]["kid"] = AGENT_KID
        assert verify_cgp(forged) is False

    def test_wrong_key_under_right_kid_fails(self, monkeypatch, trail):
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        signed = sign_cgp(trail, kid=AGENT_KID)
        monkeypatch.setenv(AGENT_KID_ENV, OTHER_AGENT_KEY)
        assert verify_cgp(signed) is False

    # ----------------------- fail closed on unknown kid ---------------------

    def test_unknown_kid_does_not_silently_pass(self, monkeypatch, trail):
        """PRE-FIX FAILS (returns True) — the defining defect.

        A signature naming `agent-ghost`, a key this deployment does not have,
        was checked against the deployment key and reported VALID.  That is a
        check that cannot fail.  The artifact is minted before hardening and
        verified after, which is the realistic migration ordering.
        """
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail, kid="agent-ghost")
        assert signed["sig"]["kid"] == "agent-ghost"

        monkeypatch.setenv("CHIT_KID_STRICT", "1")
        assert verify_cgp(signed) is False

    def test_unknown_kid_fails_closed_once_any_agent_key_exists(
        self, monkeypatch, trail
    ):
        """PRE-FIX FAILS. Provisioning any per-kid key opts the deployment into
        per-agent identity; from then on an unresolvable kid is a failure with
        no explicit flag needed."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail, kid="agent-ghost")
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        assert verify_cgp(signed) is False

    def test_strict_mode_is_not_payload_controlled(self, monkeypatch, trail):
        """A crafted payload must not be able to talk the verifier out of
        strict mode. The gate keys off operator config only."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail, kid="agent-ghost")
        monkeypatch.setenv("CHIT_KID_STRICT", "1")
        for injected in ({"CHIT_KID_STRICT": "0"}, "0", False, None):
            probe = copy.deepcopy(signed)
            probe["sig"]["strict"] = injected
            assert verify_cgp(probe) is False

    def test_single_key_regime_is_todays_behaviour(self, monkeypatch, trail):
        """Degrade-to-today: with no per-kid key anywhere and no strict flag,
        an arbitrary kid still resolves to the deployment key exactly as before.
        This passes pre-fix too — it is the no-regression guard, not evidence."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail, kid="some-unregistered-kid")
        assert verify_cgp(signed) is True

    def test_no_key_configured_still_raises_runtime_error(self, trail):
        with pytest.raises(RuntimeError):
            sign_cgp(trail)

    # -------------------------- key material never leaks --------------------

    def test_no_key_material_in_unresolved_kid_error_path(self, monkeypatch, trail):
        """Error paths leak by default (a sibling found http.client.putheader
        embeds the header value verbatim in its ValueError).  Prove this one
        does not: sign, harden, verify, and assert no key appears anywhere in
        the raised/returned text."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail, kid="agent-ghost")
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)

        blob = ""
        try:
            from pmoves.tools.chit_security import resolve_signing_key as _r

            _r("agent-ghost")
        except Exception as exc:  # noqa: BLE001 — we are inspecting the text
            blob += f"{exc!r} {exc!s}"
        blob += repr(verify_cgp(signed))

        for secret in (DEPLOY_KEY, AGENT_KEY, OTHER_AGENT_KEY):
            assert secret not in blob


@_needs_api
class TestKidResolutionAPI:
    """New surface. Skipped pre-fix — skips are not evidence."""

    def test_detailed_distinguishes_unresolved_from_mismatch(self, monkeypatch, trail):
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        ghost = sign_cgp(trail, kid="agent-ghost")
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)

        unresolved = verify_cgp_detailed(ghost)
        assert unresolved.status is SignatureStatus.UNRESOLVED_KID
        assert unresolved.exit_code == 3  # could-not-measure, not a finding

        good = sign_cgp(trail, kid=AGENT_KID)
        tampered = copy.deepcopy(good)
        tampered["summary"] = "tampered"
        mismatch = verify_cgp_detailed(tampered)
        assert mismatch.status is SignatureStatus.MISMATCH
        assert mismatch.exit_code == 1  # a finding

        assert verify_cgp_detailed(good).exit_code == 0

    def test_unresolved_result_is_falsy(self, monkeypatch, trail):
        """A caller that ignores `.status` entirely must still fail closed."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        ghost = sign_cgp(trail, kid="agent-ghost")
        monkeypatch.setenv("CHIT_KID_STRICT", "1")
        result = verify_cgp_detailed(ghost)
        assert bool(result) is False
        assert result.verified is False
        assert not result

    def test_pinned_vs_unpinned_is_reported(self, monkeypatch, trail):
        """The distinction the whole PR is about: OK means the named agent's
        key verified it; OK_UNPINNED means the deployment key did."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        legacy = verify_cgp_detailed(sign_cgp(trail))
        assert legacy.status is SignatureStatus.OK_UNPINNED
        assert legacy.key_source == "CHIT_SIGNING_KEY"

        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        agent = verify_cgp_detailed(sign_cgp(trail, kid=AGENT_KID))
        assert agent.status is SignatureStatus.OK
        assert agent.key_source == AGENT_KID_ENV
        assert agent.kid == AGENT_KID

    def test_no_signature_status(self, trail):
        result = verify_cgp_detailed(trail)
        assert result.status is SignatureStatus.NO_SIGNATURE
        assert bool(result) is False

    def test_resolve_by_file_mirrors_existing_pattern(self, monkeypatch, tmp_path, trail):
        """Per-kid keys support the same `_FILE` indirection as CHIT_SIGNING_KEY."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        key_file = tmp_path / "agent.key"
        key_file.write_text(AGENT_KEY + "\n", encoding="utf-8")
        monkeypatch.setenv(f"{AGENT_KID_ENV}_FILE", str(key_file))

        signed = sign_cgp(trail, kid=AGENT_KID)
        result = verify_cgp_detailed(signed)
        assert result.status is SignatureStatus.OK
        assert result.key_source == AGENT_KID_ENV

    def test_signing_key_id_env_aliases_the_default_key(self, monkeypatch, trail):
        """A deployment that renamed its default kid keeps working, and its
        history under the historical constant keeps verifying too."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv("CHIT_SIGNING_KEY_ID", "b850-default")
        renamed = sign_cgp(trail)
        assert renamed["sig"]["kid"] == "b850-default"
        assert verify_cgp(renamed) is True

        monkeypatch.setenv("CHIT_KID_STRICT", "1")
        monkeypatch.delenv("CHIT_SIGNING_KEY_ID")
        historical = sign_cgp(trail, kid=DEFAULT_KID)
        assert verify_cgp(historical) is True

    def test_signing_key_id_is_not_parsed_as_a_per_kid_entry(self, monkeypatch, trail):
        """`CHIT_SIGNING_KEY_ID` / `_FILE` use a single underscore; per-kid
        entries use a double one, so the former can never be misread as a key
        for kid 'ID' and can never flip strict mode on by itself."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv("CHIT_SIGNING_KEY_ID", "b850-default")
        signed = sign_cgp(trail, kid="agent-ghost")
        # Still single-key regime -> today's behaviour, no strictness.
        assert verify_cgp_detailed(signed).status is SignatureStatus.OK_UNPINNED

    def test_strict_escape_hatch_is_explicit(self, monkeypatch, trail):
        """CHIT_KID_STRICT=0 restores single-key behaviour during migration —
        an opt-in, never a silent default."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        signed = sign_cgp(trail, kid="agent-ghost")
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        assert verify_cgp(signed) is False
        monkeypatch.setenv("CHIT_KID_STRICT", "0")
        assert verify_cgp(signed) is True

    def test_sign_fails_loudly_for_unprovisioned_kid_in_strict(self, monkeypatch, trail):
        """Better to fail at sign time than to mint an artifact nobody can
        verify. KidResolutionError subclasses RuntimeError so existing
        `pytest.raises(RuntimeError)` callers keep working."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)
        with pytest.raises(KidResolutionError) as exc_info:
            sign_cgp(trail, kid="agent-ghost")
        assert isinstance(exc_info.value, RuntimeError)
        assert "CHIT_SIGNING_KEY__AGENT_GHOST" in str(exc_info.value)

    def test_error_and_result_carry_names_not_values(self, monkeypatch, trail):
        """No key material in any exception, VerifyResult, or repr."""
        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)

        err = KidResolutionError("agent-ghost", ["CHIT_SIGNING_KEY__AGENT_GHOST"])
        blobs = [str(err), repr(err)]

        ghost = sign_cgp(trail, kid="agent-ghost", passphrase=DEPLOY_KEY)
        r = verify_cgp_detailed(ghost)
        blobs += [str(r), repr(r), r.detail, json.dumps(r.kid), str(r.key_source)]

        ok = verify_cgp_detailed(sign_cgp(trail, kid=AGENT_KID))
        blobs += [str(ok), repr(ok), ok.detail]

        for blob in blobs:
            for secret in (DEPLOY_KEY, AGENT_KEY, OTHER_AGENT_KEY):
                assert secret not in blob

    def test_encrypt_anchors_signs_with_the_kid_key(self, monkeypatch):
        """encrypt_anchors() used to pre-resolve the default key and pass it to
        sign_cgp as an explicit passphrase, which would force the deployment
        key even for an agent kid."""
        pytest.importorskip("cryptography")
        pytest.importorskip("numpy")
        from pmoves.tools.chit_security import encrypt_anchors

        monkeypatch.setenv("CHIT_SIGNING_KEY", DEPLOY_KEY)
        monkeypatch.setenv("CHIT_ENCRYPTION_KEY", "encryption-key-for-tests-only")
        monkeypatch.setenv(AGENT_KID_ENV, AGENT_KEY)

        cgp = {
            "version": "cgp/0.2",
            "super_nodes": [
                {"constellations": [{"id": "c1", "anchor": [0.1, 0.2, 0.3]}]}
            ],
        }
        out = encrypt_anchors(cgp, kid=AGENT_KID)
        assert out["sig"]["kid"] == AGENT_KID
        assert verify_cgp_detailed(out).status is SignatureStatus.OK

    def test_kid_normalisation(self):
        from pmoves.tools.chit_security import _kid_env_name

        assert _kid_env_name("chit-signing-v01") == "CHIT_SIGNING_KEY__CHIT_SIGNING_V01"
        assert _kid_env_name("agent.b850/claude") == "CHIT_SIGNING_KEY__AGENT_B850_CLAUDE"
        assert _kid_env_name("--x--") == "CHIT_SIGNING_KEY__X"
