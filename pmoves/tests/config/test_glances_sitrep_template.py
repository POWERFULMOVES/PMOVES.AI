"""Render tests for pmoves/config/glances/pmoves-sitrep.jinja.

The template is rendered exactly the way Glances 4.5.7 renders a fetch template
(glances/outputs/glances_stdout_fetch.py: ``jinja2.Environment(loader=BaseLoader(),
autoescape=True).from_string(...).render(gl=...)``) against a stub ``gl``, so the
test needs jinja2 only -- not Glances, Docker or a GPU.

Regression (review of PR #3305): upstream only fills ``memory_usage`` for ACTIVE
containers (running|healthy|paused; containers/engines/docker.py
CONTAINER_ACTIVE_STATUS). An unhealthy/starting/restarting container carries no
key or ``None``, and the first template sorted on it unguarded -- one sick
container crashed the whole sitrep, i.e. exactly when it was needed.
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

import jinja2
import pytest

PMOVES = Path(__file__).resolve().parents[2]
TEMPLATE = PMOVES / "config" / "glances" / "pmoves-sitrep.jinja"
CONF = PMOVES / "config" / "glances" / "pmoves-glances.conf"

ADDRESS_SENTINEL = "ADDR-SENTINEL-must-not-render"


class _Plugin:
    """Mimics a Glances plugin: subscriptable stats + get_raw()."""

    def __init__(self, raw, **attrs):
        self._raw = raw
        for k, v in attrs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._raw[key]

    def keys(self):
        return self._raw.keys()

    def get_raw(self):
        return self._raw

    def __str__(self):
        return str(self._raw)


class _Watcher:
    def __init__(self, client):
        self.client = client


class _Gl:
    """Stub of glances.api.GlancesAPI with only what the template may touch."""

    FORBIDDEN = {"ip", "network", "connections", "ports", "wifi"}

    def __init__(self, containers=None, watchers=None, disabled=(), os_name="Windows"):
        self._disabled = set(disabled)
        self._p = {
            "system": _Plugin({"hostname": "node-x", "hr_name": "Test OS", "os_name": os_name}),
            "uptime": _Plugin("1:00:00"),
            "version": _Plugin("4.5.7"),
            "cpu": _Plugin({"total": 12.5}),
            "core": _Plugin({"log": 8}),
            "load": _Plugin({"min1": 0.1, "min5": 0.2, "min15": 0.3}),
            "mem": _Plugin({"percent": 91.0, "used": 29 * 2**30, "total": 32 * 2**30, "available": 3 * 2**30}),
            "memswap": _Plugin({"percent": 5.0, "used": 2**30, "total": 8 * 2**30}),
            "gpu": _Plugin([{"name": "GPU-A", "mem": 7.4, "proc": 3, "temperature": 33}]),
            "fs": _Plugin({"C:\\": {"percent": 95.0, "used": 900 * 2**30, "size": 950 * 2**30}}),
            "containers": _Plugin(
                containers if containers is not None else [],
                watchers=watchers if watchers is not None else {"docker": _Watcher(object())},
            ),
            "processlist": _Plugin(
                [
                    {"name": "vmmemWSL", "memory_percent": 11.2, "memory_info": {"rss": 4 * 2**30}, "cmdline": []},
                    {"name": "app.exe", "memory_percent": 2.0, "memory_info": {"rss": 2**30}, "cmdline": ["app"]},
                ]
            ),
            "alert": _Plugin([{"state": "CRITICAL", "type": "MEM", "max": 91.0, "end": -1}]),
        }

    def __getattr__(self, item):
        if item in self.FORBIDDEN:
            raise AssertionError(f"template must not read the '{item}' plugin (addresses)")
        if item in self._disabled or item not in self._p:
            raise AttributeError(item)  # upstream GlancesAPI behaviour for disabled plugins
        return self._p[item]

    def plugins(self):
        return [p for p in self._p if p not in self._disabled]

    def auto_unit(self, number, low_precision=False, min_symbol="K", none_symbol="-"):
        return none_symbol if number is None else f"{number / 2**20:.0f}M"

    def top_process(self, limit=3, sorted_by="cpu_percent", sorted_by_secondary="memory_percent"):
        procs = [p for p in self._p["processlist"].get_raw() if p["cmdline"]]  # upstream drops cmdline-less
        return [dict(p, cpu_percent=1.0) for p in procs][:limit]


def _render(gl) -> str:
    env = jinja2.Environment(loader=jinja2.BaseLoader(), autoescape=True)  # as upstream 4.5.7
    return env.from_string(TEMPLATE.read_text(encoding="ascii")).render(gl=gl)


def _containers():
    port = {"HostIp": ADDRESS_SENTINEL, "HostPort": "1"}
    return [
        {"engine": "docker", "name": "ok-big", "status": "healthy", "memory_usage": 3 * 2**30, "ports": [port]},
        {"engine": "docker", "name": "ok-small", "status": "running", "memory_usage": 2**30, "ports": [port]},
        {"engine": "docker", "name": "sick-nokey", "status": "unhealthy", "ports": [port]},  # key absent
        {"engine": "docker", "name": "boot-none", "status": "starting", "memory_usage": None},
        {"engine": "docker", "name": "loop", "status": "restarting"},
        {"engine": "docker", "name": "gone", "status": "exited", "memory_usage": None},
    ]


def test_inactive_containers_do_not_crash_and_are_listed():
    out = _render(_Gl(containers=_containers()))
    assert "DOCKER reachable: 6 containers | 4 not running/healthy" in out
    for name, status in [("sick-nokey", "unhealthy"), ("boot-none", "starting"), ("loop", "restarting"), ("gone", "exited")]:
        assert f"{name} [{status}]" in out
    mem_lines = [line for line in out.splitlines() if line.strip().startswith("mem ")]
    assert [line.split()[-1] for line in mem_lines] == ["ok-big", "ok-small"]  # only numeric memory_usage, desc


def test_old_unguarded_sort_is_the_bug_this_guards():
    env = jinja2.Environment(loader=jinja2.BaseLoader(), autoescape=True)
    old = env.from_string("{% for c in (cs | sort(attribute='memory_usage', reverse=true))[:5] %}{{ c.name }}{% endfor %}")
    with pytest.raises((jinja2.exceptions.UndefinedError, TypeError)):
        old.render(cs=_containers())


def test_docker_unreachable_is_not_zero():
    out = _render(_Gl(watchers={"docker": _Watcher(None)}))
    assert "DOCKER unreachable" in out and "UNKNOWN (not 0)" in out
    assert "0 containers" not in out


def test_docker_extra_missing():
    out = _render(_Gl(watchers={}))
    assert "glances[containers] extra (docker SDK) not installed" in out


@pytest.mark.parametrize(
    "plugin,expected",
    [
        ("containers", "DOCKER not probed (containers plugin disabled)"),
        ("gpu", "GPU    not probed (gpu plugin disabled)"),
        ("processlist", "PROCS  not probed (processlist plugin disabled)"),
    ],
)
def test_disabled_plugins_are_reported_not_crashed(plugin, expected):
    assert expected in _render(_Gl(disabled={plugin}))


def test_vmmemwsl_shown_although_top_process_hides_it():
    out = _render(_Gl())
    assert "WSLVM  vmmemWSL" in out
    top_rows = out.split("TOP MEM", 1)[1].split("TOP CPU", 1)[0].splitlines()[1:]  # skip header
    assert top_rows and not any("vmmemWSL" in row for row in top_rows)  # proves the WSLVM line is the only place it can appear


def test_no_addresses_rendered():
    out = _render(_Gl(containers=_containers()))
    assert ADDRESS_SENTINEL not in out
    assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", out)


def test_thresholds_flagged():
    out = _render(_Gl())
    assert "!! CRITICAL" in out  # mem 91 %
    assert "!! >=90%" in out  # disk 95 %


def test_template_is_ascii():
    # Glances opens --fetch-template with the platform default encoding (cp1252 on Windows).
    TEMPLATE.read_bytes().decode("ascii")


def test_pmoves_conf_disables_address_plugins():
    raw = CONF.read_bytes()
    raw.decode("ascii")
    cp = configparser.ConfigParser()
    cp.read_string(raw.decode("ascii"))
    for section in ("ip", "cloud", "connections"):
        assert cp.getboolean(section, "disable"), section
    assert cp.getboolean("global", "check_update") is False


def test_hermes_profiles_do_not_reenable_ip_plugin():
    for conf in (PMOVES / "config" / "profiles" / "hermes").glob("*glances*.conf"):
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        cp.read(conf, encoding="utf-8")
        assert not (cp.has_section("ip") and not cp.getboolean("ip", "disable", fallback=False)), conf
