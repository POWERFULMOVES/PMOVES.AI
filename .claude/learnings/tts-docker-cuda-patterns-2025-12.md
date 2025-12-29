# TTS Docker CUDA Patterns - December 2025

## Context
PR #334: Pinokio TTS engine integration with Docker container fixes

## Key Learnings

### 1. NVIDIA CUDA Base Images for GPU Services
When building GPU-accelerated services that need ONNX Runtime GPU provider:
- Use `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` as runtime base (not pytorch base)
- Install `cuda-nvrtc-12-4` package for ONNX GPU provider
- Set `LD_LIBRARY_PATH` to include CUDA library paths

**Pattern:**
```dockerfile
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS runtime
ENV LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/local/cuda/lib:/usr/lib/x86_64-linux-gnu:/opt/conda/lib:${LD_LIBRARY_PATH}"
RUN apt-get install -y cuda-nvrtc-12-4
```

### 2. Python Dataclass Mutable Defaults
When using dataclasses with mutable defaults (numpy arrays, lists, dicts):
- **Error:** `ValueError: mutable default <class 'numpy.ndarray'> is not allowed`
- **Fix:** Use `field(default_factory=lambda: np.array([]))`

**Before (broken):**
```python
@dataclass
class HiggsAudioResponse:
    generated_text_tokens: np.ndarray = np.array([])  # BROKEN
```

**After (fixed):**
```python
from dataclasses import dataclass, field

@dataclass
class HiggsAudioResponse:
    generated_text_tokens: np.ndarray = field(default_factory=lambda: np.array([]))
```

### 3. Pinokio-Matched Installation Order
When building Docker images for TTS engines with complex dependencies:
1. Install scipy/numpy from conda-forge FIRST (ABI compatibility)
2. Install gradio and devicetorch before requirements.txt
3. Pin huggingface-hub to <1.0
4. Use pip constraint files to prevent version drift
5. Force reinstall numpy/scipy at end to fix mixed conda/pip state

### 4. WSL2/CUDA Compatibility Settings
For GPU services running in WSL2:
```dockerfile
ENV CUDA_FORCE_PTX_JIT=1 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    TORCH_CUDA_ARCH_LIST="5.0;5.2;6.0;6.1;7.0;7.5;8.0;8.6;9.0" \
    TORCH_CUDNN_V8_API_ENABLED=1
```

### 5. On-Demand Model Loading
TTS engines like Kokoro, Fish Speech, and IndexTTS load models on first use:
- Don't expect all engines to show in initial load status
- Health checks should verify service is running, not all models loaded
- Pre-download critical checkpoints during build when possible

## Related Files
- `pmoves/docker/ultimate-tts-studio/Dockerfile`
- `PMOVES-Ultimate-TTS-Studio/higgs_audio/higgs_audio/serve/serve_engine.py`
- `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu` (reference pattern)

## CodeRabbit Feedback
- PR description requires Testing section with documented commands
- Docstring coverage threshold: 80%
- Watch for dead code/unreachable branches in mode handling

## Tags
#docker #cuda #nvidia #tts #gpu #dataclass #pydantic #wsl2 #onnx
