import importlib
import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[4]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.hrm_sidecar import (
    AsciiCodec,
    HrmDecoderController,
    HrmSidecarConfig,
    create_identity_sidecar,
    is_torch_available,
)


@pytest.mark.skipif(not is_torch_available(), reason="torch not available")
def test_identity_sidecar_infer_roundtrip():
    import torch

    config = HrmSidecarConfig(vocab_size=16, mmax=3, mmin=1, halt_threshold=0.8)
    sidecar = create_identity_sidecar(config)
    tokens = torch.tensor([[1, 2, 3, 4, 5]], dtype=torch.long)
    preds, steps = sidecar.infer(tokens, threshold=config.halt_threshold)
    assert preds.shape == tokens.shape
    assert torch.equal(preds.cpu(), tokens)
    assert int(steps[0].item()) <= config.mmax


@pytest.mark.skipif(not is_torch_available(), reason="torch not available")
def test_identity_sidecar_training_step_backward():
    import torch

    config = HrmSidecarConfig(vocab_size=8, mmax=2, mmin=1, halt_threshold=0.6)
    sidecar = create_identity_sidecar(config)
    sidecar.train()
    x = torch.randint(0, config.vocab_size, (2, 4), dtype=torch.long)
    y = x.clone()
    sidecar.zero_grad()
    loss = sidecar.training_step(x, y)
    assert loss.requires_grad
    loss.backward()
    grads = [p.grad for p in sidecar.parameters() if p.requires_grad]
    assert any(g is not None for g in grads)


@pytest.mark.skipif(not is_torch_available(), reason="torch not available")
def test_hrm_decoder_controller_status_and_apply():
    codec = AsciiCodec(vocab_size=128)
    stored = {
        "id": "pack-1",
        "params": {"hrm_halt_thresh": 0.7, "hrm_mmax": 3, "hrm_mmin": 1},
    }

    def fake_fetch(namespace: str, modality: str):
        return stored

    controller = HrmDecoderController(fake_fetch, codec=codec)
    text = "hello"
    summary, info = controller.maybe_refine(text, namespace="pmoves")
    assert summary == text
    assert info["enabled"] is True
    assert info["mmax"] == 3
    assert info["steps"] <= 3

    # When the pack disappears we should gracefully disable
    def missing_pack(namespace: str, modality: str):
        return None

    controller = HrmDecoderController(missing_pack, codec=codec)
    _, info_disabled = controller.maybe_refine(text, namespace="pmoves")
    assert info_disabled["enabled"] is False
    assert "decoder pack" in info_disabled["reason"]
