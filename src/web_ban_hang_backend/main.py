from contextlib import asynccontextmanager

from fastapi import FastAPI

from web_ban_hang_backend.core.firebase import init_firebase
from fastapi.middleware.cors import CORSMiddleware
from web_ban_hang_backend.api.routers import users
from fastapi_pagination import add_pagination

from web_ban_hang_backend.config import settings
from web_ban_hang_backend.core.model_state import load_models

init_firebase()

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model_state = load_models()
    yield
    app.state.model_state = None

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)

app.include_router(users.router, prefix="/api")