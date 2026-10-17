import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

from web_ban_hang_backend.core.firebase import init_firebase
from web_ban_hang_backend.core.model_state import load_models
from web_ban_hang_backend.config import settings

import cloudinary

from web_ban_hang_backend.api.routers import (
    users,
    categories,
    products,
    cart,
    orders,
    admin
)

init_firebase()
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret = settings.CLOUDINARY_API_SECRET,
    secure=True
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model_state = None
    try:
        app.state.model_state = await asyncio.to_thread(load_models)
    except Exception:
        logger.exception("Không nạp được model tìm kiếm; API tìm kiếm sẽ tạm trả 503")
    try:
        yield
    finally:
        app.state.model_state = None


app = FastAPI(lifespan=lifespan)

# Danh sách các tên miền Frontend được phép gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)

app.include_router(users.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
