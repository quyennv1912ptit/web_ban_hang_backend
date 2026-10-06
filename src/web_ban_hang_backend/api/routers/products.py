import logging
from decimal import Decimal
from uuid import UUID
import anyio

from fastapi import APIRouter, HTTPException, status, Form, UploadFile, File
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, desc, func, select

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.core.deps import ModelStateDep
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.order_item import OrderItem
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.review import Review
from web_ban_hang_backend.schemas.product import ProductRead
from web_ban_hang_backend.schemas.review import ReviewCreate, ReviewRead, ReviewUpdate

from web_ban_hang_backend.services.embedding import embed_text, embed_image_bytes

from web_ban_hang_backend.services.fusion import fuse_vectors

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


@router.get("/", response_model=Page[ProductRead])
def get_all_products(session: SessionDep):
    products = select(Product).order_by(desc(Product.created_at))
    return paginate(session, products)  # type: ignore


@router.get("/{product_id}", response_model=ProductRead)
def get_product_detail(session: SessionDep, product_id: UUID):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    return product

@router.post("/search")
async  def search_product(
    models: ModelStateDep,
    q: str|None = Form(None),
    image: UploadFile = File(None)
):
    text_vec = None
    image_vec = None

    if q:
        text_vec = await anyio.to_thread.run_sync(embed_text, models, q)

    if image is not None:
        raw = await image.read()
        image_vec = await anyio.to_thread.run_sync(embed_image_bytes, models, raw)

    query_vec = fuse_vectors(text_vec, image_vec)


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