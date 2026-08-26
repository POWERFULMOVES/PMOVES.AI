"""TEMPORARY reachability probe -- removed in the next commit on this branch.

Purpose: prove that a failing test placed under `pmoves/tests` actually turns a
CI check red. A wiring claim that cannot demonstrate reachable failure is the
same defect class in a new costume.

The check this must turn red is `python-tests` from merge-gate.yml (a required
context on main), NOT `tests (3.11)` from python-tests.yml -- see this branch's
other commit for why those are different jobs.
"""


def test_deliberate_failure_must_reach_ci():
    assert 1 == 2, "PROBE: if CI is green with this file present, pmoves/tests is not reachable"
