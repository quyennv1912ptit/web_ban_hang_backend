from fastapi import FastAPI
from web_ban_hang_backend.core.firebase import init_firebase
from fastapi.middleware.cors import CORSMiddleware
from web_ban_hang_backend.api.routers import users
from fastapi_pagination import add_pagination

from web_ban_hang_backend.config import settings

init_firebase()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)

app.include_router(users.router, prefix="/api")