"""Tests for the funnel-side self-generated secrets guard.

The Supabase JWT derivation must match scripts/supabase/generate-keys.sh
byte-for-byte; the guard must be additive (never overwrite operator values) and
must not fabricate POSTGRES_PASSWORD. An EXPIRED self-generated JWT is the one
exception to additivity: these labels are re-derivable from JWT_SECRET by
construction, so a dead key is stale, not operator intent.
"""
import base64

import pytest
import json
import time

from pmoves.tools.secrets_self_generated import (
    SELF_GENERATED,
    _jwt_exp_claim,
    derive_supabase_jwt,
    fill_self_generated,
)

# Vector produced by generate-keys.sh's generate_jwt_token for this secret+role
# (verified byte-for-byte against the shell openssl pipeline).
_SECRET = "test-jwt-secret-1234567890"
_ANON = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlLWxvY2FsIiwiaWF0IjoxNjQxNzY5MjAwLCJleHAiOjE3OTk1MzU2MDB9."
    "XBdxir4-NBsyWuaWBM3b6me3NKgqkUroUMeCCbAMM90"
)


def _decode_claims(token: str) -> dict:
    payload = token.split(".")[1]
    pad = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(pad))


def test_derive_matches_generate_keys_sh_vector():
    assert derive_supabase_jwt(_SECRET, "anon") == _ANON


def test_derive_role_changes_token():
    assert derive_supabase_jwt(_SECRET, "service_role") != derive_supabase_jwt(_SECRET, "anon")


def test_fill_derives_all_supabase_labels_from_jwt_secret():
    out = fill_self_generated({"JWT_SECRET": _SECRET})
    assert out["SUPABASE_ANON_KEY"] == _ANON
    assert out["ANON_KEY"] == _ANON
    assert out["NEXT_PUBLIC_SUPABASE_ANON_KEY"] == _ANON
    # service_role derived and consistent across its aliases
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == out["SERVICE_ROLE_KEY"]
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == derive_supabase_jwt(_SECRET, "service_role")


def test_fill_accepts_supabase_jwt_secret_alias():
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _SECRET})
    assert out["SUPABASE_ANON_KEY"] == _ANON


def test_fill_never_overwrites_operator_value():
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SUPABASE_ANON_KEY": "operator-set"})
    assert out["SUPABASE_ANON_KEY"] == "operator-set"


def test_fill_no_jwt_secret_is_noop():
    src = {"SOME_OTHER_KEY": "x"}
    assert fill_self_generated(src) == src


def test_fill_does_not_fabricate_postgres_password():
    out = fill_self_generated({"JWT_SECRET": _SECRET})
    assert "POSTGRES_PASSWORD" not in out


def test_postgres_recognized_but_not_derivable():
    # Recognized as self-generated (skip operator-missing reports) but never minted here.
    assert "POSTGRES_PASSWORD" in SELF_GENERATED


def test_self_generated_covers_supabase_labels():
    for label in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "POSTGRES_PASSWORD"):
        assert label in SELF_GENERATED


# --- expired-JWT refresh (knuckles 2026-10-22 incident) ---


def _expired_jwt(secret: str, role: str, exp: int) -> str:
    return derive_supabase_jwt(secret, role, iat=exp - 365 * 86400, exp=exp)


def test_fill_refreshes_expired_service_role_jwt():
    dead = _expired_jwt(_SECRET, "service_role", exp=int(time.time()) - 3600)
    # #3433: the refresh needs the local compose runtime STATED (expired keys are
    # gated like live ones: minted by this node AND this node's stack verifies).
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SERVICE_ROLE_KEY": dead, "SUPABASE_RUNTIME": "compose"})
    fresh = out["SERVICE_ROLE_KEY"]
    assert fresh != dead
    claims = _decode_claims(fresh)
    assert claims["role"] == "service_role"
    assert claims["exp"] > int(time.time()) + 9 * 365 * 86400


