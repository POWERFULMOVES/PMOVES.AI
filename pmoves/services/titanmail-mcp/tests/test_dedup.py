"""Mandate (c): deterministic-first dedup, zero false merges on the fixture."""
from datetime import datetime, timedelta, timezone

from titanmail.dedup import dedup, fallback_key
from titanmail.evalkit.fixture import build_fixture
from titanmail.models import EmailMessage, normalize_address, normalize_message_id

T0 = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


def m(i, *, mid="", sender="a@x.test", subject="s", body="b", dt=T0, to=("me@x.test",)):
    return EmailMessage(id=i, date=dt, subject=subject, from_addr=sender, to=list(to),
                        message_id=mid, body_text=body)


def test_fixture_has_zero_false_merges_and_full_recall():
    fx = build_fixture()
    res = dedup(fx.emails())
    truth = fx.true_duplicate_pairs()
    merged = res.merged_pairs()
    assert merged - truth == set(), f"false merges: {sorted(map(sorted, merged - truth))[:5]}"
    assert len(truth) >= 25 and merged == truth


def test_message_id_mirror_copies_merge():
    res = dedup([m("1", mid="<abc@X.TEST>"), m("2", mid="abc@x.test", dt=T0 + timedelta(seconds=40))])
    assert [c.rule for c in res.clusters] == ["message_id"]


def test_message_id_collision_with_different_sender_is_not_merged():
    res = dedup([m("1", mid="abc@x.test"), m("2", mid="abc@x.test", sender="other@y.test")])
    assert res.clusters == [] and len(res.conflicts) == 1


def test_message_id_local_part_is_case_sensitive():
    assert normalize_message_id("<ABC@Host.Test>") == "ABC@host.test"
    res = dedup([m("1", mid="ABC@x.test"), m("2", mid="abc@x.test")])
    assert res.clusters == []


def test_fallback_merges_only_within_window():
    res = dedup([m("1"), m("2", dt=T0 + timedelta(seconds=90)), m("3", dt=T0 + timedelta(minutes=10))])
    assert len(res.clusters) == 1 and {x.id for x in res.clusters[0].members} == {"1", "2"}
    assert res.ambiguous and res.ambiguous[0]["ids"] == ["2", "3"]


def test_fallback_has_no_bucket_boundary_split():
    # 23:59:30 and 00:00:30 straddle a day/bucket edge but are 60 s apart
    a = datetime(2026, 9, 1, 23, 59, 30, tzinfo=timezone.utc)
    res = dedup([m("1", dt=a), m("2", dt=a + timedelta(seconds=60))])
    assert len(res.clusters) == 1


def test_message_id_and_no_message_id_never_fallback_merged():
    res = dedup([m("1", mid="abc@x.test"), m("2")])
    assert res.clusters == []


def test_different_content_or_recipients_not_merged():
    res = dedup([m("1"), m("2", body="different"), m("3", to=("you@x.test",)), m("4", subject="Re: s")])
    assert res.clusters == []


def test_address_normalization_is_conservative():
    assert normalize_address('"Ana" <Ana@Acme.Test>') == "ana@acme.test"
    assert normalize_address("ana+news@acme.test") == "ana+news@acme.test"  # no plus stripping
    assert fallback_key(m("1", sender="Ana <ANA@x.test>")) == fallback_key(m("2", sender="ana@x.test"))


def test_tie_breaker_seam_is_called_for_conflicts_only():
    calls = []

    class Recorder:
        def decide(self, group, reason):
            calls.append((reason, sorted(x.id for x in group)))
            return []

    dedup([m("1", mid="abc@x.test"), m("2", mid="abc@x.test", sender="o@y.test"), m("3", mid="z@x.test")],
          tie_breaker=Recorder())
    assert calls == [("message_id_conflict", ["1", "2"])]
