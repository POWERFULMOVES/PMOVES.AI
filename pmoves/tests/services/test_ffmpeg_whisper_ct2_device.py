"""CTranslate2 device selection must not follow torch's CUDA availability.

They are separate runtimes. Only CTranslate2's x86_64 manylinux wheel is built
with CUDA (it bundles libcudnn); the aarch64 wheel bundles no CUDA library and
carries the literal "not compiled with CUDA support" error instead. Installing a
CUDA-enabled torch on arm64 therefore does nothing for transcription, because
transcription is not torch:

    whisperx/asr.py:  class WhisperModel(faster_whisper.WhisperModel)
    whisperx/asr.py:  load_model(...) -> WhisperModel(whisper_arch, device=device, ...)

so `provider=whisper` runs its ASR on CTranslate2 exactly as
`provider=faster-whisper` does. Passing device="cuda" into a CUDA-less build
raises at model load and surfaces as a 500 on the first transcription.

These tests pin that ASR degrades to CPU on such a build while the torch stages
(whisperx alignment, diarization) keep the GPU — the split that makes the arm64
torch-cu128 preinstall worth having.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def srv(monkeypatch):
    """Load the ffmpeg-whisper module, skipping if its heavy deps are absent."""
    import importlib.util
    import sys
    from pathlib import Path
    from types import ModuleType

    pmoves = Path(__file__).resolve().parents[2]
    path = pmoves / "services" / "ffmpeg-whisper" / "server.py"
    if not path.exists():
        pytest.skip("ffmpeg-whisper/server.py not found")

    # `services.common.supabase` does `from supabase import create_client`, and
    # putting pmoves/ on the path so `services.*` resolves also puts the
    # pmoves/supabase/ DATA directory there, which shadows the real package as an
    # empty namespace. Stub it — same approach as conftest.stub_external_modules.
    if "supabase" not in sys.modules or not hasattr(
        sys.modules["supabase"], "create_client"
    ):
        stub = ModuleType("supabase")
        stub.Client = object  # type: ignore[attr-defined]
        stub.create_client = lambda *a, **kw: None  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "supabase", stub)

    # server.py:72-73 reads NATS_URL at IMPORT time and raises KeyError (not
    # ImportError) when it is unset, so the skip-guard below cannot catch it and
    # every test errors during setup. CI runs with no NATS_URL, and the service is
    # right to fail closed there rather than silently publish nowhere -- so the
    # fixture supplies one instead of the service relaxing. Import-time only:
    # nothing in these tests opens a connection, hence the .invalid host.
    monkeypatch.setenv("NATS_URL", "nats://nats.invalid:4222")

    monkeypatch.syspath_prepend(str(pmoves))
    spec = importlib.util.spec_from_file_location("ffmpeg_whisper_server", path)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "ffmpeg_whisper_server", mod)
    try:
        spec.loader.exec_module(mod)
    except ImportError as exc:  # fastapi / requests / etc. absent
        pytest.skip(f"cannot import ffmpeg-whisper deps: {exc}")
    return mod


def _cuda_host(srv, monkeypatch):
    """A host where torch DOES see CUDA — the arm64 GB10 case after the preinstall."""
    monkeypatch.delenv("WHISPER_DEVICE", raising=False)
    monkeypatch.delenv("WHISPER_COMPUTE_TYPE", raising=False)
    monkeypatch.setattr(srv, "_detect_cuda_available", lambda: True)
    assert srv._select_device() == "cuda"


def _ct2_cuda(srv, monkeypatch, available: bool):
    # After the first call the attribute is already a plain lambda, not the
    # lru_cache-wrapped original, so clearing is conditional.
    clear = getattr(srv._ctranslate2_cuda_available, "cache_clear", None)
    if clear:
        clear()
    monkeypatch.setattr(srv, "_ctranslate2_cuda_available", lambda: available)


def test_asr_falls_back_to_cpu_when_ctranslate2_has_no_cuda(srv, monkeypatch):
    _cuda_host(srv, monkeypatch)
    _ct2_cuda(srv, monkeypatch, False)
    assert srv._select_ctranslate2_device() == "cpu", (
        "asked a CUDA-less CTranslate2 build for device=cuda — this raises "
        '"CTranslate2 package was not compiled with CUDA support" at model load'
    )


def test_torch_stages_keep_the_gpu(srv, monkeypatch):
    """The whole point of the arm64 torch-cu128 preinstall."""
    _cuda_host(srv, monkeypatch)
    _ct2_cuda(srv, monkeypatch, False)
    assert srv._select_device() == "cuda"


def test_asr_uses_cuda_when_ctranslate2_actually_has_it(srv, monkeypatch):
    """x86_64: the wheel bundles CUDA, so nothing is downgraded."""
    _cuda_host(srv, monkeypatch)
    _ct2_cuda(srv, monkeypatch, True)
    assert srv._select_ctranslate2_device() == "cuda"


def test_compute_type_follows_the_asr_device(srv, monkeypatch):
    """int8 on CPU, float16 on CUDA — a float16 request on CPU is its own failure."""
    _cuda_host(srv, monkeypatch)
    _ct2_cuda(srv, monkeypatch, False)
    assert srv._compute_type(srv._select_ctranslate2_device()) == "int8"
    _ct2_cuda(srv, monkeypatch, True)
    assert srv._compute_type(srv._select_ctranslate2_device()) == "float16"


def test_cpu_host_is_unchanged(srv, monkeypatch):
    monkeypatch.delenv("WHISPER_DEVICE", raising=False)
    monkeypatch.setattr(srv, "_detect_cuda_available", lambda: False)
    _ct2_cuda(srv, monkeypatch, False)
    assert srv._select_ctranslate2_device() == "cpu"


def test_probe_reports_false_when_ctranslate2_is_absent(srv, monkeypatch):
    """The real probe, not a stub: an unimportable/CUDA-less build must not claim CUDA."""
    import builtins

    srv._ctranslate2_cuda_available.cache_clear()
    real_import = builtins.__import__

    def _no_ct2(name, *a, **kw):
        if name == "ctranslate2":
            raise ImportError("no ctranslate2")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _no_ct2)
    try:
        assert srv._ctranslate2_cuda_available() is False
    finally:
        srv._ctranslate2_cuda_available.cache_clear()
