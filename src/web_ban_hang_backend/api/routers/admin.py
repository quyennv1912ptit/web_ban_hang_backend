from fastapi import APIRouter, Depends
from web_ban_hang_backend.core.auth import AdminUser

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(lambda: AdminUser)]
)

# 1. CRUD QUẢN LÝ SẢN PHẨM (Products)
@router.get("/products")
async def get_admin_products():
    pass

@router.post("/products")
async def create_product():
    pass

@router.get("/products/{product_id}")
async def get_admin_product_detail(product_id: str):
    pass

@router.put("/products/{product_id}")
async def update_product(product_id: str):
    pass

@router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    pass

# 2. CRUD QUẢN LÝ DANH MỤC (Categories)
@router.get("/categories")
async def get_admin_categories():
    pass

@router.post("/categories")
async def create_category():
    pass

@router.get("/categories/{category_id}")
async def get_admin_category_detail(category_id: int):
    pass

@router.put("/categories/{category_id}")
async def update_category(category_id: int):
    pass

@router.delete("/categories/{category_id}")
async def delete_category(category_id: int):
    pass

# 3. QUẢN LÝ ĐƠN HÀNG (Orders)
@router.get("/orders")
async def get_all_orders():
    pass

@router.patch("/orders/{order_id}/status")
async def update_order_status(order_id: str):
    pass

# 4. THỐNG KÊ (Analytics)
@router.get("/analytics")
async def get_analytics():
    pass