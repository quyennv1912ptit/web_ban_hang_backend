from decimal import Decimal
import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from cloudinary import uploader
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi_pagination import Page, Params, paginate as paginate_items
from fastapi_pagination.ext.sqlmodel import paginate
from pydantic import BaseModel
from slugify import slugify
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, or_, select

from web_ban_hang_backend.api.routers.products import refresh_product_rating
from web_ban_hang_backend.schemas.user import UserStatusUpdate
from web_ban_hang_backend.core.auth import get_admin_user
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.core.deps import ModelStateDep
from web_ban_hang_backend.models.category import Category
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.order_item import OrderItem
from web_ban_hang_backend.models.payment import Payment, PaymentStatus
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.product_image import IMAGE_EMBED_DIM, ProductImage
from web_ban_hang_backend.models.review import Review
from web_ban_hang_backend.models.user import User
from web_ban_hang_backend.schemas.product import ProductCreate, ProductRead
from web_ban_hang_backend.schemas.product_image import ProductImageRead
from web_ban_hang_backend.schemas.order import OrderStatusUpdate
from web_ban_hang_backend.schemas.category import CategoryCreate
from web_ban_hang_backend.services.embedding import embed_image
from web_ban_hang_backend.services.search import execute_hybrid_search
from web_ban_hang_backend.services.image_utils import (
    MAX_IMAGE_BYTES,
    ImageTooLarge,
    ImageValidationError,
    UnsupportedImageFormat,
    decode_image_bytes,
)
from web_ban_hang_backend.services.embedding_index import (
    IMAGE_EMBEDDING_MODEL,
    refresh_text_embedding,
    retry_failed,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_admin_user)],
    responses={404: {"description": "Not found"}},
)


def delete_cloud_images(storage_keys: list[str | None]) -> None:
    for key in storage_keys:
        if not key:
            continue
        try:
            uploader.destroy(key)
        except Exception:
            logger.exception("Không xóa được ảnh %s trên cloud, cần dọn thủ công", key)

class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class UserRoleUpdate(BaseModel):
    role: Literal["customer", "admin"]


# Quản lý sản phẩm