def test_fill_refreshes_all_aliases_of_same_role_consistently():
    dead = _expired_jwt(_SECRET, "anon", exp=int(time.time()) - 60)
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SUPABASE_ANON_KEY": dead, "SUPABASE_RUNTIME": "compose"})
    assert out["SUPABASE_ANON_KEY"] != dead
    assert out["ANON_KEY"] == out["NEXT_PUBLIC_SUPABASE_ANON_KEY"] == out["SUPABASE_ANON_KEY"]


def test_fill_never_touches_live_operator_jwt():
    # The canonical fixed-exp vector is far-future; must survive byte-exact.
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SUPABASE_ANON_KEY": _ANON})
    assert out["SUPABASE_ANON_KEY"] == _ANON


def test_fill_leaves_non_jwt_values_alone():
    # New-style sb_secret_* / opaque tokens are not refreshable here.
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SERVICE_ROLE_KEY": "sb_secret_opaque"})
    assert out["SERVICE_ROLE_KEY"] == "sb_secret_opaque"


def test_jwt_exp_claim_shapes():
    assert _jwt_exp_claim(None) is None
    assert _jwt_exp_claim("") is None
    assert _jwt_exp_claim("not-a-jwt") is None
    assert _jwt_exp_claim("a.b.c") is None  # undecodable payload
    assert _jwt_exp_claim(_ANON) == 1799535600
    no_exp = derive_supabase_jwt(_SECRET, "anon", exp=0)
    # exp claim present but zero is still an int
    assert _jwt_exp_claim(no_exp) == 0


