"""Deterministic CLIP embedder for images and text.
The torch/transformers model is injected so the pure logic is testable."""
from __future__ import annotations

from typing import List, Protocol

import numpy as np


class _Model(Protocol):
    def embed_images(self, images: List["np.ndarray"]) -> np.ndarray: ...
    def embed_text(self, texts) -> np.ndarray: ...


class Embedder:
    def __init__(self, model: _Model):
        self.model = model

    def embed_image(self, image: "np.ndarray") -> List[float]:
        vec = self.model.embed_images([image])
        pooled = vec[0]
        norm = float(np.linalg.norm(pooled))
        if norm > 0:
            pooled = pooled / norm
        return [round(float(x), 7) for x in pooled]

    def embed_images(self, images: List["np.ndarray"]) -> List[List[float]]:
        results = self.model.embed_images(images)
        out = []
        for row in results:
            norm = float(np.linalg.norm(row))
            if norm > 0:
                row = row / norm
            out.append([round(float(x), 7) for x in row])
        return out

    def embed_text(self, texts: List[str]):
        return self.model.embed_text(texts)


class ClipHFModel:
    """openai/clip-vit-large-patch14 loaded via transformers. Deterministic: eval(), no grad, fp32."""

    def __init__(self, model_id: str, revision: str = "main", device: str = "cpu"):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        torch.manual_seed(0)
        self._torch = torch
        self.device = device
        self.processor = CLIPProcessor.from_pretrained(model_id, revision=revision)
        self.model = CLIPModel.from_pretrained(model_id, revision=revision, torch_dtype=torch.float32)
        self.model.eval().to(device)

    def embed_images(self, images):
        import numpy as np
        torch = self._torch
        from PIL import Image
        with torch.no_grad():
            pil_images = []
            for img in images:
                if isinstance(img, np.ndarray):
                    pil_images.append(Image.fromarray(img.astype("uint8"), "RGB"))
                else:
                    pil_images.append(img)
            inputs = self.processor(images=pil_images, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self.model.get_image_features(**inputs)
            return feats.detach().cpu().float().numpy()

    def embed_text(self, texts):
        import numpy as np
        torch = self._torch
        with torch.no_grad():
            inputs = self.processor(text=list(texts), return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self.model.get_text_features(**inputs)
            return feats.detach().cpu().float().numpy()
