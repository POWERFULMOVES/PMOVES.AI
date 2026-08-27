"""Anchors pmoves/tests/make as its own pytest_ratchet group.

pytest_ratchet.group_files() groups by nearest-ancestor conftest.py, then chunks
at 20 files. Without this file these tests fall into the shared `pmoves/tests`
pool, where they landed in chunk [1] — the chunk that exceeds the 120s group
timeout on every run and whose results are therefore discarded entirely (it is
recorded as a known no-report group in configs/pytest_ratchet/_known_failures.yaml).

A gate whose own results CI throws away is not a gate. Anchoring here keeps this
directory a small group that always completes and always counts. Keep it well
under the 20-file chunk boundary; these are static Makefile scans, so the whole
group runs in well under a second.
"""
