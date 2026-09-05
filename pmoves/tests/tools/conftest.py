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

Listening, binding and socketpair are untouched -- only OUTBOUND connects are
denied -- so a test that stands up a local server on demand still can.
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


@pytest.fixture(autouse=True)
def _deny_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: fail any outbound socket connect with a message that explains it."""

    def _refuse(*args, **kwargs):
        # args[0] is `self` for the bound methods, the address for the
        # module-level helper. Report whichever looks like an address; never
        # anything else, since this is on a path that prints.
        target = next(
            (a for a in args if isinstance(a, (tuple, str, bytes))), "unknown"
        )
        raise NetworkEscape(_MESSAGE.format(target=target))

    monkeypatch.setattr(socket.socket, "connect", _refuse, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse, raising=True)
    monkeypatch.setattr(socket, "create_connection", _refuse, raising=True)
