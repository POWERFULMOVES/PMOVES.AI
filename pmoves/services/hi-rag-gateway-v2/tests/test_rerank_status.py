import contextlib
import functools
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture()
def gateway_module():
    spec = importlib.util.spec_from_file_location(
        "gateway_rerank_fixture",
        Path(__file__).resolve().parent / "test_swarm_meta.py",
    )
    assert spec and spec.loader
    helper_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper_module)
    fixture_func = helper_module.gateway_v2_module.__wrapped__

    class _TensorStub:
        def __init__(self, value=None):  # pragma: no cover - stub only
            self.value = value

        def __call__(self, *args, **kwargs):  # pragma: no cover - stub only
            return _TensorStub(self.value)

        def clone(self):  # pragma: no cover - stub only
            return _TensorStub(self.value)

        def to(self, *args, **kwargs):  # pragma: no cover - stub only
            return self

        def detach(self):  # pragma: no cover - stub only
            return self

        def mean(self, *args, **kwargs):  # pragma: no cover - stub only
            return _TensorStub(self.value)

        def squeeze(self, *args, **kwargs):  # pragma: no cover - stub only
            return self

        def expand(self, *args, **kwargs):  # pragma: no cover - stub only
            return self

        def view(self, *args, **kwargs):  # pragma: no cover - stub only
            return self

        def all(self):  # pragma: no cover - stub only
            return False

        def any(self):  # pragma: no cover - stub only
            return bool(self.value)

        def argmax(self, *args, **kwargs):  # pragma: no cover - stub only
            return self

        def __and__(self, other):  # pragma: no cover - stub only
            return self

        def __or__(self, other):  # pragma: no cover - stub only
            return self

        def __invert__(self):  # pragma: no cover - stub only
            return self

        def __getitem__(self, key):  # pragma: no cover - stub only
            return self

        def __setitem__(self, key, value):  # pragma: no cover - stub only
            self.value = value

        def __iter__(self):  # pragma: no cover - stub only
            return iter([])

        def size(self, *args, **kwargs):  # pragma: no cover - stub only
            return (1,)

        def copy_(self, other):  # pragma: no cover - stub only
            self.value = getattr(other, "value", other)
            return self

        def zero_(self):  # pragma: no cover - stub only
            self.value = 0
            return self

        def float(self):  # pragma: no cover - stub only
            return self

        def long(self):  # pragma: no cover - stub only
            return self

        def bool(self):  # pragma: no cover - stub only
            return self

        def __add__(self, other):  # pragma: no cover - stub only
            return self

        def __radd__(self, other):  # pragma: no cover - stub only
            return self

        def __mul__(self, other):  # pragma: no cover - stub only
            return self

        def __rmul__(self, other):  # pragma: no cover - stub only
            return self

        def __repr__(self):  # pragma: no cover - stub only
            return f"_TensorStub({self.value!r})"

    class _DummyModule:
        def __init__(self, *args, **kwargs):  # pragma: no cover - stub only
            self.args = args
            self.kwargs = kwargs

        def __call__(self, *args, **kwargs):  # pragma: no cover - stub only
            return _TensorStub()

        def __getattr__(self, name):  # pragma: no cover - stub only
            if name in {"weight", "bias", "ln"}:
                return _TensorStub()
            return _DummyModule()

        def register_buffer(self, *args, **kwargs):  # pragma: no cover - stub only
            return None

        def to(self, *args, **kwargs):  # pragma: no cover - stub only
            return self

        def eval(self):  # pragma: no cover - stub only
            return self

    nn_stub = types.ModuleType("torch.nn")
    nn_stub.__path__ = []  # pragma: no cover - package marker
    nn_stub.Module = _DummyModule
    nn_stub.Embedding = _DummyModule
    nn_stub.TransformerEncoderLayer = _DummyModule
    nn_stub.TransformerEncoder = _DummyModule
    nn_stub.Sequential = _DummyModule
    nn_stub.Identity = _DummyModule
    nn_stub.Parameter = lambda *args, **kwargs: _TensorStub()
    nn_stub.LayerNorm = _DummyModule
    nn_stub.Linear = _DummyModule

    class _NoGrad(contextlib.ContextDecorator):  # pragma: no cover - stub only
        def __enter__(self):  # pragma: no cover - stub only
            return None

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - stub only
            return False

        def __call__(self, func):  # pragma: no cover - stub only
            @functools.wraps(func)
            def _wrapped(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)

            return _wrapped

    def _no_grad(func=None):  # pragma: no cover - stub only
        decorator = _NoGrad()
        if func is None:
            return decorator
        return decorator(func)

    def _tensor_from(*args, **kwargs):  # pragma: no cover - stub only
        return _TensorStub(kwargs.get("value") if "value" in kwargs else None)

    torch_stub = types.ModuleType("torch")
    torch_stub.__path__ = []  # pragma: no cover - package marker
    torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False, current_device=lambda: 0)
    torch_stub.nn = nn_stub
    torch_stub.Tensor = _TensorStub
    torch_stub.tensor = lambda *args, **kwargs: _TensorStub(args[0] if args else kwargs.get("value"))
    torch_stub.randn = lambda *args, **kwargs: _TensorStub(0.0)
    torch_stub.zeros = lambda *args, **kwargs: _TensorStub(0.0)
    torch_stub.zeros_like = lambda *args, **kwargs: _TensorStub(0.0)
    torch_stub.ones = lambda *args, **kwargs: _TensorStub(1.0)
    torch_stub.eye = lambda *args, **kwargs: _TensorStub()
    torch_stub.arange = lambda *args, **kwargs: _TensorStub()
    torch_stub.stack = lambda *args, **kwargs: _TensorStub()
    torch_stub.cat = lambda *args, **kwargs: _TensorStub()
    torch_stub.matmul = lambda *args, **kwargs: _TensorStub()
    torch_stub.mm = lambda *args, **kwargs: _TensorStub()
    torch_stub.topk = lambda *args, **kwargs: (_TensorStub(), _TensorStub())
    torch_stub.sigmoid = lambda x: _TensorStub(0.0)
    torch_stub.manual_seed = lambda *args, **kwargs: None
    torch_stub.set_grad_enabled = lambda *args, **kwargs: None
    torch_stub.bool = "bool"
    torch_stub.long = "long"
    torch_stub.float32 = 0.0
    torch_stub.device = lambda *args, **kwargs: "cpu"
    torch_stub.is_tensor = lambda obj: isinstance(obj, _TensorStub)
    torch_stub.clone = lambda *args, **kwargs: _TensorStub()
    torch_stub.no_grad = _no_grad

    functional_stub = types.ModuleType("torch.nn.functional")
    functional_stub.cross_entropy = lambda *args, **kwargs: _TensorStub(0.0)
    functional_stub.binary_cross_entropy_with_logits = lambda *args, **kwargs: _TensorStub(0.0)
    functional_stub.softmax = lambda *args, **kwargs: _TensorStub(0.0)
    functional_stub.relu = lambda *args, **kwargs: _TensorStub(0.0)
    functional_stub.gelu = lambda *args, **kwargs: _TensorStub(0.0)
    functional_stub.normalize = lambda *args, **kwargs: _TensorStub(0.0)

    previous_torch = sys.modules.get("torch")
    previous_torch_nn = sys.modules.get("torch.nn")
    previous_torch_nf = sys.modules.get("torch.nn.functional")
    sys.modules["torch"] = torch_stub
    sys.modules["torch.nn"] = nn_stub
    sys.modules["torch.nn.functional"] = functional_stub
    gen = fixture_func()
    module = next(gen)

    try:
        yield module
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
        if previous_torch is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = previous_torch
        if previous_torch_nn is None:
            sys.modules.pop("torch.nn", None)
        else:
            sys.modules["torch.nn"] = previous_torch_nn
        if previous_torch_nf is None:
            sys.modules.pop("torch.nn.functional", None)
        else:
            sys.modules["torch.nn.functional"] = previous_torch_nf


