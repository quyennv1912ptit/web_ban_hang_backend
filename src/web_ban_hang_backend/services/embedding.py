import io
import numpy as np
from PIL import Image
from web_ban_hang_backend.core.model_state import ModelState

def _normalize(vec: np.ndarray) -> list[float]:
    return (vec / np.linalg.norm(vec)).tolist()

def embed_text(models: ModelState, text: str) -> list[float]:
    vec = models.text_model.encode(text, normalize_embeddings=True)
    return vec.tolist()

def embed_image_bytes(models: ModelState, raw: bytes) -> list[float]:
    pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
    vec = models.image_model.encode_image([pil_img])[0]  # type: ignore[attr-defined]
    return _normalize(np.array(vec))