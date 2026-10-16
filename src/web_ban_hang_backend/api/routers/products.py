import logging
from decimal import Decimal
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query, UploadFile, File
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, desc, func, select

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
# from web_ban_hang_backend.core.deps import ModelStateDep
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.order_item import OrderItem
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.review import Review
from web_ban_hang_backend.schemas.product import ProductRead
from web_ban_hang_backend.schemas.review import ReviewCreate, ReviewRead, ReviewUpdate

# from web_ban_hang_backend.services.embedding import embed_text, embed_image_bytes

# from web_ban_hang_backend.services.fusion import fuse_vectors

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/products",
    tags=["Products"],
    responses={404: {"description": "Not found"}},
)


def refresh_product_rating(session: Session, product_id: UUID) -> None:
    """Tính lại average_rating. Gọi sau flush(), trước commit()."""
    product = session.get(Product, product_id)
    if not product:
        return
    avg = session.exec(
        select(func.coalesce(func.avg(Review.rating), 0)).where(
            Review.product_id == product_id
        )
    ).one()
    product.average_rating = Decimal(str(avg)).quantize(Decimal("0.01"))
    session.add(product)


def get_own_review(
    session: Session, review_id: UUID, product_id: UUID, user_id: UUID
) -> Review:
    review = session.exec(
        select(Review).where(
            Review.id == review_id,
            Review.product_id == product_id,
            Review.user_id == user_id,
        )
    ).first()
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đánh giá")
    return review

# --- CÁC ROUTE TÌM KIẾM & LỌC (MỚI & ĐƯỢC CẬP NHẬT) ---

@router.get("/", response_model=Page[ProductRead])
def get_all_products(
    session: SessionDep,
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    on_sale: Optional[bool] = None,
    sort: Optional[str] = Query(None, description="newest, best_selling, price_asc, price_desc, top_rated"),
):
    query = select(Product).where(Product.is_active == True)

    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    if category_id:
        query = query.where(Product.category_id == category_id)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if on_sale:
        query = query.where(
            Product.original_price.is_not(None),
            Product.original_price > Product.price,
        )

    if sort == "best_selling":
        query = query.order_by(col(Product.sold_count).desc())
    elif sort == "price_asc":
        query = query.order_by(col(Product.price).asc())
    elif sort == "price_desc":
        query = query.order_by(col(Product.price).desc())
    elif sort == "top_rated":
        query = query.order_by(col(Product.average_rating).desc())
    else: # newest fallback
        query = query.order_by(desc(Product.created_at))

    return paginate(session, query)  # type: ignore

@router.get("/search", response_model=Page[ProductRead])
def search_products(q: str, session: SessionDep):
    """Tìm theo văn bản bằng embedding bge-m3 và pgvector (Cần implement embedding logic)."""
    # TODO: Gọi model bge-m3 để lấy embedding của `q`. Ví dụ vec = get_embedding(q)
    # query = select(Product).order_by(Product.semantic_embedding.l2_distance(vec))
    pass

@router.post("/search/image")
async def search_products_by_image(file: UploadFile = File(...), session: SessionDep = None):
    """Upload ảnh, tìm sản phẩm giống bằng Jina-CLIP."""
    # TODO: Gọi Jina-CLIP sinh embedding cho ảnh, query pgvector.
    pass

@router.get("/suggestions")
def get_product_suggestions(session: SessionDep):
    """Gợi ý hôm nay cho trang chủ."""
    query = select(Product).where(Product.is_active == True).order_by(func.random()).limit(10)
    return session.exec(query).all()

# --- CHI TIẾT SẢN PHẨM & TƯƠNG TỰ ---

@router.get("/{product_id}", response_model=ProductRead)
def get_product_detail(session: SessionDep, product_id: UUID):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    return product

@router.get("/{product_id}/related")
def get_related_products(product_id: UUID, session: SessionDep):
    """Sản phẩm tương tự theo embedding."""
    # TODO: Lấy Product hiện tại -> Lấy embedding của nó -> Query KNN cosine similarity.
    pass


# --- CÁC ROUTE REVIEWS (GIỮ NGUYÊN TỪ MÃ CŨ CỦA BẠN) ---

@router.get("/{product_id}/reviews", response_model=Page[ReviewRead])
def get_product_reviews(session: SessionDep, product_id: UUID):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")

    reviews = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(col(Review.created_at).desc(), col(Review.id))
    )
    return paginate(session, reviews)  # type: ignore


@router.post(
    "/{product_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def add_product_review(
    product_id: UUID,
    data: ReviewCreate,
    current_user: CurrentUser,
    session: SessionDep,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")

    order = session.exec(
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)  # type: ignore
        .where(
            Order.id == data.order_id,
            Order.user_id == current_user.id,
            Order.status == OrderStatus.DELIVERED.value,
            OrderItem.product_id == product_id,
        )
    ).first()
    if not order:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bạn chỉ có thể đánh giá sản phẩm đã mua và nhận hàng",
        )

    review = Review(
        user_id=current_user.id,
        product_id=product_id,
        order_id=order.id,
        rating=data.rating,
        comment=data.comment,
    )
    session.add(review)
    try:
        session.flush()
        refresh_product_rating(session, product_id)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Bạn đã đánh giá sản phẩm này cho đơn hàng này",
        )
    except Exception:
        session.rollback()
        logger.exception("Lỗi thêm đánh giá")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Không thể thêm đánh giá. Vui lòng thử lại!",
        )

    session.refresh(review)
    return review


@router.put("/{product_id}/reviews/{review_id}", response_model=ReviewRead)
def update_product_review(
    product_id: UUID,
    review_id: UUID,
    data: ReviewUpdate,
    current_user: CurrentUser,
    session: SessionDep,
):
    review = get_own_review(session, review_id, product_id, current_user.id)
    review.sqlmodel_update(data.model_dump(exclude_unset=True, exclude_none=True))
    session.add(review)
    try:
        session.flush()
        refresh_product_rating(session, product_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi cập nhật đánh giá")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Không thể cập nhật đánh giá. Vui lòng thử lại!",
        )

    session.refresh(review)
    return review


@router.delete(
    "/{product_id}/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_product_review(
    product_id: UUID,
    review_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
):
    review = get_own_review(session, review_id, product_id, current_user.id)
    session.delete(review)
    try:
        session.flush()
        refresh_product_rating(session, product_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi xóa đánh giá")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Không thể xóa đánh giá. Vui lòng thử lại!",
        )
