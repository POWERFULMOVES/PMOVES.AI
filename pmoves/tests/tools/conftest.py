"""Directory-scoped network guard for the `pmoves/tools/` unit tests.

WHY THIS EXISTS
---------------
These are offline tests. Every one of them stubs whatever would otherwise leave
the box. Nothing enforced that, and the enforcement gap is not hypothetical --
it has already been paid for once, in this very directory:

`test_cipher_preflight.py` used to stub `urllib.request.urlopen`. When
`cipher_preflight.probe` moved to an opener (`build_opener(...).open(...)`) so
redirects could be refused, that call stopped routing through `urlopen`. The
stubs silently detached. The suite kept passing -- while dialling the real
network on every run. The only visible symptom was the wall clock: 0.05s to
6.35s. Nothing failed. A test that quietly stops testing is this fleet's
dominant defect class, and a green suite that is measuring the operator's own
laptop instead of the code is worse than a red one.

So: deny the syscall. If a future edit bypasses the module's `_urlopen` seam,
the test fails LOUDLY at the connect, naming the address it tried to reach,
instead of silently succeeding against a live service.

BLAST RADIUS
------------
Deliberately this directory only, not `pmoves/tests/conftest.py`. The shared
conftest owns `nats_available`, which probes 127.0.0.1:4222 for real and must
keep working for the integration suites; a repo-wide guard would break it (or
worse, make it always report NATS down). Verified against the full
`pmoves/tests/tools/` run: pass/fail counts are unchanged with this file in
place.

Listening, binding and socketpair are untouched. Outbound CONNECTS to the
loopback (127.0.0.0/8, ::1, localhost) are ALSO allowed: tests/tools spins up
its own stub servers on 127.0.0.1 (agent_zero_smoke) and must be able to dial
them. Everything else -- every non-loopback address -- is denied. A test that
needs a remote service patches the module's seam instead of dialling it.
"""

from __future__ import annotations

import socket

import pytest


class NetworkEscape(AssertionError):
    """A test in this directory tried to open a real connection."""


_MESSAGE = (
    "network access is denied in pmoves/tests/tools/ — a stub or seam was "
    "bypassed and this test would otherwise have measured a live service "
    "instead of the code under test. Attempted: {target!r}. Patch the module's "
    "own network seam (e.g. cipher_preflight._urlopen), not a urllib "
    "internal. See pmoves/tests/tools/conftest.py."
)


def _loopback(target) -> bool:
    """Is this connect target the test's own loopback? (stub servers bind there)"""
    if isinstance(target, tuple) and target:
        host = str(target[0]).strip("[]").lower()
    elif isinstance(target, bytes):
        host = target.decode("utf-8", "replace").strip("[]").lower()
    elif isinstance(target, str):
        host = target.strip("[]").lower()
    else:
        return False
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


_LOOPBACK_HOSTS = {"::1", "localhost"}


@pytest.fixture(autouse=True)
def _deny_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: fail outbound connects to NON-loopback addresses.

    Loopback connects are allowed: tests/tools stands up its own stub servers
    on 127.0.0.1 (agent_zero_smoke) and dials them — that dial is the test
    double, not a network escape. Everything off-box is refused loudly.
    """

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def _guard(target, allow_real, *args, **kwargs):
        if _loopback(target):
            return allow_real(*args, **kwargs)
        raise NetworkEscape(_MESSAGE.format(target=target))

    def _connect(self, address, *args, **kwargs):
        return _guard(address, real_connect, self, address, *args, **kwargs)

    def _connect_ex(self, address, *args, **kwargs):
        return _guard(address, real_connect_ex, self, address, *args, **kwargs)

    def _create_connection(address, *args, **kwargs):
        return _guard(address, real_create_connection, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", _connect, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _connect_ex, raising=True)
    monkeypatch.setattr(socket, "create_connection", _create_connection, raising=True)
