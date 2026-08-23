"""Anchors pmoves/tests/config as its own pytest_ratchet group.

Grouping is by nearest-ancestor conftest.py, then chunks of 20. Without this the
directory joins the shared pmoves/tests pool, where chunk [1] exceeds the group
timeout — results there are recovered per-file now, but a gate should not depend
on the fallback to be counted at all.
"""
