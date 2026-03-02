import asyncio
import importlib.util
import sys
import types
from pathlib import Path


if "librosa" not in sys.modules:
    sys.modules["librosa"] = types.ModuleType("librosa")

if "redis" not in sys.modules:
    redis_stub = types.ModuleType("redis")

    class _Redis:  # pragma: no cover - stub only
        def __init__(self, *args, **kwargs):
            pass

    redis_stub.Redis = _Redis
    sys.modules["redis"] = redis_stub

if "neo4j" not in sys.modules:
    neo4j_stub = types.ModuleType("neo4j")

    class _GraphDatabase:  # pragma: no cover - stub only
        @staticmethod
        def driver(*args, **kwargs):
            return None

    neo4j_stub.GraphDatabase = _GraphDatabase
    sys.modules["neo4j"] = neo4j_stub

if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")

    class _Client:  # pragma: no cover - stub only
        pass

    def _create_client(*args, **kwargs):  # pragma: no cover - stub only
        return _Client()

    supabase_stub.Client = _Client
    supabase_stub.create_client = _create_client
    sys.modules["supabase"] = supabase_stub


MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("audio_processor_main", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _new_processor(provider: str, allow_cross_fallback: bool = True):
    processor = MODULE.MediaProcessor(skip_external_clients=True)
    processor.audio_provider = provider
    processor.allow_cross_fallback = allow_cross_fallback
    return processor


def test_auto_falls_back_from_ollama_to_huggingface():
    processor = _new_processor("auto")
    calls = []

    async def ollama_fail(_audio_path):
        calls.append("ollama")
        raise MODULE.AIProviderError("ollama unavailable")

    async def huggingface_ok(_audio_path):
        calls.append("huggingface")
        return {"provider": "huggingface", "description": "ok", "analysis": {"text": "ok"}}

    processor._analyze_with_ollama = ollama_fail
    processor._analyze_with_huggingface = huggingface_ok

    result = asyncio.run(processor.analyze_audio_with_ai("song.wav"))
    assert result["provider"] == "huggingface"
    assert calls == ["ollama", "huggingface"]


def test_ollama_only_without_cross_fallback():
    processor = _new_processor("ollama", allow_cross_fallback=False)
    calls = []

    async def ollama_fail(_audio_path):
        calls.append("ollama")
        raise MODULE.AIProviderError("ollama unavailable")

    async def huggingface_ok(_audio_path):
        calls.append("huggingface")
        return {"provider": "huggingface", "description": "ok", "analysis": {"text": "ok"}}

    processor._analyze_with_ollama = ollama_fail
    processor._analyze_with_huggingface = huggingface_ok

    result = asyncio.run(processor.analyze_audio_with_ai("song.wav"))
    assert result["provider"] == "none"
    assert calls == ["ollama"]


def test_ollama_with_cross_fallback_enabled():
    processor = _new_processor("ollama", allow_cross_fallback=True)
    calls = []

    async def ollama_fail(_audio_path):
        calls.append("ollama")
        raise MODULE.AIProviderError("ollama unavailable")

    async def huggingface_ok(_audio_path):
        calls.append("huggingface")
        return {"provider": "huggingface", "description": "ok", "analysis": {"text": "ok"}}

    processor._analyze_with_ollama = ollama_fail
    processor._analyze_with_huggingface = huggingface_ok

    result = asyncio.run(processor.analyze_audio_with_ai("song.wav"))
    assert result["provider"] == "huggingface"
    assert calls == ["ollama", "huggingface"]


def test_huggingface_with_cross_fallback_to_ollama():
    processor = _new_processor("huggingface", allow_cross_fallback=True)
    calls = []

    async def huggingface_fail(_audio_path):
        calls.append("huggingface")
        raise MODULE.AIProviderError("hf unavailable")

    async def ollama_ok(_audio_path):
        calls.append("ollama")
        return {"provider": "ollama", "description": "ok", "analysis": {"text": "ok"}}

    processor._analyze_with_huggingface = huggingface_fail
    processor._analyze_with_ollama = ollama_ok

    result = asyncio.run(processor.analyze_audio_with_ai("song.wav"))
    assert result["provider"] == "ollama"
    assert calls == ["huggingface", "ollama"]
