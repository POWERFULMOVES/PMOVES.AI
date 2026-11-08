"""Static checks for the tensorzero-clickhouse config.d override.

metric_log must stay disabled: with a TTL it is forced into Horizontal merges
across 1136 columns, which OOM a 4 GiB container and retry forever (~138% CPU).
See the comment above <metric_log> in the XML for the full provenance.
"""

from pathlib import Path
import xml.etree.ElementTree as ET

PMOVES = Path(__file__).resolve().parents[1]
OVERRIDE = PMOVES / "config" / "clickhouse" / "pmoves-system-log-limits.xml"
MOUNT = "./config/clickhouse/pmoves-system-log-limits.xml:/etc/clickhouse-server/config.d/"


def _root():
    return ET.parse(OVERRIDE).getroot()


def test_override_parses_with_clickhouse_root():
    assert _root().tag == "clickhouse"


def test_metric_log_is_removed_not_ttld():
    node = _root().find("metric_log")
    assert node is not None, "metric_log must be explicitly removed, not omitted (omitting re-enables the image default)"
    assert node.get("remove") is not None
    assert len(node) == 0, "a removed metric_log must carry no child settings"


def test_every_enabled_system_log_has_a_ttl():
    for node in _root():
        if not node.tag.endswith("_log") or node.get("remove") is not None:
            continue
        ttl = node.find("ttl")
        assert ttl is not None and "DELETE" in (ttl.text or ""), f"{node.tag} has no TTL"


def test_override_is_mounted_by_compose():
    for name in ("docker-compose.yml", "docker-compose.core.yml"):
        assert MOUNT in (PMOVES / name).read_text(encoding="utf-8"), f"{name} no longer mounts the override"
