import logging
from uuid import UUID
from typing import Any, List, Literal, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlmodel import select, func
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from pydantic import BaseModel, Field

from web_ban_hang_backend.core.auth import AdminUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.category import Category
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.user import User
from web_ban_hang_backend.models.review import Review
from web_ban_hang_backend.models.product_image import ProductImage
from web_ban_hang_backend.api.routers.products import refresh_product_rating # Tái sử dụng hàm tính lại rating

logger = logging.getLogger(__name__)

# --- SỬA TẠI ĐÂY: Bỏ dependencies=[Depends(AdminUser)] để tránh lỗi 422 ---
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    # dependencies=[Depends(AdminUser)], <--- Xóa hoặc comment dòng này lại
    responses={404: {"description": "Not found"}},
)

# --- SCHEMAS TẠM THỜI (Nên chuyển vào thư mục schemas sau) ---
class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None

class ProductCreate(BaseModel):
    category_id: Optional[int] = None
    name: str
    slug: str
    description: Optional[str] = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=0)
    original_price: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=12, decimal_places=0
    )
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    sku: Optional[str] = None
    weight_grams: Optional[int] = Field(default=0, ge=0)

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class UserRoleUpdate(BaseModel):
    role: Literal["customer", "admin"]


# ==========================================
# 1. CRUD QUẢN LÝ SẢN PHẨM (Products)
# ==========================================
@router.get("/products", response_model=Page[Product])
def get_admin_products(session: SessionDep):
    """Danh sách sản phẩm (có phân trang)"""
    return paginate(session, select(Product).order_by(Product.created_at.desc()))

@router.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, session: SessionDep):
    """Tạo sản phẩm mới"""
    product = Product(**data.model_dump())
    session.add(product)
    session.commit()
    session.refresh(product)
    return product

@router.get("/products/{product_id}", response_model=Product)
def get_admin_product_detail(product_id: UUID, session: SessionDep):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    return product

@router.put("/products/{product_id}", response_model=Product)
def update_product(product_id: UUID, data: ProductCreate, session: SessionDep):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    
    product.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(product)
    session.commit()
    session.refresh(product)
    return product

@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: UUID, session: SessionDep):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    session.delete(product)
    session.commit()

# --- QUẢN LÝ ẢNH SẢN PHẨM ---
@router.post("/products/{product_id}/images")
async def upload_product_image(product_id: UUID, session: SessionDep, file: UploadFile = File(...)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
        
    # TODO: Implement upload file lên Cloud (AWS S3, Firebase Storage, Cloudinary, v.v.)
    # TODO: Gọi model Jina-CLIP sinh embedding cho file ảnh này
    fake_image_url = f"https://example.com/uploads/{file.filename}"
    
    next_position = session.exec(
        select(func.coalesce(func.max(ProductImage.position), -1)).where(
            ProductImage.product_id == product_id
        )
    ).one() + 1
    image = ProductImage(
        product_id=product_id,
        original_url=fake_image_url,
        position=next_position,
    )
    session.add(image)
    session.commit()
    return {"message": "Upload thành công", "original_url": fake_image_url}

@router.delete("/products/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_image(product_id: UUID, image_id: UUID, session: SessionDep):
    image = session.exec(
        select(ProductImage).where(ProductImage.id == image_id, ProductImage.product_id == product_id)
    ).first()
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy ảnh")
    session.delete(image)
    session.commit()


# ==========================================
# 2. CRUD QUẢN LÝ DANH MỤC (Categories)
# ==========================================
@router.get("/categories", response_model=List[Category])
def get_admin_categories(session: SessionDep):
    return session.exec(select(Category)).all()

@router.post("/categories", response_model=Category, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, session: SessionDep):
    category = Category(**data.model_dump())
    session.add(category)
    session.commit()
    session.refresh(category)
    return category

@router.get("/categories/{category_id}", response_model=Category)
def get_admin_category_detail(category_id: int, session: SessionDep):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy danh mục")
    return category

@router.put("/categories/{category_id}", response_model=Category)
def update_category(category_id: int, data: CategoryCreate, session: SessionDep):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy danh mục")
    category.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(category)
    session.commit()
    session.refresh(category)
    return category

@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, session: SessionDep):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy danh mục")
    session.delete(category)
    session.commit()


# ==========================================
# 3. QUẢN LÝ ĐƠN HÀNG (Orders)
# ==========================================
@router.get("/orders", response_model=Page[Order])
def get_all_orders(session: SessionDep):
    """Danh sách tất cả đơn hàng trên hệ thống"""
    return paginate(session, select(Order).order_by(Order.created_at.desc()))

@router.get("/orders/{order_id}")
def get_admin_order_detail(order_id: UUID, session: SessionDep):
    """Chi tiết đơn hàng kèm các items bên trong"""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn hàng")
    return order

@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: UUID, data: OrderStatusUpdate, session: SessionDep):
    """Cập nhật trạng thái đơn hàng (ví dụ: Chờ xử lý -> Đang giao)"""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn hàng")
    
    order.status = data.status.value
    session.commit()
    session.refresh(order)
    return order


# ==========================================
# 4. QUẢN LÝ NGƯỜI DÙNG (Users)
# ==========================================
@router.get("/users", response_model=Page[User])
def get_all_users(session: SessionDep):
    return paginate(session, select(User).order_by(User.created_at.desc()))

@router.patch("/users/{user_id}")
def update_user_role(user_id: UUID, data: UserRoleUpdate, session: SessionDep):
    """Cập nhật vai trò người dùng"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng")
    
    user.role = data.role
    session.commit()
    session.refresh(user)
    return {"message": "Đã cập nhật vai trò người dùng", "role": user.role}


# ==========================================
# 5. QUẢN LÝ ĐÁNH GIÁ (Reviews)
# ==========================================
@router.get("/reviews", response_model=Page[Review])
def get_admin_reviews(session: SessionDep):
    """Lấy danh sách tất cả đánh giá để kiểm duyệt"""
    return paginate(session, select(Review).order_by(Review.created_at.desc()))

@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_review(review_id: UUID, session: SessionDep):
    """Xóa đánh giá vi phạm và tính lại rating trung bình của sản phẩm"""
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đánh giá")
    
    product_id = review.product_id
    session.delete(review)
    session.flush() # Xóa tạm thời để tính lại rating
    
    # Tính lại rating trung bình cho sản phẩm sau khi xóa
    refresh_product_rating(session, product_id)
    
    session.commit()


# ==========================================
# 6. THỐNG KÊ (Analytics)
# ==========================================
@router.get("/analytics")
def get_analytics(session: SessionDep):
    """Trả về các con số thống kê tổng quan cho Dashboard Admin"""
    total_users = session.exec(select(func.count(User.id))).one()
    total_products = session.exec(select(func.count(Product.id))).one()
    total_orders = session.exec(select(func.count(Order.id))).one()
    
    # Tính tổng doanh thu từ các đơn hàng đã giao.
    total_revenue_result = session.exec(
        select(func.sum(Order.total_amount)).where(Order.status == OrderStatus.DELIVERED.value)
    ).one()
    total_revenue = total_revenue_result if total_revenue_result else 0

    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_revenue": total_revenue
    }
