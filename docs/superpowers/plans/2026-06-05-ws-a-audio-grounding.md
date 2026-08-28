# WS-A — Audio Grounding Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 4-scalar ffmpeg audio analysis with an open, reproducible, CHIT-signed audio-grounding layer (librosa + CLAP embeddings + optional AST) that emits CGP v2 packets so every downstream Hyperdimensions hologram is provably tied to measured audio signal.

**Architecture:** A new stateless `clap-embed` microservice (FastAPI, port **8108**) loads `laion/larger_clap_music` and returns deterministic 512-d audio/text embeddings over HTTP (+ optional NATS). `analyze_beats.py` is upgraded to compute interpretable librosa features and fetch CLAP embeddings, cluster on the embeddings (silhouette-validated), and optionally escalate to an open audio-LLM only when clustering is ambiguous. `beats_to_cgp.py` is upgraded to emit **CGP v2** (`chit.cgp.v0.2`) populating the `hyperbolic` (Poincaré), `attribution` (Dirichlet + Merkle), and `sig` (HMAC) extensions, validated against `cgp.v2.schema.json` and signed via the canonical `pmoves.tools.chit_security.sign_cgp`.

**Tech Stack:** Python 3.11/3.12, FastAPI + uvicorn, `transformers`/`torch` (CLAP, AST), `librosa`, `scikit-learn`, `jsonschema`, `prometheus-client`, `nats-py`, `httpx`, `typer`. Reuses `pmoves.tools.chit_security` (HMAC-SHA256 CGP signing) and `pmoves-model-registry` (8110).

**Spec:** `docs/superpowers/specs/2026-06-03-ws-a-audio-grounding-design.md`. **Program context:** `research/HYPERDIMENSIONS_UTILIZATION_PLAN.md`.

**Pre-flight (do once before Phase 1):**
- Port: `clap-embed` = **8108** (spec said 8112; corrected — 8112/8113/8114 are bound to GitHub-automation services. Verified free: 8107/8108/8109/8115/8116; 8108 chosen, in the AI/CHIT tier next to Consciousness 8106).
- All models pinned by revision and Apache/MIT/BSD/ISC only. CLAP `laion/larger_clap_music` (Apache-2.0), AST `MIT/ast-finetuned-audioset-10-10-0.4593` (BSD-3-Clause). Semantic tier (Qwen2-Audio / Step-Audio-2-mini) is **registry-driven, not hardcoded** and out of the deterministic hot path.

---

## File Structure

**New files:**
- `pmoves/services/clap-embed/__init__.py` — package marker.
- `pmoves/services/clap-embed/app.py` — FastAPI app factory + routes (`/healthz`, `/embed/audio`, `/embed/text`, `/metrics`).
- `pmoves/services/clap-embed/embedder.py` — deterministic CLAP load + windowed embed (the only ML code; pure, testable with a fake model).
- `pmoves/services/clap-embed/nats_responder.py` — optional NATS request/reply bridge.
- `pmoves/services/clap-embed/config.py` — env-driven config (model id/rev, clip length/hop, port, NATS).
- `pmoves/services/clap-embed/requirements.txt`, `Dockerfile`, `README.md`.
- `pmoves/services/clap-embed/torch.js` — Pinokio multi-arch torch installer (for PBNJ/Pinokio packaging parity).
- `pmoves/services/clap-embed/tests/test_embedder.py`, `tests/test_app.py`, `tests/test_nats_responder.py`.
- `pmoves/tools/hyperbolic_encode.py` — pure Poincaré-disk encoder (shared math; no deps beyond numpy).
- `pmoves/tools/cgp_v2_build.py` — pure CGP v2 builders (hyperbolic block, Dirichlet attribution, Merkle root). No I/O.
- `pmoves/tools/clap_client.py` — thin HTTP client for `clap-embed` with librosa-only fallback flag.
- `pmoves/tools/tests/test_hyperbolic_encode.py`, `tests/test_cgp_v2_build.py`, `tests/test_clap_client.py`, `tests/test_beats_features.py`, `tests/test_beats_to_cgp_v2.py`, `tests/test_reproducibility.py`.

**Modified files:**
- `pmoves/tools/analyze_beats.py` — add librosa feature extraction + CLAP embedding fetch; cluster on embeddings; swap `gaze` semantic backend to registry-driven open audio-LLM.
- `pmoves/tools/beats_to_cgp.py` — emit CGP v2 (hyperbolic/attribution/sig) + schema validation.
- `docs/superpowers/specs/2026-06-03-ws-a-audio-grounding-design.md` — correct port 8112 → 8108.
- `.claude/CATALOG.md` — register `clap-embed :8108`.
- `pmoves/docker-compose.yml` — add `clap-embed` service (CPU profile default).

**Responsibility boundaries:** pure math (`hyperbolic_encode.py`, `cgp_v2_build.py`) is dependency-light and 100% unit-testable without audio or network. ML lives only in `embedder.py` (service) behind an injectable model, so tests use a fake. Network lives only in `clap_client.py` + `app.py`. The two `tools/*.py` CLIs orchestrate; they import the pure modules.

---

## Phase 0 — Shared pure math (no audio, no network)

### Task 1: Poincaré-disk encoder

**Files:**
- Create: `pmoves/tools/hyperbolic_encode.py`
- Test: `pmoves/tools/tests/test_hyperbolic_encode.py`

- [ ] **Step 1: Write the failing test**

```python
# pmoves/tools/tests/test_hyperbolic_encode.py
import math
import numpy as np
import pytest
from pmoves.tools.hyperbolic_encode import poincare_encode, encode_hierarchy


def test_point_inside_unit_disk():
    p = poincare_encode(angle=0.0, depth=3, max_radius=0.95)
    assert p["x"] ** 2 + p["y"] ** 2 < 1.0
    assert 0.0 <= p["r"] <= 0.95
    assert 0.0 <= p["theta"] < 2 * math.pi


def test_root_is_near_center():
    root = poincare_encode(angle=1.2, depth=0, max_radius=0.95)
    assert root["r"] < 0.5  # depth 0 sits near origin


def test_deeper_is_farther_out():
    shallow = poincare_encode(angle=1.2, depth=1, max_radius=0.95)
    deep = poincare_encode(angle=1.2, depth=4, max_radius=0.95)
    assert deep["r"] > shallow["r"]
    assert deep["r"] < 0.95


def test_angle_from_vector_is_deterministic():
    a = poincare_encode(angle=None, vector=np.array([1.0, 0.0]), depth=2)
    b = poincare_encode(angle=None, vector=np.array([1.0, 0.0]), depth=2)
    assert a == b
    assert a["theta"] == pytest.approx(0.0, abs=1e-9)


def test_encode_hierarchy_links_parents():
    groups = {"g0": np.array([1.0, 0.0]), "g1": np.array([0.0, 1.0])}
    members = {"g0": {"t0": np.array([1.0, 0.1]), "t1": np.array([0.9, -0.1])},
               "g1": {"t2": np.array([0.0, 1.0])}}
    pts = encode_hierarchy(groups, members, max_radius=0.95)
    by_id = {p["id"]: p for p in pts}
    assert by_id["g0"]["depth"] == 1 and "parent_id" not in by_id["g0"]
    assert by_id["t0"]["parent_id"] == "g0" and by_id["t0"]["depth"] == 2
    assert all(p["x"] ** 2 + p["y"] ** 2 < 1.0 for p in pts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_hyperbolic_encode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pmoves.tools.hyperbolic_encode'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/tools/hyperbolic_encode.py
"""Pure Poincaré-disk encoder for CGP v2 hyperbolic blocks.

Maps a hierarchy (group -> track) into the Poincaré disk: depth controls
Euclidean radius (root near centre, leaves toward the boundary but always
|z| < max_radius < 1), angle comes from a 2-D direction so semantically
similar items sit in similar directions. No external services; numpy only.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

import numpy as np


def _radius_for_depth(depth: int, max_radius: float) -> float:
    # Geometric saturation toward the boundary: depth 0 -> 0, depth->inf -> max_radius.
    # r(d) = max_radius * (1 - 0.5 ** d)
    return round(max_radius * (1.0 - 0.5 ** depth), 6)


def _angle_from_vector(vector: np.ndarray) -> float:
    if vector.shape[0] < 2:
        vector = np.concatenate([vector, np.zeros(2 - vector.shape[0])])
    theta = math.atan2(float(vector[1]), float(vector[0]))
    if theta < 0:
        theta += 2 * math.pi
    return theta


def poincare_encode(
    angle: Optional[float] = None,
    *,
    vector: Optional[np.ndarray] = None,
    depth: int = 0,
    max_radius: float = 0.95,
) -> Dict[str, float]:
    if angle is None:
        if vector is None:
            raise ValueError("poincare_encode requires either angle or vector")
        angle = _angle_from_vector(np.asarray(vector, dtype=float))
    theta = float(angle) % (2 * math.pi)
    r = _radius_for_depth(int(depth), max_radius)
    return {
        "x": round(r * math.cos(theta), 6),
        "y": round(r * math.sin(theta), 6),
        "r": r,
        "theta": round(theta, 6),
        "depth": int(depth),
    }


def encode_hierarchy(
    groups: Mapping[str, np.ndarray],
    members: Mapping[str, Mapping[str, np.ndarray]],
    *,
    max_radius: float = 0.95,
) -> list[Dict[str, Any]]:
    """Return a flat list of poincare_point dicts (groups depth=1, tracks depth=2)."""
    points: list[Dict[str, Any]] = []
    for gid in sorted(groups):
        gp = poincare_encode(vector=np.asarray(groups[gid], dtype=float), depth=1, max_radius=max_radius)
        gp["id"] = gid
        points.append(gp)
        for tid in sorted(members.get(gid, {})):
            tp = poincare_encode(vector=np.asarray(members[gid][tid], dtype=float), depth=2, max_radius=max_radius)
            tp["id"] = tid
            tp["parent_id"] = gid
            points.append(tp)
    return points
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_hyperbolic_encode.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/hyperbolic_encode.py pmoves/tools/tests/test_hyperbolic_encode.py
git commit -m "feat(ws-a): add pure Poincaré-disk encoder for CGP v2 hyperbolic block"
```

