from fastapi import FastAPI
from web_ban_hang_backend.core.firebase import init_firebase
from fastapi.middleware.cors import CORSMiddleware
from web_ban_hang_backend.api.routers import users
from fastapi_pagination import add_pagination

init_firebase()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)

app.include_router(users.router, prefix="/api")