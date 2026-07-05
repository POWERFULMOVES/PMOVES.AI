import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_ui: live ComfyUI + browser; skipped in CI")
