from typing import Annotated
from fastapi import Request, Depends
from web_ban_hang_backend.core.model_state import ModelState

def get_models(request: Request) -> ModelState | None:
    return getattr(request.app.state, "model_state", None)

ModelStateDep = Annotated[ModelState | None, Depends(get_models)]