---

### Task 2: CGP v2 builders (Dirichlet attribution + Merkle root)

**Files:**
- Create: `pmoves/tools/cgp_v2_build.py`
- Test: `pmoves/tools/tests/test_cgp_v2_build.py`

- [ ] **Step 1: Write the failing test**

```python
# pmoves/tools/tests/test_cgp_v2_build.py
import re
import numpy as np
from pmoves.tools.cgp_v2_build import (
    build_attribution, build_hyperbolic_block, merkle_root,
)

HEX64 = re.compile(r"^0x[a-fA-F0-9]{64}$")


def test_merkle_root_shape_and_determinism():
    leaves = ["track_a", "track_b", "track_c"]
    r1 = merkle_root(leaves)
    r2 = merkle_root(leaves)
    assert HEX64.match(r1) and r1 == r2


def test_merkle_root_order_independent_is_false():
    # order matters (leaves are pre-sorted by caller); different order -> different root
    assert merkle_root(["a", "b"]) != merkle_root(["b", "a"])


def test_build_attribution_weights_sum_to_one():
    attr = build_attribution({"t0": 3.0, "t1": 1.0})
    weights = [c["weight"] for c in attr["contributors"]]
    assert abs(sum(weights) - 1.0) < 1e-9
    assert attr["total_alpha"] == 4.0
    assert HEX64.match(attr["merkle_root"])
    # t0 had 3x the raw contribution -> 0.75 weight
    by_addr = {c["address"]: c for c in attr["contributors"]}
    assert abs(by_addr["t0"]["weight"] - 0.75) < 1e-9


def test_build_attribution_handles_zero_total():
    attr = build_attribution({"t0": 0.0, "t1": 0.0})
    # uniform fallback when all alpha are zero
    weights = sorted(c["weight"] for c in attr["contributors"])
    assert weights == [0.5, 0.5]


def test_build_hyperbolic_block_shape():
    groups = {"g0": np.array([1.0, 0.0])}
    members = {"g0": {"t0": np.array([1.0, 0.1])}}
    block = build_hyperbolic_block(groups, members)
    assert block["space"] == "poincare_disk"
    assert block["curvature"] == -1
    assert block["max_radius"] == 0.95
    assert block["hierarchy_depth"] == 2
    assert all(p["x"] ** 2 + p["y"] ** 2 < 1.0 for p in block["points"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_cgp_v2_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pmoves.tools.cgp_v2_build'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/tools/cgp_v2_build.py
"""Pure builders for CGP v2 extension blocks: hyperbolic, attribution, Merkle.

No I/O, no network. Consumed by beats_to_cgp.py. Outputs validate against
pmoves/contracts/schemas/geometry/cgp.v2.schema.json.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping

import numpy as np

from pmoves.tools.hyperbolic_encode import encode_hierarchy


def _sha256_hex(data: bytes) -> str:
    return "0x" + hashlib.sha256(data).hexdigest()


def merkle_root(leaves: List[str]) -> str:
    """Binary Merkle root over leaf strings. Stable for a given ordered list.

    Empty -> sha256(b"") sentinel. Odd levels duplicate the last node.
    """
    if not leaves:
        return _sha256_hex(b"")
    level = [_sha256_hex(leaf.encode("utf-8")) for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            _sha256_hex((level[i] + level[i + 1]).encode("utf-8"))
            for i in range(0, len(level), 2)
        ]
    return level[0]


def build_attribution(raw_contributions: Mapping[str, float]) -> Dict[str, Any]:
    """Dirichlet attribution: alpha_i = max(raw_i, 0); weight_i = alpha_i / sum.

    All-zero -> uniform weights. merkle_root over sorted contributor addresses.
    """
    addrs = sorted(raw_contributions)
    alphas = [max(float(raw_contributions[a]), 0.0) for a in addrs]
    total = float(sum(alphas))
    n = len(addrs)
    if total <= 0.0:
        weights = [1.0 / n] * n if n else []
    else:
        weights = [a / total for a in alphas]
    contributors = [
        {
            "address": addr,
            "weight": round(w, 9),
            "raw_contribution": round(float(raw_contributions[addr]), 9),
            "alpha_component": round(a, 9),
        }
        for addr, a, w in zip(addrs, alphas, weights)
    ]
    return {
        "dirichlet_alpha": [round(a, 9) for a in alphas],
        "total_alpha": round(total, 9),
        "contributors": contributors,
        "merkle_root": merkle_root(addrs),
    }


def build_hyperbolic_block(
    groups: Mapping[str, np.ndarray],
    members: Mapping[str, Mapping[str, np.ndarray]],
    *,
    max_radius: float = 0.95,
) -> Dict[str, Any]:
    points = encode_hierarchy(groups, members, max_radius=max_radius)
    depth = max((p["depth"] for p in points), default=0)
    return {
        "space": "poincare_disk",
        "curvature": -1,
        "max_radius": max_radius,
        "points": points,
        "hierarchy_depth": depth,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_cgp_v2_build.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/cgp_v2_build.py pmoves/tools/tests/test_cgp_v2_build.py
git commit -m "feat(ws-a): add pure CGP v2 builders (Dirichlet attribution + Merkle root + hyperbolic block)"
```

---

## Phase 1 — clap-embed microservice

### Task 3: Deterministic embedder (injectable model)

**Files:**
- Create: `pmoves/services/clap-embed/__init__.py` (empty)
- Create: `pmoves/services/clap-embed/config.py`
- Create: `pmoves/services/clap-embed/embedder.py`
- Test: `pmoves/services/clap-embed/tests/test_embedder.py`

- [ ] **Step 1: Write the failing test** (uses a fake model — no torch/transformers download)