def _reload_with_env(monkeypatch, module, **env):
    keys = {
        "RERANK_ENABLE",
        "RERANK_MODEL",
        "RERANK_MODEL_LABEL",
        "RERANK_TOPN",
        "RERANK_K",
        "RERANK_FUSION",
        "RERANK_PROVIDER",
    }
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    module_name = module.__name__
    module_path = Path(module.__file__)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec and spec.loader
    fresh_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = fresh_module
    spec.loader.exec_module(fresh_module)
    return fresh_module


def test_rerank_status_defaults(monkeypatch, gateway_module):
    module = _reload_with_env(monkeypatch, gateway_module)
    status = module.get_rerank_status()
    assert status["enabled"] is True
    assert status["provider"] == "flag"
    assert status["fusion"] == "mul"
    assert status["errors"] == []
    assert status["warnings"] == []


def test_rerank_status_reports_invalid_values(monkeypatch, gateway_module):
    module = _reload_with_env(
        monkeypatch,
        gateway_module,
        RERANK_TOPN="4",
        RERANK_K="not-a-number",
        RERANK_PROVIDER="unknown",
        RERANK_FUSION="bogus",
    )
    status = module.get_rerank_status()
    assert status["topn"] == 4
    # Fallback default of 10 should be truncated to topn=4 when invalid input provided.
    assert status["k"] == 4
    assert any("RERANK_K" in msg for msg in status["errors"])
    assert any("RERANK_PROVIDER" in msg for msg in status["warnings"])
    assert status["provider"] == "flag"
    assert status["fusion"] == "mul"


def test_admin_rerank_status_applies_label(monkeypatch, gateway_module):
    monkeypatch.setenv("SMOKE_ALLOW_ADMIN_STATS", "true")
    module = _reload_with_env(
        monkeypatch,
        gateway_module,
        RERANK_MODEL="BAAI/bge-reranker-base",
        RERANK_MODEL_LABEL="custom-label",
    )
    request = module.Request(client=types.SimpleNamespace(host="127.0.0.1"), headers={})
    payload = module.admin_rerank_status(request)
    assert payload["model_report"] == "custom-label"
    assert payload["model"] == "BAAI/bge-reranker-base"
    assert payload["warnings"] == []
