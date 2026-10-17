import numpy as np
from PIL import Image
from web_ban_hang_backend.core.model_state import ModelState
from web_ban_hang_backend.services.image_utils import decode_image_bytes

def _normalize(vec: np.ndarray) -> list[float]:
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("Embedding không hợp lệ")
    return (vec / norm).tolist()

def embed_text(models: ModelState, text: str) -> list[float]:
    vec = models.text_model.encode(text, normalize_embeddings=True)
    return vec.tolist()

def embed_image(models: ModelState, image: Image.Image) -> list[float]:
    vec = models.image_model.encode_image([image])[0]  # type: ignore[attr-defined]
    return _normalize(np.asarray(vec))

def embed_clip_text(models: ModelState, text: str) -> list[float]:
    vec = models.image_model.encode_text(text)  # type: ignore[attr-defined]
    return _normalize(np.asarray(vec))

def embed_image_bytes(models: ModelState, raw: bytes) -> list[float]:
    return embed_image(models, decode_image_bytes(raw))