@router.get("/products", response_model=Page[ProductRead])
def get_admin_products(
    session: SessionDep,
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    on_sale: Optional[bool] = None,
    sort: Optional[Literal["newest", "best_selling", "price_asc", "price_desc", "top_rated", "biggest_discount"]] = None,
    is_active: Optional[bool] = None,
    params: Params = Depends(),
):
    """Danh sách sản phẩm quản trị, có tìm kiếm và lọc phân trang."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Giá tối thiểu không được lớn hơn giá tối đa")

    query = select(Product)
    if q and q.strip():
        query = query.where(Product.name.ilike(f"%{q.strip()}%"))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if is_active is not None:
        query = query.where(Product.is_active.is_(is_active))

    discounted = Product.original_price.is_not(None) & (Product.original_price > Product.price)
    if on_sale is True:
        query = query.where(discounted)
    elif on_sale is False:
        query = query.where(or_(Product.original_price.is_(None), Product.original_price <= Product.price))

    if sort == "best_selling":
        query = query.order_by(Product.sold_count.desc(), Product.created_at.desc())
    elif sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "top_rated":
        query = query.order_by(Product.average_rating.desc())
    elif sort == "biggest_discount":
        query = query.order_by((Product.original_price - Product.price).desc(), Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    return paginate(session, query, params=params)


def paginate_admin_ranked_products(session, product_ids: list[UUID], params: Params):
    if not product_ids:
        return paginate_items([], params=params)

    products = session.exec(select(Product).where(Product.id.in_(product_ids))).all()
    products_by_id = {product.id: product for product in products}
    ordered_products = [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]
    return paginate_items(ordered_products, params=params)


@router.post("/products/search/image", response_model=Page[ProductRead])
def search_admin_products_by_image(
    session: SessionDep,
    model_state: ModelStateDep,
    file: UploadFile = File(...),
    q: Optional[str] = Form(None),
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    on_sale: Optional[bool] = None,
    is_active: Optional[bool] = None,
    params: Params = Depends(),
):
    if model_state is None or not model_state.ready:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Mô hình tìm kiếm hình ảnh chưa sẵn sàng",
        )
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Giá tối thiểu không được lớn hơn giá tối đa")

    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)
    try:
        image = decode_image_bytes(image_bytes)
    except UnsupportedImageFormat as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except ImageTooLarge as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except ImageValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    product_ids = execute_hybrid_search(
        session=session,
        model_state=model_state,
        q=q.strip() if q and q.strip() else None,
        image=image,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        is_active=is_active,
        on_sale=on_sale,
    )
    return paginate_admin_ranked_products(session, product_ids, params)

_DB_ERRORS = {
    "products_slug_key": (status.HTTP_409_CONFLICT, "Slug đã tồn tại"),
    "products_sku_key": (status.HTTP_409_CONFLICT, "SKU đã tồn tại"),
    "products_category_id_fkey": (422, "Danh mục không tồn tại"),
    "products_check": (422, "Giá gốc phải lớn hơn hoặc bằng giá bán"),
    "products_price_check": (422, "Giá không được âm"),
    "products_stock_quantity_check": (422, "Tồn kho không được âm"),
}


def product_integrity_error(exc: IntegrityError) -> HTTPException:
    name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    code, detail = _DB_ERRORS.get(name, (status.HTTP_409_CONFLICT, "Dữ liệu sản phẩm không hợp lệ"))
    return HTTPException(code, detail)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, session: SessionDep, model_state: ModelStateDep):
    unique_slug = f"{slugify(data.name)}-{str(uuid4())[:8]}"

    product = Product(**data.model_dump(), slug=unique_slug)
    refresh_text_embedding(product, model_state)

    session.add(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise product_integrity_error(exc)
    session.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductRead)
def get_admin_product_detail(product_id: UUID, session: SessionDep):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    return product


@router.put("/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: UUID, data: ProductCreate, session: SessionDep, model_state: ModelStateDep
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")

    product.sqlmodel_update(data.model_dump(exclude_unset=True))
    refresh_text_embedding(product, model_state)

    session.add(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise product_integrity_error(exc)
    session.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: UUID, session: SessionDep):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    storage_keys = [img.storage_key for img in product.images]
    session.delete(product)
    session.commit()
    delete_cloud_images(storage_keys)


# Quản lý ảnh sản phẩm

@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_product_image(
    product_id: UUID,
    session: SessionDep,
    model_state: ModelStateDep,
    file: UploadFile = File(...),
):
    if not session.get(Product, product_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")

    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File rỗng")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Ảnh vượt quá 10 MB")
    try:
        image = decode_image_bytes(data)
    except UnsupportedImageFormat as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Chỉ chấp nhận ảnh JPEG, PNG hoặc WEBP",
        ) from exc
    except ImageTooLarge as exc:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            str(exc),
        ) from exc
    except ImageValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    vector, embed_status, embed_error = None, "pending", None
    if model_state is not None and model_state.ready:
        try:
            vector = embed_image(model_state, image)
            if len(vector) != IMAGE_EMBED_DIM:
                raise ValueError(f"Vector {len(vector)} chiều, cột DB cần {IMAGE_EMBED_DIM}")
            embed_status = "indexed"
        except Exception as e:
            logger.exception("Lỗi tạo embedding ảnh sản phẩm %s", product_id)
            vector, embed_status, embed_error = None, "failed", str(e)[:500]

    file.file.seek(0)
    try:
        result = uploader.upload(file.file, folder="product_images")
        public_id = result.get("public_id")
        url = result.get("secure_url")
    except Exception:
        logger.exception("Upload ảnh lên cloud thất bại")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Không tải được ảnh lên kho lưu trữ")

    try:
        session.exec(select(Product.id).where(Product.id == product_id).with_for_update())
        next_position = session.exec(
            select(func.coalesce(func.max(ProductImage.position), -1) + 1).where(
                ProductImage.product_id == product_id
            )
        ).one()

        row = ProductImage(
            product_id=product_id,
            position=next_position,
            image_url=url,
            storage_key=public_id,
            multimodal_embedding=vector,
            embedding_model=IMAGE_EMBEDDING_MODEL if vector is not None else None,
            embedding_status=embed_status,
            embedding_error=embed_error,
            indexed_at=datetime.now(timezone.utc) if vector is not None else None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    except Exception:
        session.rollback()
        logger.exception("Ghi DB ảnh sản phẩm thất bại, xóa ảnh %s trên cloud", public_id)
        delete_cloud_images([public_id])
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Không lưu được ảnh sản phẩm")

    return ProductImageRead(
        id=row.id,
        image_url=row.image_url,
        position=row.position,
        embedding_status=row.embedding_status,
        embedding_error=row.embedding_error,
    )


@router.delete("/products/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_image(product_id: UUID, image_id: UUID, session: SessionDep):
    image = session.exec(
        select(ProductImage).where(ProductImage.id == image_id, ProductImage.product_id == product_id)
    ).first()
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy ảnh")
    storage_key = image.storage_key
    session.delete(image)
    session.commit()
    delete_cloud_images([storage_key])

@router.post("/embeddings/retry-failed")
def retry_failed_embeddings(session: SessionDep):
    """Đưa sản phẩm/ảnh bị failed về pending để worker encode lại."""
    return retry_failed(session)

# CRUD QUẢN LÝ DANH MỤC (Categories)

_CATEGORY_ERRORS = {
    "categories_slug_key": (status.HTTP_409_CONFLICT, "Danh mục đã tồn tại"),
    "categories_parent_id_fkey": (422, "Danh mục cha không tồn tại"),
    "categories_parent_not_self_check": (422, "Danh mục không thể là cha của chính nó"),
}


def category_integrity_error(exc: IntegrityError) -> HTTPException:
    name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    code, detail = _CATEGORY_ERRORS.get(name, (status.HTTP_409_CONFLICT, "Dữ liệu danh mục không hợp lệ"))
    return HTTPException(code, detail)


@router.get("/categories", response_model=List[Category])
def get_admin_categories(session: SessionDep):
    return session.exec(select(Category)).all()


@router.post("/categories", response_model=Category, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, session: SessionDep):
    category = Category(**data.model_dump(exclude={"slug"}), slug=slugify(data.name))
    session.add(category)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise category_integrity_error(exc)
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
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise category_integrity_error(exc)
    session.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, session: SessionDep):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy danh mục")
    session.delete(category)
    session.commit()


# QUẢN LÝ ĐƠN HÀNG (Orders)

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
    return {**order.model_dump(), "items": [item.model_dump() for item in order.items]}


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: UUID, data: OrderStatusUpdate, session: SessionDep):
    """Cập nhật trạng thái theo vòng đời đơn và đồng bộ tồn kho."""
    order = session.exec(
        select(Order).where(Order.id == order_id).with_for_update()
    ).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn hàng")

    target_status = data.status.value
    if order.status == target_status:
        return order

    allowed_transitions = {
        OrderStatus.PENDING.value: {
            OrderStatus.PROCESSING.value,
            OrderStatus.CANCELLED.value,
        },
        OrderStatus.PROCESSING.value: {
            OrderStatus.SHIPPED.value,
            OrderStatus.CANCELLED.value,
        },
        OrderStatus.SHIPPED.value: {
            OrderStatus.DELIVERED.value,
            OrderStatus.RETURNED.value,
        },
        OrderStatus.DELIVERED.value: {OrderStatus.RETURNED.value},
    }
    if target_status not in allowed_transitions.get(order.status, set()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Không thể chuyển đơn từ {order.status} sang {target_status}",
        )

    try:
        if target_status == OrderStatus.CANCELLED.value:
            payment = session.exec(
                select(Payment).where(Payment.order_id == order.id).with_for_update()
            ).first()
            if payment and payment.status in {
                PaymentStatus.PROCESSING.value,
                PaymentStatus.COMPLETED.value,
            }:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Không thể hủy đơn khi thanh toán đang xử lý hoặc đã hoàn tất",
                )

        if target_status in (OrderStatus.CANCELLED.value, OrderStatus.RETURNED.value):
            items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()
            product_ids = [item.product_id for item in items if item.product_id]
            products = {
                product.id: product
                for product in session.exec(
                    select(Product)
                    .where(Product.id.in_(product_ids))
                    .order_by(Product.id)
                    .with_for_update()
                ).all()
            }
            for item in items:
                product = products.get(item.product_id) if item.product_id else None
                if product:
                    product.sold_count = max(0, product.sold_count - item.quantity)
                    if target_status == OrderStatus.CANCELLED.value:
                        product.stock_quantity += item.quantity

        order.status = target_status
        session.add(order)
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi cập nhật trạng thái đơn %s", order_id)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Không thể cập nhật trạng thái đơn hàng. Vui lòng thử lại!",
        )

    session.refresh(order)
    return order


# QUẢN LÝ NGƯỜI DÙNG (Users)

@router.get("/users", response_model=Page[User])
def get_all_users(session: SessionDep):
    return paginate(session, select(User).order_by(User.created_at.desc()))


@router.patch("/users/{user_id}/status")
def update_user_status(user_id: UUID, data: UserStatusUpdate, session: SessionDep):
    """Khóa hoặc mở khóa tài khoản người dùng."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng")

    user.is_active = data.is_active
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Đã cập nhật trạng thái người dùng", "is_active": user.is_active}


@router.patch("/users/{user_id}/role")
def update_user_role(user_id: UUID, data: UserRoleUpdate, session: SessionDep):
    """Cập nhật vai trò người dùng."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng")
    
    user.role = data.role
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Đã cập nhật vai trò người dùng", "role": user.role}


# QUẢN LÝ ĐÁNH GIÁ (Reviews)

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
    session.flush()

    refresh_product_rating(session, product_id)

    session.commit()


# THỐNG KÊ (Analytics)

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
        "total_revenue": total_revenue,
    }