```python
# pmoves/services/clap-embed/tests/test_embedder.py
import numpy as np
import pytest
from embedder import Embedder, window_audio


def test_window_audio_fixed_nonoverlapping():
    sr = 48000
    audio = np.ones(sr * 25, dtype="float32")  # 25 s
    wins = window_audio(audio, sr, clip_seconds=10, hop_seconds=10)
    assert len(wins) == 3                      # 0-10, 10-20, 20-25 (padded)
    assert all(w.shape[0] == sr * 10 for w in wins)


def test_window_audio_short_is_padded_to_one_window():
    sr = 48000
    audio = np.ones(sr * 3, dtype="float32")
    wins = window_audio(audio, sr, clip_seconds=10, hop_seconds=10)
    assert len(wins) == 1 and wins[0].shape[0] == sr * 10


class _FakeModel:
    """Returns a deterministic embedding derived from the window mean."""
    def embed_windows(self, windows):
        return np.stack([np.full(512, float(np.mean(w)), dtype="float32") for w in windows])


def test_embed_is_mean_pooled_and_l2_normalised():
    emb = Embedder(model=_FakeModel(), sr=48000, clip_seconds=10, hop_seconds=10)
    audio = np.ones(48000 * 12, dtype="float32")
    vec = emb.embed_audio(audio, 48000)
    assert len(vec) == 512
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-6)


def test_embed_is_deterministic():
    emb = Embedder(model=_FakeModel(), sr=48000, clip_seconds=10, hop_seconds=10)
    audio = (np.sin(np.linspace(0, 100, 48000 * 11))).astype("float32")
    v1 = emb.embed_audio(audio, 48000)
    v2 = emb.embed_audio(audio, 48000)
    assert v1 == v2  # list equality — bit-identical
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/test_embedder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'embedder'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/services/clap-embed/config.py
import os


class Config:
    MODEL_ID = os.environ.get("CLAP_MODEL_ID", "laion/larger_clap_music")
    MODEL_REVISION = os.environ.get("CLAP_MODEL_REVISION", "main")
    SR = int(os.environ.get("CLAP_SAMPLE_RATE", "48000"))          # CLAP expects 48 kHz
    CLIP_SECONDS = int(os.environ.get("CLAP_CLIP_SECONDS", "10"))  # deterministic window
    HOP_SECONDS = int(os.environ.get("CLAP_HOP_SECONDS", "10"))    # non-overlapping
    PORT = int(os.environ.get("CLAP_EMBED_PORT", "8108"))
    DEVICE = os.environ.get("CLAP_DEVICE", "cpu")                  # cpu|cuda|mps
    NATS_URL = os.environ.get("NATS_URL", "")                      # empty disables NATS
    REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://model-registry:8110")
    EMBED_DIM = 512
```

```python
# pmoves/services/clap-embed/embedder.py
"""Deterministic CLAP embedder. The torch/transformers model is injected so the
pure windowing + pooling logic is testable without any model download."""
from __future__ import annotations

from typing import List, Protocol

import numpy as np


def window_audio(audio: np.ndarray, sr: int, clip_seconds: int, hop_seconds: int) -> List[np.ndarray]:
    """Split mono audio into fixed-length non-overlapping windows (last is zero-padded)."""
    clip = clip_seconds * sr
    hop = hop_seconds * sr
    audio = np.asarray(audio, dtype="float32").reshape(-1)
    if audio.shape[0] <= clip:
        out = np.zeros(clip, dtype="float32")
        out[: audio.shape[0]] = audio
        return [out]
    windows: List[np.ndarray] = []
    for start in range(0, audio.shape[0], hop):
        seg = audio[start : start + clip]
        if seg.shape[0] == 0:
            break
        if seg.shape[0] < clip:
            padded = np.zeros(clip, dtype="float32")
            padded[: seg.shape[0]] = seg
            seg = padded
        windows.append(seg)
    return windows


class _Model(Protocol):
    def embed_windows(self, windows: List[np.ndarray]) -> np.ndarray: ...


class Embedder:
    def __init__(self, model: _Model, sr: int, clip_seconds: int, hop_seconds: int):
        self.model = model
        self.sr = sr
        self.clip_seconds = clip_seconds
        self.hop_seconds = hop_seconds

    def embed_audio(self, audio: np.ndarray, sr: int) -> List[float]:
        if sr != self.sr:
            import librosa
            audio = librosa.resample(np.asarray(audio, dtype="float32"), orig_sr=sr, target_sr=self.sr)
        windows = window_audio(audio, self.sr, self.clip_seconds, self.hop_seconds)
        per_window = self.model.embed_windows(windows)        # (n, 512)
        pooled = per_window.mean(axis=0)                       # mean pool
        norm = float(np.linalg.norm(pooled))
        if norm > 0:
            pooled = pooled / norm
        return [round(float(x), 7) for x in pooled]           # rounded -> bit-stable JSON
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/test_embedder.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/clap-embed/__init__.py pmoves/services/clap-embed/config.py pmoves/services/clap-embed/embedder.py pmoves/services/clap-embed/tests/test_embedder.py
git commit -m "feat(ws-a): clap-embed deterministic windowed embedder (injectable model)"
```

---

### Task 4: Real CLAP model loader (HF transformers)

**Files:**
- Modify: `pmoves/services/clap-embed/embedder.py` (append `ClapHFModel`)
- Test: `pmoves/services/clap-embed/tests/test_embedder.py` (add a guarded integration test)

- [ ] **Step 1: Write the failing test** (skipped unless model present — keeps CI fast/offline)

```python
# append to pmoves/services/clap-embed/tests/test_embedder.py
import os
import pytest


@pytest.mark.skipif(os.environ.get("CLAP_RUN_MODEL_TESTS") != "1",
                    reason="set CLAP_RUN_MODEL_TESTS=1 to download+run the real CLAP model")
def test_clap_hf_model_embeds_512():
    import numpy as np
    from embedder import ClapHFModel
    m = ClapHFModel(model_id="laion/larger_clap_music", revision="main", device="cpu")
    out = m.embed_windows([np.zeros(48000 * 10, dtype="float32")])
    assert out.shape == (1, 512)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/clap-embed && CLAP_RUN_MODEL_TESTS=1 python -m pytest tests/test_embedder.py::test_clap_hf_model_embeds_512 -v`
Expected: FAIL — `ImportError: cannot import name 'ClapHFModel'` (or collection error)

- [ ] **Step 3: Write minimal implementation**

```python
# append to pmoves/services/clap-embed/embedder.py
class ClapHFModel:
    """laion CLAP loaded via transformers. Deterministic: eval(), no grad, fp32."""

    def __init__(self, model_id: str, revision: str = "main", device: str = "cpu"):
        import torch
        from transformers import ClapModel, ClapProcessor

        torch.manual_seed(0)
        self._torch = torch
        self.device = device
        self.processor = ClapProcessor.from_pretrained(model_id, revision=revision)
        self.model = ClapModel.from_pretrained(model_id, revision=revision, torch_dtype=torch.float32)
        self.model.eval().to(device)

    def embed_windows(self, windows):
        import numpy as np
        torch = self._torch
        with torch.no_grad():
            inputs = self.processor(audios=[w for w in windows], sampling_rate=48000, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self.model.get_audio_features(**inputs)   # (n, 512)
            return feats.detach().cpu().float().numpy()

    def embed_text(self, texts):
        import numpy as np
        torch = self._torch
        with torch.no_grad():
            inputs = self.processor(text=list(texts), return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self.model.get_text_features(**inputs)
            return feats.detach().cpu().float().numpy()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/clap-embed && CLAP_RUN_MODEL_TESTS=1 python -m pytest tests/test_embedder.py::test_clap_hf_model_embeds_512 -v`
