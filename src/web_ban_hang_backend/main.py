from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

from web_ban_hang_backend.core.firebase import init_firebase
from web_ban_hang_backend.config import settings

# 1. IMPORT ĐẦY ĐỦ CÁC ROUTER
from web_ban_hang_backend.api.routers import (
    users,
    categories,
    products,
    cart,
    orders,
    admin
)

init_firebase()
app = FastAPI()

# Danh sách các tên miền Frontend được phép gọi API
origins = [
    "http://localhost:5173",      
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    # 2. TRUYỀN ĐÚNG BIẾN origins VÀO ĐÂY
    allow_origins=origins, 
    allow_credentials=True, # Bắt buộc phải có True để frontend có thể gửi token Firebase sang
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)

# 3. ĐĂNG KÝ TOÀN BỘ ROUTER VÀO ỨNG DỤNG
app.include_router(users.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(admin.router, prefix="/api")