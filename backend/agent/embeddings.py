from __future__ import annotations
from typing import List
import torch
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer

class CLIPEncoder:
    def __init__(self, model_name: str = "clip-ViT-B-32"):
        # One model supports both text and image
        self.model = SentenceTransformer(model_name)

    def encode_text(self, texts: List[str]) -> np.ndarray:
        embs = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return embs.astype("float32")

    def encode_image(self, image: Image.Image) -> np.ndarray:
        # Ensure consistent shape by always batching a single image
        emb = self.model.encode([image], normalize_embeddings=True, convert_to_numpy=True)
        return emb.astype("float32")[0]