Expected: PASS (1 passed) — requires `pip install torch transformers librosa`. Without the env var, the test is skipped.

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/clap-embed/embedder.py pmoves/services/clap-embed/tests/test_embedder.py
git commit -m "feat(ws-a): clap-embed HF model loader (laion/larger_clap_music, deterministic)"
```

---

### Task 5: FastAPI app (`/healthz`, `/embed/audio`, `/embed/text`, `/metrics`)

**Files:**
- Create: `pmoves/services/clap-embed/app.py`
- Test: `pmoves/services/clap-embed/tests/test_app.py`

- [ ] **Step 1: Write the failing test** (fake embedder injected via dependency override)

```python
# pmoves/services/clap-embed/tests/test_app.py
import io
import wave
import numpy as np
from fastapi.testclient import TestClient
from app import create_app, get_embedder


class _FakeEmbedder:
    def embed_audio(self, audio, sr):
        return [0.1] * 512
    def embed_text(self, texts):
        return [[0.2] * 512 for _ in texts]


def _wav_bytes(seconds=1, sr=48000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        samples = (np.zeros(sr * seconds) * 32767).astype("<i2")
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def _client():
    app = create_app()
    app.dependency_overrides[get_embedder] = lambda: _FakeEmbedder()
    return TestClient(app)


def test_healthz_ok():
    r = _client().get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["model_id"]


def test_embed_audio_returns_512():
    r = _client().post("/embed/audio", files={"file": ("x.wav", _wav_bytes(), "audio/wav")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["embedding"]) == 512 and body["model_rev"]


def test_embed_text_returns_512():
    r = _client().post("/embed/text", json={"texts": ["dark techno"]})
    assert r.status_code == 200
    assert len(r.json()["embeddings"][0]) == 512


def test_metrics_exposed():
    c = _client()
    c.get("/healthz")
    r = c.get("/metrics")
    assert r.status_code == 200 and b"clap_embed_requests_total" in r.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/services/clap-embed/app.py
"""clap-embed FastAPI service — stateless deterministic CLAP embedder (port 8108)."""
from __future__ import annotations

import io

import librosa
import numpy as np
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from config import Config
from embedder import ClapHFModel, Embedder

REQUESTS = Counter("clap_embed_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram("clap_embed_seconds", "Embed latency seconds", ["endpoint"])

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        model = ClapHFModel(Config.MODEL_ID, Config.MODEL_REVISION, Config.DEVICE)
        _embedder = Embedder(model, Config.SR, Config.CLIP_SECONDS, Config.HOP_SECONDS)
    return _embedder


class TextRequest(BaseModel):
    texts: list[str]


def create_app() -> FastAPI:
    app = FastAPI(title="clap-embed", version="1.0.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "model_id": Config.MODEL_ID, "model_rev": Config.MODEL_REVISION,
                "sr": Config.SR, "clip_seconds": Config.CLIP_SECONDS, "dim": Config.EMBED_DIM}

    @app.post("/embed/audio")
    async def embed_audio(file: UploadFile = File(...), emb: Embedder = Depends(get_embedder)):
        REQUESTS.labels("embed_audio").inc()
        with LATENCY.labels("embed_audio").time():
            raw = await file.read()
            audio, sr = librosa.load(io.BytesIO(raw), sr=None, mono=True)
            vec = emb.embed_audio(np.asarray(audio, dtype="float32"), int(sr))
        return {"embedding": vec, "model_rev": Config.MODEL_REVISION, "sr": Config.SR}

    @app.post("/embed/text")
    def embed_text(req: TextRequest, emb: Embedder = Depends(get_embedder)):
        REQUESTS.labels("embed_text").inc()
        with LATENCY.labels("embed_text").time():
            vecs = emb.model.embed_text(req.texts)
            out = [[round(float(x), 7) for x in row] for row in np.asarray(vecs)]
        return {"embeddings": out, "model_rev": Config.MODEL_REVISION}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/test_app.py -v`
Expected: PASS (4 passed). Requires `pip install fastapi httpx librosa prometheus-client pydantic`.

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/clap-embed/app.py pmoves/services/clap-embed/tests/test_app.py
git commit -m "feat(ws-a): clap-embed FastAPI app (/healthz /embed/audio /embed/text /metrics)"
```

---

### Task 6: Optional NATS responder

**Files:**
- Create: `pmoves/services/clap-embed/nats_responder.py`
- Test: `pmoves/services/clap-embed/tests/test_nats_responder.py`

- [ ] **Step 1: Write the failing test** (pure handler — no live NATS)

```python
# pmoves/services/clap-embed/tests/test_nats_responder.py
import base64, io, json, wave
import numpy as np
from nats_responder import handle_request


class _FakeEmbedder:
    def embed_audio(self, audio, sr):
        return [0.3] * 512


def _wav_b64(sr=48000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.zeros(sr) * 32767).astype("<i2").tobytes())
    return base64.b64encode(buf.getvalue()).decode()


def test_handle_request_returns_embedding_and_context():
    msg = {"context_id": "ctx-1", "audio_b64": _wav_b64()}
    out = json.loads(handle_request(json.dumps(msg).encode(), _FakeEmbedder()))
    assert out["context_id"] == "ctx-1"
    assert len(out["embedding"]) == 512
    assert out["ok"] is True


def test_handle_request_bad_payload_is_flagged_not_raised():
    out = json.loads(handle_request(b"not-json", _FakeEmbedder()))
    assert out["ok"] is False and "error" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/test_nats_responder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nats_responder'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/services/clap-embed/nats_responder.py
"""Optional NATS request/reply bridge for clap-embed.

Subjects: audio.embed.request.v1 -> audio.embed.result.v1.
Enabled only when NATS_URL is set. handle_request is pure (testable)."""
from __future__ import annotations

import base64
import io
import json

import librosa
import numpy as np

from config import Config

SUBJECT_REQUEST = "audio.embed.request.v1"
SUBJECT_RESULT = "audio.embed.result.v1"


def handle_request(data: bytes, embedder) -> bytes:
    try:
        msg = json.loads(data)
        audio_bytes = base64.b64decode(msg["audio_b64"])
        audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)
        vec = embedder.embed_audio(np.asarray(audio, dtype="float32"), int(sr))
        return json.dumps({
            "ok": True,
            "context_id": msg.get("context_id"),
            "embedding": vec,
            "model_rev": Config.MODEL_REVISION,
        }).encode()
    except Exception as exc:  # never crash the responder; flag the failure
        return json.dumps({"ok": False, "error": str(exc)}).encode()


async def run_responder(embedder):  # pragma: no cover - requires live NATS
    import nats
    nc = await nats.connect(Config.NATS_URL)

    async def _cb(m):
        result = handle_request(m.data, embedder)
        reply = m.reply or SUBJECT_RESULT
        await nc.publish(reply, result)

    await nc.subscribe(SUBJECT_REQUEST, cb=_cb)
    return nc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/test_nats_responder.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/clap-embed/nats_responder.py pmoves/services/clap-embed/tests/test_nats_responder.py
git commit -m "feat(ws-a): clap-embed optional NATS responder (audio.embed.request/result.v1)"
```

---

### Task 7: Packaging — requirements, Dockerfile, torch.js, README, registry register

**Files:**
- Create: `pmoves/services/clap-embed/requirements.txt`
- Create: `pmoves/services/clap-embed/Dockerfile`
- Create: `pmoves/services/clap-embed/torch.js`
- Create: `pmoves/services/clap-embed/README.md`
- Modify: `pmoves/services/clap-embed/app.py` (startup model-registry registration)

- [ ] **Step 1: Write requirements.txt**

```text
# pmoves/services/clap-embed/requirements.txt
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
python-multipart>=0.0.9
librosa>=0.10
numpy>=1.26
prometheus-client>=0.20
httpx>=0.27
nats-py>=2.7
transformers>=4.40
torch>=2.2
```

- [ ] **Step 2: Write the Dockerfile** (CPU default; matches jellyfin-bridge non-root pattern)

```dockerfile
# pmoves/services/clap-embed/Dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/.hf
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt ./
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
COPY . .
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    mkdir -p /app/.hf && chown -R pmoves:pmoves /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg && rm -rf /var/lib/apt/lists/*
USER pmoves:pmoves
EXPOSE 8108
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8108/healthz || exit 1
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8108"]
```

- [ ] **Step 3: Write torch.js** (Pinokio multi-arch parity — mirrors `pmoves/docs/ARTSTUFF/realtime/torch.js`)

```javascript
// pmoves/services/clap-embed/torch.js
// Multi-arch torch installer for Pinokio/PBNJ packaging of clap-embed.
module.exports = {
  run: [{
    method: "shell.run",
    params: {
      venv: "env",
      message: [
        "{{platform === 'darwin' ? 'pip install torch librosa transformers' :" +
        " gpu === 'nvidia' ? 'pip install torch --index-url https://download.pytorch.org/whl/cu128 && pip install librosa transformers' :" +
        " gpu === 'amd' ? 'pip install torch --index-url https://download.pytorch.org/whl/rocm6.2 && pip install librosa transformers' :" +
        " 'pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install librosa transformers'}}"
      ]
    }
  }, {
    method: "shell.run",
    params: { venv: "env", message: "python -c \"import torch; print(torch.cuda.get_arch_list()); import librosa, transformers\"" }
  }]
};
```

- [ ] **Step 4: Add startup registry registration to app.py**

```python
# add inside create_app(), before `return app`
    @app.on_event("startup")
    async def _register():
        import httpx
        payload = {
            "service": "clap-embed",
            "model_id": Config.MODEL_ID,
            "revision": Config.MODEL_REVISION,
            "license": "Apache-2.0",
            "provenance": "laion/larger_clap_music",
            "endpoint": f"http://clap-embed:{Config.PORT}",
        }
        try:
            async with httpx.AsyncClient(timeout=4) as c:
                await c.post(f"{Config.REGISTRY_URL}/api/deployments", json=payload)
        except Exception:
            pass  # registry offline is non-fatal; service still serves
```

- [ ] **Step 5: Write README.md**

```markdown
# clap-embed (:8108)

Stateless deterministic CLAP embedder (MOF lattice node). Loads
`laion/larger_clap_music` (Apache-2.0) and returns 512-d audio/text embeddings.

- `GET  /healthz` — model id/rev, sr, clip params, dim.
- `POST /embed/audio` (multipart `file`) → `{embedding:[512], model_rev, sr}`.
- `POST /embed/text` (`{texts:[...]}`) → `{embeddings:[[512],...]}`.
- `GET  /metrics` — Prometheus.
- Optional NATS: `audio.embed.request.v1` → `audio.embed.result.v1` (set `NATS_URL`).

Deterministic: fixed 10 s non-overlapping windows, mean-pooled, L2-normalised,
rounded to 7 dp. Same audio + revision → identical embedding.

Env: `CLAP_MODEL_ID`, `CLAP_MODEL_REVISION`, `CLAP_SAMPLE_RATE`, `CLAP_CLIP_SECONDS`,
`CLAP_HOP_SECONDS`, `CLAP_DEVICE` (cpu|cuda|mps), `CLAP_EMBED_PORT` (8108), `NATS_URL`,
`MODEL_REGISTRY_URL`.

Test: `python -m pytest tests/ -v` (model tests gated by `CLAP_RUN_MODEL_TESTS=1`).
```

- [ ] **Step 6: Verify tests still pass + commit**

Run: `cd pmoves/services/clap-embed && python -m pytest tests/ -v`
Expected: PASS (all non-model tests)

```bash
git add pmoves/services/clap-embed/requirements.txt pmoves/services/clap-embed/Dockerfile pmoves/services/clap-embed/torch.js pmoves/services/clap-embed/README.md pmoves/services/clap-embed/app.py
git commit -m "feat(ws-a): clap-embed packaging (Dockerfile, torch.js, README, registry register)"
```

---

### Task 8: Compose + CATALOG registration

**Files:**
- Modify: `pmoves/docker-compose.yml` (add `clap-embed` service)
- Modify: `.claude/CATALOG.md` (add the catalog line)
- Modify: `docs/superpowers/specs/2026-06-03-ws-a-audio-grounding-design.md` (port 8112 → 8108)

- [ ] **Step 1: Add the compose service** (place near other AI-tier services; CPU default)

```yaml
  clap-embed:
    build:
      context: ./services/clap-embed
      dockerfile: Dockerfile
    image: pmoves/clap-embed:latest
    environment:
      - CLAP_MODEL_ID=${CLAP_MODEL_ID:-laion/larger_clap_music}
      - CLAP_MODEL_REVISION=${CLAP_MODEL_REVISION:-main}
      - CLAP_DEVICE=${CLAP_DEVICE:-cpu}
      - CLAP_EMBED_PORT=8108
      - NATS_URL=${NATS_URL:-}
      - MODEL_REGISTRY_URL=${MODEL_REGISTRY_URL:-http://model-registry:8110}
    ports:
      - "${CLAP_EMBED_BIND:-0.0.0.0}:8108:8108"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8108/healthz"]
      interval: 30s
      timeout: 5s
      start_period: 60s
      retries: 3
```

- [ ] **Step 2: Add the CATALOG line** (under the AI/CHIT services section)

```markdown
**clap-embed** `:8108` — Deterministic CLAP audio/text embedder (MOF lattice node, `laion/larger_clap_music`). `POST /embed/audio`, `POST /embed/text`, `GET /healthz`, `GET /metrics`. Optional NATS `audio.embed.request.v1`/`audio.embed.result.v1`. WS-A grounding layer.
```

- [ ] **Step 3: Correct the spec port**

In `docs/superpowers/specs/2026-06-03-ws-a-audio-grounding-design.md`, replace every `8112` with `8108` and update the §11 line to: "`clap-embed` **port 8108** in the AI/CHIT tier (8112/8113/8114 were already bound to GitHub-automation; 8108 verified free)."

- [ ] **Step 4: Validate compose syntax**

Run: `cd pmoves && docker compose config --quiet && echo OK`
Expected: `OK` (no YAML/schema errors). Do **not** run `up`.

- [ ] **Step 5: Commit**

```bash
git add pmoves/docker-compose.yml .claude/CATALOG.md docs/superpowers/specs/2026-06-03-ws-a-audio-grounding-design.md
git commit -m "feat(ws-a): register clap-embed :8108 in compose + CATALOG; correct spec port"
```

---

## Phase 2 — analyze_beats.py: librosa features

### Task 9: librosa interpretable feature extractor

**Files:**
- Create: `pmoves/tools/tests/test_beats_features.py`
- Modify: `pmoves/tools/analyze_beats.py` (add `librosa_features()` + wire into `extract_all`)

- [ ] **Step 1: Write the failing test** (synthetic tone — no real audio file needed)

```python
# pmoves/tools/tests/test_beats_features.py
import numpy as np
from pmoves.tools.analyze_beats import librosa_features_from_array


def test_librosa_features_shapes_and_keys():
    sr = 22050
    t = np.linspace(0, 5, sr * 5, endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * 220 * t).astype("float32")  # 220 Hz tone
    f = librosa_features_from_array(y, sr)
    assert {"tempo_bpm", "chroma", "mfcc", "spectral_contrast",
            "tonnetz", "onset_rate", "spectral_centroid"} <= set(f)
    assert len(f["chroma"]) == 12
    assert len(f["mfcc"]) == 20
    assert isinstance(f["tempo_bpm"], float)


def test_librosa_features_deterministic():
    sr = 22050
    y = np.sin(np.linspace(0, 50, sr * 4)).astype("float32")
    a = librosa_features_from_array(y, sr)
    b = librosa_features_from_array(y, sr)
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_beats_features.py -v`
Expected: FAIL — `ImportError: cannot import name 'librosa_features_from_array'`

- [ ] **Step 3: Write minimal implementation** (add to `analyze_beats.py`, after imports)

```python
# add near the top-level helpers in pmoves/tools/analyze_beats.py
def librosa_features_from_array(y: "np.ndarray", sr: int) -> dict:
    """Deterministic interpretable features from a mono float32 waveform."""
    import librosa
    y = np.asarray(y, dtype="float32")
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr).mean(axis=1)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20).mean(axis=1)
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr).mean(axis=1)
    tonnetz = librosa.feature.tonnetz(y=librosa.effects.harmonic(y), sr=sr).mean(axis=1)
    onset_env = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    duration = max(len(y) / sr, 1e-6)
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    flatness = float(librosa.feature.spectral_flatness(y=y).mean())
    return {
        "tempo_bpm": round(float(np.asarray(tempo).item()), 4),
        "chroma": [round(float(v), 6) for v in chroma],
        "mfcc": [round(float(v), 6) for v in mfcc],
        "spectral_contrast": [round(float(v), 6) for v in contrast],
        "tonnetz": [round(float(v), 6) for v in tonnetz],
        "onset_rate": round(len(onset_env) / duration, 6),
        "spectral_centroid": round(centroid, 4),
        "spectral_flatness": round(flatness, 6),
    }


def librosa_features(path: "Path") -> dict:
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    return librosa_features_from_array(y, sr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_beats_features.py -v`
Expected: PASS (2 passed). Requires `pip install librosa`.

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/analyze_beats.py pmoves/tools/tests/test_beats_features.py
git commit -m "feat(ws-a): analyze_beats librosa interpretable feature extractor (deterministic)"
```

---

## Phase 3 — analyze_beats.py: CLAP client + embedding-based clustering

### Task 10: CLAP HTTP client with librosa-only fallback

**Files:**
- Create: `pmoves/tools/clap_client.py`
- Test: `pmoves/tools/tests/test_clap_client.py`

- [ ] **Step 1: Write the failing test** (mock transport — no live service)

```python
# pmoves/tools/tests/test_clap_client.py
import httpx
from pmoves.tools.clap_client import ClapClient


def test_embed_audio_success():
    def handler(request):
        return httpx.Response(200, json={"embedding": [0.5] * 512, "model_rev": "main"})
    client = ClapClient("http://clap-embed:8108", transport=httpx.MockTransport(handler))
    vec = client.embed_audio_bytes(b"fakewav", "x.wav")
    assert len(vec) == 512 and client.last_grounding == "full"


def test_embed_audio_failure_flags_partial_and_returns_none():
    def handler(request):
        return httpx.Response(503)
    client = ClapClient("http://clap-embed:8108", transport=httpx.MockTransport(handler))
    vec = client.embed_audio_bytes(b"fakewav", "x.wav")
    assert vec is None and client.last_grounding == "partial"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_clap_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pmoves.tools.clap_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/tools/clap_client.py
"""Thin client for clap-embed (:8108). On any failure returns None and sets
last_grounding='partial' so the caller can degrade to librosa-only, flagged."""
from __future__ import annotations

import os
from typing import Optional

import httpx


class ClapClient:
    def __init__(self, base_url: Optional[str] = None, transport: Optional[httpx.BaseTransport] = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("CLAP_EMBED_URL", "http://localhost:8108")).rstrip("/")
        self._transport = transport
        self.timeout = timeout
        self.last_grounding = "full"

    def embed_audio_bytes(self, data: bytes, filename: str) -> Optional[list[float]]:
        try:
            with httpx.Client(transport=self._transport, timeout=self.timeout) as c:
                r = c.post(f"{self.base_url}/embed/audio",
                           files={"file": (filename, data, "audio/wav")})
                r.raise_for_status()
                self.last_grounding = "full"
                return r.json()["embedding"]
        except Exception:
            self.last_grounding = "partial"
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_clap_client.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/clap_client.py pmoves/tools/tests/test_clap_client.py
git commit -m "feat(ws-a): clap-embed HTTP client with flagged librosa-only fallback"
```

---

### Task 11: Wire CLAP + librosa into analyze_beats `extract_all`; cluster on embeddings

**Files:**
- Modify: `pmoves/tools/analyze_beats.py` (`extract_all`, `cluster`, `measure_coherence`)
- Test: `pmoves/tools/tests/test_beats_features.py` (add clustering test)

- [ ] **Step 1: Write the failing test**

```python
# append to pmoves/tools/tests/test_beats_features.py
from pmoves.tools.analyze_beats import cluster_on_embeddings


def test_cluster_on_embeddings_separates_two_blobs():
    import numpy as np
    rng = np.random.default_rng(0)
    a = [{"clap_embedding": (np.r_[rng.normal(0, 0.01, 512)] + 1.0).tolist()} for _ in range(6)]
    b = [{"clap_embedding": (np.r_[rng.normal(0, 0.01, 512)] - 1.0).tolist()} for _ in range(6)]
    records = a + b
    labels, sil = cluster_on_embeddings(records, n_groups=2)
    assert len(labels) == 12
    assert sil > 0.5                                   # clean separation
    assert len(set(labels[:6])) == 1                   # first blob one cluster
    assert labels[0] != labels[6]                      # blobs differ
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_beats_features.py::test_cluster_on_embeddings_separates_two_blobs -v`
Expected: FAIL — `ImportError: cannot import name 'cluster_on_embeddings'`

- [ ] **Step 3: Write minimal implementation** (add to `analyze_beats.py`)

```python
# add to pmoves/tools/analyze_beats.py
def cluster_on_embeddings(records: list[dict], n_groups: int) -> tuple[list[int], float]:
    """KMeans on CLAP embeddings, silhouette-validated. Falls back to acoustic
    feature vector for any record missing an embedding (flagged upstream)."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    dim = 512
    X = []
    for r in records:
        emb = r.get("clap_embedding")
        if emb and len(emb) == dim:
            X.append(emb)
        else:
            base = [r.get("tempo_bpm", 90.0) / 200.0,
                    r.get("spectral_centroid", 2000.0) / 8000.0,
                    r.get("spectral_flatness", 0.3)]
            X.append(base + [0.0] * (dim - len(base)))
    Xs = StandardScaler().fit_transform(np.array(X))
    n = max(2, min(n_groups, len(records) - 1))
    labels = KMeans(n_clusters=n, random_state=42, n_init="auto").fit_predict(Xs).tolist()
    try:
        sil = round(float(silhouette_score(Xs, labels)), 4)
    except Exception:
        sil = 0.0
    return labels, sil
```

Then in `extract_all`, after the librosa block, add the embedding fetch (deterministic tier) — insert before the label assignments:

```python
        # CLAP embedding (deterministic grounding tier)
        from pmoves.tools.clap_client import ClapClient
        _clap = ClapClient()
        feat["clap_embedding"] = _clap.embed_audio_bytes(path.read_bytes(), path.name) or []
        feat["grounding"] = _clap.last_grounding
        feat.update(librosa_features(path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_beats_features.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/analyze_beats.py pmoves/tools/tests/test_beats_features.py
git commit -m "feat(ws-a): analyze_beats clusters on CLAP embeddings (silhouette-validated) + librosa fingerprint"
```

---

## Phase 4 — beats_to_cgp.py: CGP v2 emission

### Task 12: Emit CGP v2 with hyperbolic + attribution + signature, schema-validated

**Files:**
- Modify: `pmoves/tools/beats_to_cgp.py` (`group_to_cgp` → v2; add `build_cgp_v2`, sign, validate)
- Test: `pmoves/tools/tests/test_beats_to_cgp_v2.py`

- [ ] **Step 1: Write the failing test** (validates against the real schema)

```python
# pmoves/tools/tests/test_beats_to_cgp_v2.py
import json
import os
from pathlib import Path

import jsonschema
from pmoves.tools.beats_to_cgp import build_cgp_v2

SCHEMA = json.loads(Path("pmoves/contracts/schemas/geometry/cgp.v2.schema.json").read_text(encoding="utf-8"))


def _fixtures():
    groups = [
        {"group": "Allegro_warm_Bright", "count": 2, "tracks": ["t0", "t1"]},
        {"group": "Largo_bass_Deep", "count": 1, "tracks": ["t2"]},
    ]
    fps = {
        "t0": {"name": "t0", "tempo_bpm": 128, "spectral_centroid": 3000, "loudness_LRA": 6,
               "spectral_flatness": 0.1, "clap_embedding": [0.9, 0.1] + [0.0] * 510, "duration_s": 200},
        "t1": {"name": "t1", "tempo_bpm": 126, "spectral_centroid": 3200, "loudness_LRA": 7,
               "spectral_flatness": 0.12, "clap_embedding": [0.8, 0.2] + [0.0] * 510, "duration_s": 190},
        "t2": {"name": "t2", "tempo_bpm": 60, "spectral_centroid": 800, "loudness_LRA": 12,
               "spectral_flatness": 0.4, "clap_embedding": [0.1, 0.9] + [0.0] * 510, "duration_s": 240},
    }
    return groups, fps


def test_cgp_v2_validates_against_schema(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    jsonschema.validate(cgp, SCHEMA)
    assert cgp["spec"] == "chit.cgp.v0.2"


def test_cgp_v2_has_hyperbolic_attribution_sig(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    assert cgp["hyperbolic"]["space"] == "poincare_disk"
    assert all(p["x"] ** 2 + p["y"] ** 2 < 1.0 for p in cgp["hyperbolic"]["points"])
    assert abs(sum(c["weight"] for c in cgp["attribution"]["contributors"]) - 1.0) < 1e-6
    assert cgp["sig"]["alg"] == "HMAC-SHA256" and cgp["sig"]["hmac"]


def test_cgp_v2_signature_verifies(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    from pmoves.tools.chit_security import verify_cgp
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    assert verify_cgp(cgp, passphrase="test-key") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_beats_to_cgp_v2.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_cgp_v2'`

- [ ] **Step 3: Write minimal implementation** (add to `beats_to_cgp.py`)

```python
# add imports near the top of pmoves/tools/beats_to_cgp.py
import numpy as np
from pmoves.tools.cgp_v2_build import build_attribution, build_hyperbolic_block
from pmoves.tools.chit_security import sign_cgp


def _group_anchor_vec(members: list[dict]) -> "np.ndarray":
    embs = [m["clap_embedding"][:2] for m in members if m.get("clap_embedding")]
    if not embs:
        return np.array([0.0, 0.0])
    return np.mean(np.array(embs), axis=0)


def build_cgp_v2(groups: list[dict], fingerprints: dict[str, dict], coherence: float = 0.5) -> dict:
    """Assemble a single signed CGP v2 packet across all groups.

    Each track is a point (modality 'audio'); each group is a constellation +
    a Poincaré hierarchy node; attribution is Dirichlet-weighted by track count.
    """
    super_constellations = []
    hb_groups: dict[str, np.ndarray] = {}
    hb_members: dict[str, dict[str, np.ndarray]] = {}
    raw_contrib: dict[str, float] = {}

    for g in groups:
        gname = g["group"]
        members = [fingerprints[n] for n in g["tracks"] if n in fingerprints]
        if not members:
            continue
        gid = _stable_id(gname)
        hb_groups[gid] = _group_anchor_vec(members)
        hb_members[gid] = {}
        raw_contrib[gid] = float(len(members))

        points = []
        for i, rec in enumerate(members):
            sv = track_to_state_vector(rec)
            tid = _stable_id(rec.get("name", f"track_{i}"))
            hb_members[gid][tid] = np.array(rec.get("clap_embedding", [0.0, 0.0])[:2] or [0.0, 0.0])
            points.append({
                "id": tid,
                "label": rec.get("name", f"track_{i}"),
                "modality": "audio",
                "proj": [sv["Hz"], sv["delta"], abs(sv["kappa"])],
                "conf": sv["A"],
                "summary": rec.get("name", ""),
                "meta": {"grounding": rec.get("grounding", "full"),
                         "duration_s": rec.get("duration_s", 0)},
            })
        anchor = _group_anchor_vec(members).tolist()
        super_constellations.append({
            "id": gid,
            "summary": gname,
            "anchor": anchor if anchor else [0.0, 0.0],
            "spectrum": list(np.mean(
                np.array([m.get("mfcc", [0.0] * 20) for m in members]), axis=0)),
            "points": points,
        })

    cgp = {
        "spec": "chit.cgp.v0.2",
        "summary": "DARKXSIDE beats grounding (WS-A)",
        "created_at": _now_iso(),
        "meta": {"source": "cipher_beats_analyst", "coherence": round(coherence, 4),
                 "clap_model": os.environ.get("CLAP_MODEL_ID", "laion/larger_clap_music")},
        "hyperbolic": build_hyperbolic_block(hb_groups, hb_members),
        "attribution": build_attribution(raw_contrib),
        "super_nodes": [{
            "id": _stable_id("sn_beats"),
            "label": "Beats Grounding",
            "constellations": super_constellations,
        }],
    }
    return sign_cgp(cgp, passphrase=os.environ.get("CHIT_PASSPHRASE"))
```

Add the timestamp helper near the other helpers:

```python
def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_beats_to_cgp_v2.py -v`
Expected: PASS (3 passed). Requires `pip install jsonschema`.

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/beats_to_cgp.py pmoves/tools/tests/test_beats_to_cgp_v2.py
git commit -m "feat(ws-a): beats_to_cgp emits signed CGP v2 (hyperbolic + Dirichlet attribution), schema-validated"
```

---

### Task 13: Wire v2 into the `render`/`dump` commands behind a flag

**Files:**
- Modify: `pmoves/tools/beats_to_cgp.py` (`render`, `dump` gain `--v2/--no-v2`, default `--v2`)

- [ ] **Step 1: Add a CGP-version test**

```python
# append to pmoves/tools/tests/test_beats_to_cgp_v2.py
def test_render_dump_uses_v2_by_default(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    from pmoves.tools.beats_to_cgp import select_builder
    groups, fps = _fixtures()
    cgp = select_builder(v2=True)(groups, fps, coherence=0.7)
    assert cgp["spec"] == "chit.cgp.v0.2" and "hyperbolic" in cgp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_beats_to_cgp_v2.py::test_render_dump_uses_v2_by_default -v`
Expected: FAIL — `ImportError: cannot import name 'select_builder'`

- [ ] **Step 3: Write minimal implementation** (add to `beats_to_cgp.py`)

```python
def select_builder(v2: bool = True):
    """Return a (groups, fingerprints, coherence) -> cgp callable.

    v2  -> build_cgp_v2 (whole-packet, signed). Legacy -> per-group group_to_cgp,
    wrapped so the signature matches.
    """
    if v2:
        return build_cgp_v2
    def _legacy(groups, fps, coherence=0.5):
        return {"spec": "chit.cgp.v0.2", "super_nodes":
                [group_to_cgp(g, fps, coherence).get("super_nodes", [{}])[0] for g in groups
                 if group_to_cgp(g, fps, coherence)]}
    return _legacy
```

Then add `v2: bool = typer.Option(True, "--v2/--no-v2", help="Emit CGP v2 (hyperbolic+attribution+sig)")` to `render` and `dump`, and in `render` replace the per-group loop body to build one packet with `select_builder(v2)(groups, fps, coherence=coherence)` and publish it once on `SUBJECT_CGP`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_beats_to_cgp_v2.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/beats_to_cgp.py pmoves/tools/tests/test_beats_to_cgp_v2.py
git commit -m "feat(ws-a): beats_to_cgp render/dump emit CGP v2 by default (--no-v2 for legacy)"
```

---

## Phase 5 — Jellyfin source + reproducibility

### Task 14: Jellyfin music-library source adapter

**Files:**
- Create: `pmoves/tools/jellyfin_audio_source.py`
- Test: `pmoves/tools/tests/test_jellyfin_audio_source.py`

- [ ] **Step 1: Write the failing test** (mock transport)

```python
# pmoves/tools/tests/test_jellyfin_audio_source.py
import httpx
from pmoves.tools.jellyfin_audio_source import JellyfinAudioSource


def test_list_audio_items_maps_item_id():
    def handler(request):
        assert "/Items" in str(request.url)
        return httpx.Response(200, json={"Items": [
            {"Id": "abc123", "Name": "Track One", "Path": "/music/one.flac", "RunTimeTicks": 1200000000},
        ]})
    src = JellyfinAudioSource("http://jellyfin:8096", "key", transport=httpx.MockTransport(handler))
    items = src.list_audio_items()
    assert items[0]["jellyfin_item_id"] == "abc123"
    assert items[0]["name"] == "Track One"
    assert items[0]["duration_s"] == 120.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_jellyfin_audio_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pmoves.tools.jellyfin_audio_source'`

- [ ] **Step 3: Write minimal implementation**

```python
# pmoves/tools/jellyfin_audio_source.py
"""Jellyfin music-library source for audio grounding. Maps Jellyfin item ids
into fingerprints for provenance (links each CGP point back to its source)."""
from __future__ import annotations

import os
from typing import Optional

import httpx


class JellyfinAudioSource:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 transport: Optional[httpx.BaseTransport] = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("JELLYFIN_URL", "http://localhost:8096")).rstrip("/")
        self.api_key = api_key or os.environ.get("JELLYFIN_API_KEY", "")
        self._transport = transport
        self.timeout = timeout

    def list_audio_items(self) -> list[dict]:
        params = {"IncludeItemTypes": "Audio", "Recursive": "true",
                  "Fields": "Path,RunTimeTicks", "api_key": self.api_key}
        with httpx.Client(transport=self._transport, timeout=self.timeout) as c:
            r = c.get(f"{self.base_url}/Items", params=params)
            r.raise_for_status()
            items = r.json().get("Items", [])
        return [{
            "jellyfin_item_id": it["Id"],
            "name": it.get("Name", it["Id"]),
            "file": it.get("Path", ""),
            "duration_s": round(it.get("RunTimeTicks", 0) / 1e7, 3),  # ticks(100ns) -> s
        } for it in items]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_jellyfin_audio_source.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/jellyfin_audio_source.py pmoves/tools/tests/test_jellyfin_audio_source.py
git commit -m "feat(ws-a): Jellyfin music-library audio source (item-id provenance)"
```

---

### Task 15: Reproducibility guarantee (fingerprint hash stability)

**Files:**
- Create: `pmoves/tools/tests/test_reproducibility.py`
- Modify: `pmoves/tools/beats_to_cgp.py` (add `fingerprint_hash`)

- [ ] **Step 1: Write the failing test**

```python
# pmoves/tools/tests/test_reproducibility.py
from pmoves.tools.beats_to_cgp import fingerprint_hash


def test_same_features_same_hash():
    rec = {"name": "t", "tempo_bpm": 128.0, "spectral_centroid": 3000.0,
           "clap_embedding": [0.1, 0.2, 0.3], "mfcc": [1.0, 2.0]}
    assert fingerprint_hash(rec) == fingerprint_hash(dict(rec))


def test_different_embedding_different_hash():
    a = {"name": "t", "clap_embedding": [0.1, 0.2]}
    b = {"name": "t", "clap_embedding": [0.1, 0.3]}
    assert fingerprint_hash(a) != fingerprint_hash(b)


def test_hash_ignores_volatile_fields():
    a = {"name": "t", "clap_embedding": [0.1], "ts": 1.0, "sense_mode": "glaze"}
    b = {"name": "t", "clap_embedding": [0.1], "ts": 999.0, "sense_mode": "gaze"}
    assert fingerprint_hash(a) == fingerprint_hash(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tools/tests/test_reproducibility.py -v`
Expected: FAIL — `ImportError: cannot import name 'fingerprint_hash'`

- [ ] **Step 3: Write minimal implementation** (add to `beats_to_cgp.py`)

```python
def fingerprint_hash(rec: dict) -> str:
    """Stable content hash over the grounding-relevant fields only.

    Excludes volatile fields (timestamps, sense_mode, transient flags) so the
    same audio + model revision always hashes identically (CI reproducibility)."""
    keep = ("name", "tempo_bpm", "spectral_centroid", "spectral_flatness",
            "loudness_LRA", "clap_embedding", "mfcc", "chroma",
            "spectral_contrast", "tonnetz", "onset_rate")
    canon = {k: rec[k] for k in keep if k in rec}
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest pmoves/tools/tests/test_reproducibility.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full WS-A suite + commit**

Run: `python -m pytest pmoves/tools/tests/ pmoves/services/clap-embed/tests/ -v`
Expected: PASS (all non-model-gated tests)

```bash
git add pmoves/tools/beats_to_cgp.py pmoves/tools/tests/test_reproducibility.py
git commit -m "feat(ws-a): reproducible fingerprint hashing (excludes volatile fields)"
```

---

## Self-Review

**1. Spec coverage:**
- §1 goal (replace 4-scalar analysis) → Tasks 9, 11 (librosa + CLAP replace ffmpeg scalars). ✓
- §2 open-source only → all models Apache/MIT/BSD; requirements pin permissive deps. ✓
- §2 model-can-model/tool-can-tool → deterministic tier (Tasks 3–5, 9–11); semantic tier left registry-driven and out of hot path (note in Pre-flight; `gaze` swap deferred — see Gap below). ◑
- §3/§4.1 clap-embed (HTTP + optional NATS, multi-arch, registry, pinned clip/hop, port) → Tasks 3–8. ✓
- §4.2 analyze_beats upgrade (librosa + CLAP + clustering + silhouette) → Tasks 9–11. ✓
- §4.3 CGP v2 (hyperbolic + attribution + sig, schema-validated) → Tasks 1, 2, 12, 13. ✓
- §5 Jellyfin source + backfill → Task 14 (source adapter). Backfill *command* wiring is a thin CLI loop over `list_audio_items()` → `analyze` (Gap below). ◑
- §7 scientific contract (reproducible/validated/auditable/open) → Tasks 12 (schema+sig), 15 (hash), 11 (silhouette). ✓
- §8 error handling (clap down → librosa fallback flagged; schema fail → reject) → Task 10 (`grounding=partial`), Task 12 (jsonschema.validate raises → caller rejects). ✓
- §9 testing (unit/integration/service/repro) → every task is TDD; Task 4 gated model test; Task 12 schema integration; Task 15 repro. ✓

**Gaps found & resolved inline:**
- **Gap (semantic-tier swap):** §4.2 says `gaze` should swap proprietary Qwen2-Audio-via-Ollama for the open registry-driven tier. This plan grounds everything deterministically (so `gaze` is rarely needed) but does not rewrite `gaze_enrich`. **Resolution:** out of WS-A scope as written — escalation backend selection is a registry/config concern tracked for a follow-up task; the deterministic path (the keystone) is complete. Flagged here rather than silently dropped.
- **Gap (Jellyfin backfill command):** Task 14 delivers the source; the `analyze --source jellyfin --backfill` CLI flag is a one-loop addition. **Resolution:** add as Task 16 if the executor wants the CLI surface now; the source adapter is the testable unit and is covered.
- **Gap (pre-CHIT Jellyfin docs):** explicitly deferred to WS-E per spec §5/§10. Correct — not in this plan.

**2. Placeholder scan:** No `TBD`/`TODO`/"add error handling"/"write tests for the above". Every code step has complete code; every test step has full assertions. ✓

**3. Type consistency:** `clap_embedding` (list[float], key name) used identically in Tasks 11, 12, 15. `last_grounding`/`grounding` ("full"|"partial") consistent across Tasks 10–12. `build_cgp_v2(groups, fingerprints, coherence)` signature identical in Tasks 12, 13. `poincare_encode`/`encode_hierarchy`/`build_hyperbolic_block` names consistent Tasks 1, 2, 12. `embed_audio`/`embed_windows`/`embed_text` consistent Tasks 3–5. ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-05-ws-a-audio-grounding.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Note:** the WS-A *design* PR (#1714) should clear the AGNOTE4482 signoff gate before implementation PRs land; coordinate with the Z890 session (important PRs in flight). Implementation should happen on a fresh `feat/ws-a-audio-grounding` branch off `main`, **not** the docs branch.
