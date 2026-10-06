from typing import Annotated
from fastapi import Request, HTTPException, Depends
from web_ban_hang_backend.core.model_state import ModelState

def get_models(request: Request) -> ModelState:
    model_state = getattr(request.app.state, "model_state", None)
    if model_state is None:
        raise HTTPException(503, "Models chưa sẵn sàng")
    return model_state

ModelStateDep = Annotated[ModelState, Depends(get_models)]