def test_refreshed_token_signature_verifies_with_same_secret():
    import hashlib
    import hmac as hmac_mod

    dead = _expired_jwt(_SECRET, "service_role", exp=int(time.time()) - 1)
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SERVICE_ROLE_KEY": dead, "SUPABASE_RUNTIME": "compose"})
    token = out["SERVICE_ROLE_KEY"]
    assert token != dead  # otherwise the signature check below is vacuous
    header, payload, sig = token.split(".")
    expected = base64.urlsafe_b64encode(
        hmac_mod.new(_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    assert sig == expected


# ── verifier precedence (#3433 review P2) ────────────────────────────────────
# Every compose verifier (PostgREST, GoTrue, Realtime, Studio) reads
# ${SUPABASE_JWT_SECRET:-${JWT_SECRET:-}}. Minting JWT_SECRET-first produced keys
# Kong admits but PostgREST refuses (PGRST301) wherever the two secrets differ.

_VERIFIER = "verifier-secret-abcdefghijklmnopqrstuvwxyz"
_OTHER = "legacy-jwt-secret-abcdefghijklmnopqrstuvwxyz"


def _signed_by(token: str, secret: str) -> bool:
    import hashlib
    import hmac as hmac_mod

    header, payload, sig = token.split(".")
    expected = base64.urlsafe_b64encode(
        hmac_mod.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return sig == expected


def test_mints_with_the_verifiers_secret_when_the_two_secrets_differ():
    out = fill_self_generated({"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER})
    for label in ("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY", "ANON_KEY"):
        assert _signed_by(out[label], _VERIFIER), label
        assert not _signed_by(out[label], _OTHER), label


def test_remints_a_live_key_that_does_not_verify_under_the_verifiers_secret():
    # Live (unexpired) but minted under the other secret: the old funnel left it,
    # so PostgREST refused it forever. It is self-generated, so re-mint it.
    live_exp = int(time.time()) + 365 * 86400
    wrong = derive_supabase_jwt(_OTHER, "service_role", exp=live_exp)
    out = fill_self_generated({
        "JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER,
        "SUPABASE_SERVICE_ROLE_KEY": wrong, "SERVICE_ROLE_KEY": wrong,
        "SUPABASE_RUNTIME": "compose",
    })
    assert out["SUPABASE_SERVICE_ROLE_KEY"] != wrong
    assert _signed_by(out["SUPABASE_SERVICE_ROLE_KEY"], _VERIFIER)
    # one role, one key: every alias moves to the same mint
    assert out["SERVICE_ROLE_KEY"] == out["SUPABASE_SERVICE_ROLE_KEY"]


def test_live_key_that_verifies_is_still_never_touched():
    live = derive_supabase_jwt(_VERIFIER, "service_role", exp=int(time.time()) + 86400)
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": live})
    assert out["SERVICE_ROLE_KEY"] == live


def test_non_hs256_values_are_never_judged_by_signature():
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": "sb_secret_opaque"})
    assert out["SERVICE_ROLE_KEY"] == "sb_secret_opaque"



# ── ownership + runtime gates on the live re-mint (#3433 follow-up P1/P2/P3) ──
# A live key is rewritten only if it is provably funnel-minted (HS256, iss
# supabase-local, the label's role) AND this node's compose Supabase is the
# verifier. Before #3433 live keys were never touched; a CLI/cloud key that does
# not verify under OUR secret may be exactly right for ITS verifier.

from pmoves.tools.secrets_self_generated import compose_consumers, local_runtime_is_verifier  # noqa: E402

_LIVE = int(time.time()) + 365 * 86400
_COMPOSE = {"SUPABASE_RUNTIME": "compose"}


def _jwt(header: dict, claims: dict, secret: str = "x") -> str:
    import hashlib
    import hmac as hmac_mod

    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()  # noqa: E731
    si = f"{enc(header)}.{enc(claims)}"
    sig = base64.urlsafe_b64encode(hmac_mod.new(secret.encode(), si.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{si}.{sig}"


def _base(**extra):
    return {"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER, **_COMPOSE, **extra}


def test_rs256_shaped_jwt_is_left_alone():
    rs = _jwt({"alg": "RS256", "typ": "JWT"}, {"role": "anon", "iss": "supabase-local", "exp": _LIVE})
    events = []
    out = fill_self_generated(_base(SUPABASE_ANON_KEY=rs), events=events)
    assert out["SUPABASE_ANON_KEY"] == rs
    assert not [e for e in events if e["label"] == "SUPABASE_ANON_KEY"]


def test_foreign_iss_hs256_cloud_key_is_left_alone_and_warned_by_name():
    cloud = _jwt({"alg": "HS256", "typ": "JWT"},
                 {"iss": "supabase", "ref": "abcd", "role": "anon", "exp": _LIVE}, secret="cloud-secret")
    events = []
    out = fill_self_generated(_base(SUPABASE_ANON_KEY=cloud, NEXT_PUBLIC_SUPABASE_ANON_KEY=cloud), events=events)
    assert out["SUPABASE_ANON_KEY"] == cloud and out["NEXT_PUBLIC_SUPABASE_ANON_KEY"] == cloud
    assert {(e["label"], e["action"], e["reason"]) for e in events if e["role"] == "anon" and e["action"] != "filled"} == {
        ("SUPABASE_ANON_KEY", "left_unchanged", "not_minted_here"),
        ("NEXT_PUBLIC_SUPABASE_ANON_KEY", "left_unchanged", "not_minted_here"),
    }
    assert all(cloud not in str(e) for e in events)


def test_our_key_signed_with_the_other_secret_is_reminted_and_announced(capsys):
    from pmoves.tools.secrets_sync import announce_jwt_events

    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)  # iss supabase-local
    events = []
    out = fill_self_generated(_base(SUPABASE_SERVICE_ROLE_KEY=ours, SERVICE_ROLE_KEY=ours), events=events)
    assert out["SUPABASE_SERVICE_ROLE_KEY"] != ours and _signed_by(out["SUPABASE_SERVICE_ROLE_KEY"], _VERIFIER)
    assert ("SUPABASE_SERVICE_ROLE_KEY", "reminted", "signed_with_other_secret") in {
        (e["label"], e["action"], e["reason"]) for e in events}
    consumers = announce_jwt_events(events)  # real compose files
    printed = capsys.readouterr().out
    assert "could not read" not in printed  # every docker-compose*.yml parsed (incl. !reset overlays)
    assert "RE-MINTED SUPABASE_SERVICE_ROLE_KEY (service_role): signed_with_other_secret" in printed
    assert {"supabase-kong", "cipher-api"} <= set(consumers)
    assert "make -C pmoves up-supabase" in printed and "make -C pmoves up-cipher" in printed
    assert ours not in printed and out["SUPABASE_SERVICE_ROLE_KEY"] not in printed


@pytest.mark.parametrize(
    "ctx, reason",
    [
        ({"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": "https://abcd.supabase.co"}, "remote_url"),
        ({"SUPABASE_RUNTIME": "compose", "SUPABASE_REST_URL": "http://node.tailnet.example:8000/rest/v1"}, "remote_url"),
        ({"SUPABASE_RUNTIME": "cli"}, "runtime_cli"),
        ({}, "runtime_unknown"),
    ],
    ids=["cloud-url", "remote-rest-url", "cli-runtime", "runtime-unstated"],
)
def test_no_live_remint_unless_the_local_compose_stack_is_the_verifier(ctx, reason):
    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    secrets = {"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER,
               "SUPABASE_SERVICE_ROLE_KEY": ours, "SERVICE_ROLE_KEY": ours, **ctx}
    events = []
    out = fill_self_generated(secrets, events=events)
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == ours and out["SERVICE_ROLE_KEY"] == ours
    assert {e["reason"] for e in events if e["role"] == "service_role"} == {reason}


_SERVICES = frozenset({"supabase-kong", "supabase-postgrest"})


def test_local_urls_count_as_local():
    for url in ("http://supabase-kong:8000", "http://localhost:3001", "http://127.0.0.1:8000/rest/v1",
                "http://host.docker.internal:8000"):
        assert local_runtime_is_verifier({"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": url},
                                         _SERVICES) == (True, "local"), url


@pytest.mark.parametrize(
    "url",
    ["http://pmoves-z890:8000",      # tailnet MagicDNS short name (a PEER's Supabase)
     "http://nas:8000",              # LAN short hostname
     "http://supabase-kong:8000"],   # a real compose name, but no service set was loaded
    ids=["magicdns-short", "lan-short", "compose-name-without-service-set"],
)
def test_dotless_hosts_are_not_local_unless_defined_in_compose(url):
    ctx = {"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": url}
    services = None if "supabase-kong" in url else _SERVICES
    assert local_runtime_is_verifier(ctx, services) == (False, "remote_url")


def test_peer_short_name_never_triggers_a_remint():
    """Measured by the #3433 final review: runtime=compose +
    SUPABASE_URL=http://pmoves-z890:8000 re-minted our-iss key. It must not."""
    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    secrets = _base(SERVICE_ROLE_KEY=ours, SUPABASE_URL="http://pmoves-z890:8000")
    events = []
    out = fill_self_generated(secrets, events=events, local_services=_SERVICES)
    assert out["SERVICE_ROLE_KEY"] == ours
    assert ("SERVICE_ROLE_KEY", "left_unchanged", "remote_url") in {(e["label"], e["action"], e["reason"]) for e in events}


def test_real_compose_service_names_are_local():
    from pmoves.tools.secrets_self_generated import compose_service_names
    from pmoves.tools.secrets_sync import load_compose_docs

    docs, skipped = load_compose_docs()
    assert skipped == []
    services = compose_service_names(docs)
    assert {"supabase-kong", "supabase-postgrest", "cipher-api"} <= services
    assert "pmoves-z890" not in services
    assert local_runtime_is_verifier({"SUPABASE_RUNTIME": "compose",
                                      "SUPABASE_REST_URL": "http://supabase-kong:8000/rest/v1"},
                                     services) == (True, "local")


def test_another_pmoves_nodes_key_is_not_ours_even_with_our_iss():
    """iss supabase-local is stamped by EVERY PMOVES funnel. A key signed by a
    peer's secret verifies under neither of this node's secrets: leave it."""
    peer = derive_supabase_jwt("peer-node-secret-abcdefghijklmnopqrstuvwxyz", "service_role", exp=_LIVE)
    events = []
    out = fill_self_generated(_base(SERVICE_ROLE_KEY=peer), events=events)
    assert out["SERVICE_ROLE_KEY"] == peer
    assert ("SERVICE_ROLE_KEY", "left_unchanged", "not_minted_here") in {(e["label"], e["action"], e["reason"]) for e in events}


# ── set-but-EMPTY is unknown, and the context's source is announced ────────


@pytest.mark.parametrize("var", ["SUPABASE_URL", "SUPABASE_REST_URL", "SUPABASE_RUNTIME"])
def test_set_but_empty_shell_export_means_no_live_remint(var, capsys):
    """Measured by the final review: cloud SUPABASE_URL in the map + `export
    SUPABASE_URL=` + runtime=compose RE-MINTED. Empty must be UNKNOWN."""
    from pmoves.tools.secrets_sync import announce_jwt_events, runtime_context

    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    # The secret map holds the REAL value under the very name the empty export
    # shadows (a cloud URL, or runtime=compose); the export blanks it.
    shadowed = {var: "compose" if var == "SUPABASE_RUNTIME" else "https://abcd.supabase.co"}
    secret_map = {**_base(SERVICE_ROLE_KEY=ours), **shadowed}
    environ = {var: ""} if var == "SUPABASE_RUNTIME" else {var: "", "SUPABASE_RUNTIME": "compose"}
    context, sources = runtime_context(secret_map, environ)
    events = []
    out = fill_self_generated(secret_map, context=context, events=events, local_services=_SERVICES)
    assert out["SERVICE_ROLE_KEY"] == ours
    assert {e["reason"] for e in events if e["label"] == "SERVICE_ROLE_KEY"} == {f"empty_{var}"}
    announce_jwt_events(events, docs=[], context=context, sources=sources, local_services=_SERVICES)
    printed = capsys.readouterr().out
    assert f"{var} is set but EMPTY (from shell env)" in printed
    assert "abcd.supabase.co" not in printed  # URLs are classified, never printed


def test_runtime_from_shell_env_is_announced_as_such(capsys):
    from pmoves.tools.secrets_sync import announce_jwt_events, runtime_context

    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    secret_map = {k: v for k, v in _base(SERVICE_ROLE_KEY=ours).items() if k != "SUPABASE_RUNTIME"}
    context, sources = runtime_context(secret_map, {"SUPABASE_RUNTIME": "compose"})
    events = []
    fill_self_generated(secret_map, context=context, events=events, local_services=_SERVICES)
    announce_jwt_events(events, docs=[], context=context, sources=sources, local_services=_SERVICES)
    printed = capsys.readouterr().out
    assert "SUPABASE_RUNTIME=compose (from shell env)" in printed
    assert "SUPABASE_URL=unset" in printed


def test_context_overrides_the_secret_map():
    # secrets_sync passes {**secrets, **os.environ}: an exported runtime wins.
    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    out = fill_self_generated(_base(SERVICE_ROLE_KEY=ours), context={"SUPABASE_RUNTIME": "cli"})
    assert out["SERVICE_ROLE_KEY"] == ours


# ── expired keys are gated too (#3433 final review P2) ─────────────────────


@pytest.mark.parametrize(
    "secret, ctx, reason",
    [
        ("cloud", {"SUPABASE_RUNTIME": "compose"}, "expired_not_minted_here"),       # cloud key, foreign secret
        (_VERIFIER, {"SUPABASE_RUNTIME": "cli"}, "expired_runtime_cli"),            # CLI runtime verifies it
        (_VERIFIER, {"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": "https://abcd.supabase.co"},
         "expired_remote_url"),
    ],
    ids=["cloud-key", "cli-runtime", "remote-url"],
)
def test_expired_key_not_ours_or_not_local_is_left_dead_and_warned(secret, ctx, reason, capsys):
    from pmoves.tools.secrets_sync import _refusal_text

    dead = _jwt({"alg": "HS256", "typ": "JWT"}, {"iss": "supabase-demo", "role": "service_role",
                                                 "exp": int(time.time()) - 60}, secret=secret)
    events = []
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": dead, **ctx},
                              events=events, local_services=_SERVICES)
    assert out["SERVICE_ROLE_KEY"] == dead  # visibly dead beats fresh-looking-but-refused
    ev = [e for e in events if e["label"] == "SERVICE_ROLE_KEY"]
    assert [(e["action"], e["reason"]) for e in ev] == [("left_unchanged", reason)]
    text = _refusal_text(ev[0], {})
    assert "expired" in text and dead not in text
    if reason == "expired_not_minted_here":
        assert "obtain a new key from its issuer" in text


def test_expired_key_minted_here_on_local_runtime_is_refreshed_like_3410():
    """The knuckles 2026-10-21 shape: a CLI-minted (iss supabase-demo) 1-year key
    signed with THIS node's secret. Ours by signature, so it refreshes."""
    dead = _jwt({"alg": "HS256", "typ": "JWT"}, {"iss": "supabase-demo", "role": "service_role",
                                                 "exp": int(time.time()) - 60}, secret=_VERIFIER)
    events = []
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": dead,
                               "SUPABASE_RUNTIME": "compose",
                               "SUPABASE_REST_URL": "http://supabase-kong:8000/rest/v1"},
                              events=events, local_services=_SERVICES)
    assert out["SERVICE_ROLE_KEY"] != dead and _signed_by(out["SERVICE_ROLE_KEY"], _VERIFIER)
    assert ("SERVICE_ROLE_KEY", "reminted", "expired") in {(e["label"], e["action"], e["reason"]) for e in events}


def test_compose_consumers_reads_environment_and_build_args():
    docs = [{"services": {
        "kong": {"environment": ["SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY:-}}"]},
        "ui": {"build": {"args": {"NEXT_PUBLIC_SUPABASE_ANON_KEY": "${NEXT_PUBLIC_SUPABASE_ANON_KEY}"}}},
        "other": {"environment": {"X": "${SERVICE_ROLE_KEYS_LIST}"}},   # different name, no match
    }}]
    assert compose_consumers(["SERVICE_ROLE_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"], docs) == ["kong", "ui"]


# ── announcement output is a closed vocabulary (#3433 CodeQL clear-text) ────

_FAKE = "sk_live_FAKE-SECRET-9f8e7d6c5b4a"


def test_raw_runtime_value_never_reaches_a_reason():
    """The one real flow found: SUPABASE_RUNTIME's VALUE (secret map / shell)
    used to become reason f"runtime_{value}". It is now a closed name."""
    assert local_runtime_is_verifier({"SUPABASE_RUNTIME": _FAKE}) == (False, "runtime_other")
    assert local_runtime_is_verifier({"SUPABASE_RUNTIME": "cli"}) == (False, "runtime_cli")


def test_every_emitted_event_field_is_in_the_closed_vocabulary():
    from pmoves.tools.secrets_self_generated import EVENT_ACTIONS, EVENT_REASONS, EVENT_ROLES, _SUPABASE_JWT_KEYS

    ours_other = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    dead_local = derive_supabase_jwt(_VERIFIER, "anon", iat=1, exp=int(time.time()) - 5)
    dead_cloud = _jwt({"alg": "HS256"}, {"role": "anon", "exp": int(time.time()) - 5}, secret="cloud")
    contexts = [{}, {"SUPABASE_RUNTIME": ""}, {"SUPABASE_RUNTIME": "cli"}, {"SUPABASE_RUNTIME": _FAKE},
                {"SUPABASE_RUNTIME": "compose"}, {"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": ""},
                {"SUPABASE_RUNTIME": "compose", "SUPABASE_REST_URL": "https://x.example"}]
    seen = 0
    for ctx in contexts:
        for values in ({"SERVICE_ROLE_KEY": ours_other}, {"ANON_KEY": dead_local}, {"SUPABASE_ANON_KEY": dead_cloud}, {}):
            events = []
            fill_self_generated({"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER, **values},
                                context=ctx, events=events, local_services=_SERVICES)
            for e in events:
                seen += 1
                assert e["label"] in _SUPABASE_JWT_KEYS and e["role"] in EVENT_ROLES
                assert e["action"] in EVENT_ACTIONS and e["reason"] in EVENT_REASONS, e
    assert seen > 20


@pytest.mark.parametrize("field", ["label", "role", "action", "reason"])
@pytest.mark.parametrize("shape", ["whole", "prefixed-expired", "prefixed-empty", "suffix"])
def test_fuzzed_event_fields_never_print_a_secret(field, shape, capsys):
    from pmoves.tools.secrets_sync import _refusal_text, announce_jwt_events

    poison = {"whole": _FAKE, "prefixed-expired": "expired_" + _FAKE,
              "prefixed-empty": "empty_" + _FAKE, "suffix": "SERVICE_ROLE_KEY" + _FAKE}[shape]
    base = [
        {"label": "SERVICE_ROLE_KEY", "role": "service_role", "action": "reminted", "reason": "expired"},
        {"label": "SUPABASE_ANON_KEY", "role": "anon", "action": "left_unchanged", "reason": "empty_SUPABASE_URL"},
    ]
    events = [{**e, field: poison, "extra": _FAKE} for e in base]
    context = {"SUPABASE_RUNTIME": _FAKE, "SUPABASE_URL": "https://user:" + _FAKE + "@abcd.supabase.co",
               "SUPABASE_REST_URL": _FAKE}
    sources = {k: _FAKE for k in ("SUPABASE_RUNTIME", "SUPABASE_URL", "SUPABASE_REST_URL")}
    announce_jwt_events(events, docs=[], context=context, sources=sources, local_services=_SERVICES)
    for e in events:
        print(_refusal_text(e, sources))
    printed = capsys.readouterr().out
    assert _FAKE not in printed
    assert "FAKE-SECRET" not in printed and "abcd.supabase.co" not in printed
    assert "<unrecognised>" in printed or field == "action"


# ── review threads on #3433: announce only what is written; tags as data ───


def _run_sync_main(monkeypatch, capsys, argv, *, required_missing=False):
    """Drive secrets_sync.main end to end with an in-memory manifest + secret map;
    nothing touches disk. Returns (rc, stdout, written outputs or None)."""
    from pmoves.tools import secrets_sync as ss

    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)   # signed with our OTHER secret
    secrets = {"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER, "SUPABASE_RUNTIME": "compose",
               "SERVICE_ROLE_KEY": ours, "SUPABASE_SERVICE_ROLE_KEY": ours, "OTHER_TOKEN": "x" * 40}
    entries = [
        ss.Entry(id="srk", label="SUPABASE_SERVICE_ROLE_KEY", required=True,
                 targets=[ss.Target(file="env.tier-agent", key="SUPABASE_SERVICE_ROLE_KEY")],
                 aliases=("SERVICE_ROLE_KEY",)),
        ss.Entry(id="other", label="OTHER_TOKEN", required=True,
                 targets=[ss.Target(file="env.tier-agent", key="OTHER_TOKEN")]),
    ]
    if required_missing:
        entries.append(ss.Entry(id="gone", label="ABSENT_REQUIRED", required=True,
                                targets=[ss.Target(file="env.tier-agent", key="ABSENT_REQUIRED")]))
    written = {}
    monkeypatch.setattr(ss, "load_manifest", lambda path: (path, entries))
    monkeypatch.setattr(ss, "load_cgp", lambda path: b"")
    monkeypatch.setattr(ss, "decode_secret_map", lambda payload: dict(secrets))
    monkeypatch.setattr(ss, "load_compose_docs", lambda *a, **k: ([], []))
    monkeypatch.setattr(ss, "write_env_files", lambda outputs, **kw: written.update(outputs))
    for k in ("SUPABASE_RUNTIME", "SUPABASE_URL", "SUPABASE_REST_URL"):
        monkeypatch.delenv(k, raising=False)
    rc = ss.main(argv)
    return rc, capsys.readouterr().out, (written or None)


def test_full_generate_announces_the_remint_it_writes(monkeypatch, capsys):
    rc, out, written = _run_sync_main(monkeypatch, capsys, ["generate"])
    assert rc == 0 and written
    assert "RE-MINTED SUPABASE_SERVICE_ROLE_KEY (service_role): signed_with_other_secret" in out
    assert "RECREATE every consumer" in out and "NOT WRITTEN" not in out


@pytest.mark.parametrize(
    "argv, missing",
    [(["generate", "--keys", "OTHER_TOKEN"], False),   # --keys excludes the re-minted label
     (["report"], False),                               # report-only run writes nothing
     (["generate"], True)],                             # aborted run (missing required secret)
    ids=["keys-excludes-it", "report-mode", "aborted-run"],
)
def test_a_remint_that_is_not_written_is_never_announced_as_one(argv, missing, monkeypatch, capsys):
    """r4428996868 / r4429049880: 'RE-MINTED ... RECREATE' must correspond to a
    value written on THIS run; otherwise it is reported as NOT WRITTEN."""
    rc, out, written = _run_sync_main(monkeypatch, capsys, argv, required_missing=missing)
    assert "RE-MINTED" not in out and "RECREATE" not in out
    assert "NOT WRITTEN SUPABASE_SERVICE_ROLE_KEY (service_role)" in out
    if missing:
        assert rc == 1 and written is None


def test_keys_including_the_label_still_announces_it(monkeypatch, capsys):
    rc, out, _ = _run_sync_main(monkeypatch, capsys, ["generate", "--keys", "SUPABASE_SERVICE_ROLE_KEY"])
    assert "RE-MINTED SUPABASE_SERVICE_ROLE_KEY" in out and "NOT WRITTEN" not in out


def test_not_written_path_never_prints_a_secret(capsys):
    from pmoves.tools.secrets_sync import announce_jwt_events

    events = [{"label": _FAKE, "role": _FAKE, "action": "reminted", "reason": _FAKE},
              {"label": "SERVICE_ROLE_KEY", "role": "service_role", "action": "reminted", "reason": "expired" + _FAKE}]
    announce_jwt_events(events, docs=[], written_labels=set())
    printed = capsys.readouterr().out
    assert "NOT WRITTEN" in printed and _FAKE not in printed and "FAKE-SECRET" not in printed


def test_override_and_reset_blocks_are_parsed_as_data_not_dropped(tmp_path):
    """r4428996874: a label named only inside an !override env list must still
    make its service a consumer."""
    from pmoves.tools.secrets_sync import load_compose_docs

    f = tmp_path / "docker-compose.overlay.yml"
    f.write_text(
        "services:\n"
        "  studio:\n"
        "    environment: !override\n"
        "      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-}\n"
        "  voice:\n"
        "    deploy: !reset {}\n"
        "    build:\n"
        "      args: !override\n"
        "        ANON: ${NEXT_PUBLIC_SUPABASE_ANON_KEY}\n"
    )
    docs, skipped = load_compose_docs([f])
    assert skipped == []
    assert compose_consumers(["SUPABASE_SERVICE_ROLE_KEY"], docs) == ["studio"]
    assert compose_consumers(["NEXT_PUBLIC_SUPABASE_ANON_KEY"], docs) == ["voice"]
