"""Anchors `pmoves/tests/ci` as its own group for `pmoves/tools/pytest_ratchet.py`.

The ratchet groups by nearest-ancestor `conftest.py` and then chunks each group
into CHUNK_SIZE files that share one pytest process. Without this file these
CI-wiring tests join the 88-file `pmoves/tests` group, so adding or removing one
of them shifts every later file across chunk boundaries — changing which modules
share a process with which.

That is not hypothetical. Adding `test_ghcr_runtime_gate.py` moved
`test_mcp_server_chit_signing.py` from position 2 to 3 of chunk [5], pulling
`test_mcp_config_generator.py` in ahead of it, and the ratchet reported three new
failures (`ModuleNotFoundError: No module named 'mcp'`) in a file this branch
never touched.

The root cause is elsewhere and is NOT fixed by this file: there are two distinct
`mcp_server` modules — `pmoves/tools/mcp_server.py` (imports `mcp` at module
scope) and `pmoves/services/agent-zero/mcp_server.py`. `test_mcp_server_chit_signing`
does a bare `import mcp_server` after a `sys.path.insert`, so whichever module
already occupies `sys.modules["mcp_server"]` wins. Making that import
unambiguous is the real fix and belongs to that test's owner.

Parent fixtures still apply — pytest loads conftests up the tree, so this does
not detach these tests from `pmoves/tests/conftest.py`.
"""
