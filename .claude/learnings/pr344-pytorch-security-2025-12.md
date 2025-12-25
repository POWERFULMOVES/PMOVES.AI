# PR #344: PyTorch Security Upgrade (CVE in torch.load)

**Date:** 2025-12-22
**PR:** #344 (fix(security): Upgrade PyTorch to 2.6.0)
**Source:** Dependabot alert #61, CodeRabbit review

---

## 1. The Security Issue: torch.load CVE

### Vulnerability

`torch.load()` without `weights_only=True` can execute arbitrary Python code during deserialization. This is a **critical** security vulnerability when loading model weights from untrusted sources.

### Pattern: Safe Model Loading

```python
# BAD: Vulnerable to arbitrary code execution
model.load_state_dict(torch.load("model.pt"))

# GOOD: Safe loading with weights_only
model.load_state_dict(torch.load("model.pt", weights_only=True))
```

### When weights_only=True Works

- Loading state dictionaries (model weights)
- Loading tensors
- Loading standard Python types (dict, list, tuple, str, int, float, bool)

### When You Need weights_only=False

- Loading custom Python objects
- Loading legacy model formats
- Loading models with custom unpicklers

```python
# If you must use weights_only=False, document the trust source
# WARNING: Only use with trusted model files
model = torch.load(
    "trusted_model.pt",
    weights_only=False,
    # Optional: restrict to known classes
    # map_location=torch.device('cpu')
)
```

---

## 2. CUDA Version Upgrade

### Version Changes

| Package | Before | After | Notes |
|---------|--------|-------|-------|
| torch | 2.3.1+cu121 | 2.6.0+cu124 | Major version bump |
| torchvision | 0.18.1+cu121 | 0.21.0+cu124 | Requires torch >=2.8.0 metadata (!) |
| torchaudio | 2.3.1+cu121 | 2.6.0+cu124 | Aligned with torch |

### Breaking Change: CUDA 12.4 Required

The upgrade requires CUDA 12.4 runtime (was 12.1). Update base images:

```dockerfile
# BEFORE
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# AFTER
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04
```

### Torchvision Metadata Warning

Torchvision 0.21.0 declares `torch >=2.8.0` in its metadata, but actually works with torch 2.6.0. This is a packaging bug upstream.

```bash
# You may see this warning during pip install:
# WARNING: torchvision 0.21.0 requires torch>=2.8.0
# This can be safely ignored - torchvision 0.21.0 works with torch 2.6.0
```

---

## 3. Affected Services

### media-video

Primary consumer of PyTorch for YOLO object detection.

```dockerfile
# pmoves/services/media-video/Dockerfile
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

# Pin exact versions for reproducibility
RUN pip install \
    torch==2.6.0+cu124 \
    torchvision==0.21.0+cu124 \
    torchaudio==2.6.0+cu124 \
    --extra-index-url https://download.pytorch.org/whl/cu124
```

### Other GPU Services

Check these services if they use PyTorch:
- flute-gateway (TTS models)
- hi-rag-gateway-v2-gpu (embedding models)
- ultimate-tts-studio

---

## 4. Verification Checklist

```bash
# 1. Check CUDA version on host
nvidia-smi | head -3

# 2. Rebuild affected images
docker compose build media-video

# 3. Verify torch import works
docker exec pmoves-media-video-1 python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.version.cuda}')
print(f'Available: {torch.cuda.is_available()}')
"

# 4. Run smoke tests
cd pmoves && make smoke
```

---

## 5. Requirements.lock Pattern

For services with PyTorch, maintain separate requirements files:

```
requirements.txt          # Main dependencies (no PyTorch)
requirements-torch.txt    # PyTorch with exact versions + index
requirements.lock         # Generated lock file for main deps
```

```dockerfile
# Dockerfile pattern
COPY requirements.txt requirements-torch.txt ./
RUN pip install --constraint requirements.lock -r requirements.txt
RUN pip install -r requirements-torch.txt --extra-index-url https://download.pytorch.org/whl/cu124
```

### Why Separate Files?

- PyTorch packages use different indexes (download.pytorch.org)
- Hash verification conflicts between PyPI and PyTorch indexes
- Allows independent version pinning

---

## 6. Security Scanning

### Dependabot Alert Format

```markdown
## Security Advisory
Package: torch
Severity: Critical
Affected versions: < 2.6.0
CVE: [CVE-XXXX-XXXXX]
Fix: Upgrade to torch >= 2.6.0
```

### Trivy Scanning

```bash
# Scan Docker images for vulnerabilities
trivy image pmoves-media-video:latest --severity CRITICAL,HIGH
```

---

## Related Commits

| Hash | Description |
|------|-------------|
| PR #344 | PyTorch 2.6.0 security upgrade |
| Dependabot #61 | Original security alert |

---

## Tags

`security` `pytorch` `cuda` `cve` `torch.load` `gpu` `dependabot`
