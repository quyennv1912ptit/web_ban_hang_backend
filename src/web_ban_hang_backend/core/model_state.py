from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
from transformers import AutoModel
import torch

@dataclass
class ModelState:
    text_model: SentenceTransformer
    image_model: AutoModel
    device: str

model_state: ModelState | None = None

def load_models() -> ModelState:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    text_model = SentenceTransformer("BAAI/bge-m3", device=device)
    image_model = AutoModel.from_pretrained(
        "jinaai/jina-clip-v2", trust_remote_code=True
    ).to(device).eval()
    return ModelState(text_model=text_model, image_model=image_model, device=device)
