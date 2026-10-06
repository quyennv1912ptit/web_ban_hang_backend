import numpy as np

def fuse_vectors(
    text_vec: list[float] | None,
    image_vec: list[float] | None,
    alpha: float = 0.6,
    beta: float = 0.4,
) -> list[float]:
    if text_vec is not None and image_vec is not None:
        v = alpha * np.array(image_vec) + beta * np.array(text_vec)
    elif image_vec is not None:
        v = np.array(image_vec)
    elif text_vec is not None:
        v = np.array(text_vec)
    else:
        raise ValueError("Cần ít nhất text_vec hoặc image_vec để fuse")
    return (v / np.linalg.norm(v)).tolist()