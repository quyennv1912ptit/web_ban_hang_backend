import logging
from decimal import Decimal
from uuid import UUID
from typing import Literal, Optional

from fastapi import APIRouter, Form, HTTPException, status, Query, UploadFile, File
from fastapi import Depends
from fastapi_pagination import Page, Params
from fastapi_pagination import paginate as paginate_items
from fastapi_pagination.ext.sqlmodel import paginate as paginate_query
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, desc, func, or_, select

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
# from web_ban_hang_backend.core.deps import ModelStateDep
from web_ban_hang_backend.core.deps import ModelStateDep
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.order_item import OrderItem
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.review import Review
from web_ban_hang_backend.schemas.product import ProductRead
from web_ban_hang_backend.schemas.review import ReviewCreate, ReviewRead, ReviewUpdate

from web_ban_hang_backend.services.search import execute_hybrid_search
from web_ban_hang_backend.services.image_utils import (
    MAX_IMAGE_BYTES,
    ImageTooLarge,
    ImageValidationError,
    UnsupportedImageFormat,
    decode_image_bytes,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/products",
    tags=["Products"],
    responses={404: {"description": "Not found"}},
)


def refresh_product_rating(session: Session, product_id: UUID) -> None:
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

def paginate_ranked_products(
    session: Session,
    product_ids: list[UUID],
    params: Params,
):
    if not product_ids:
        return paginate_items([], params=params)

    stmt = select(Product).where(
        Product.id.in_(product_ids),
        Product.is_active.is_(True),
    )

    products = session.exec(stmt).all()
    products_by_id = {product.id: product for product in products}

    ordered_products = [
        products_by_id[product_id]
        for product_id in product_ids
        if product_id in products_by_id
    ]

    return paginate_items(ordered_products, params=params)

@router.get("/", response_model=Page[ProductRead])
def get_all_products(
    session: SessionDep,
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    on_sale: Optional[bool] = None,
    sort: Optional[Literal["newest", "best_selling", "price_asc", "price_desc", "top_rated"]] = Query(
        None,
        description="newest, best_selling, price_asc, price_desc, top_rated",
    ),
):
    query = select(Product).where(Product.is_active.is_(True))

    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    
    discounted = Product.original_price.is_not(None) & (
        Product.original_price > Product.price
    )
    if on_sale is True:
        query = query.where(discounted)
    elif on_sale is False:
        query = query.where(
            or_(
                Product.original_price.is_(None),
                Product.original_price <= Product.price,
            )
        )

    if sort == "best_selling":
        query = query.order_by(col(Product.sold_count).desc())
    elif sort == "price_asc":
        query = query.order_by(col(Product.price).asc())
    elif sort == "price_desc":
        query = query.order_by(col(Product.price).desc())
    elif sort == "top_rated":
        query = query.order_by(col(Product.average_rating).desc())
    elif sort == "best_selling":
        query = query.order_by(desc(Product.sold_count), desc(Product.created_at))
    else: # newest fallback
        query = query.order_by(desc(Product.created_at))

    return paginate_query(session, query)  # type: ignore

@router.get("/search", response_model=Page[ProductRead])
def search_products(
    session: SessionDep,
    model_state: ModelStateDep,
    q: str = Query(..., min_length=1),
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    params: Params = Depends()
):
    if model_state is None or not model_state.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mô hình tìm kiếm chưa sẵn sàng",
        )

    q = q.strip()

    if not q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Từ khóa tìm kiếm không được để trống",
        )

    product_ids = execute_hybrid_search(
        session=session,
        model_state=model_state,
        q=q,
        image=None,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
    )

    return paginate_ranked_products(
        session,
        product_ids,
        params,
    )

@router.post("/search/image", response_model=Page[ProductRead])
def search_products_by_image(
    session: SessionDep,
    model_state: ModelStateDep,
    file: UploadFile = File(...),
    q: Optional[str] = Form(None),
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    params: Params = Depends(),
):
    if model_state is None or not model_state.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mô hình tìm kiếm hình ảnh chưa sẵn sàng",
        )

    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)
    try:
        image = decode_image_bytes(image_bytes)
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

    product_ids = execute_hybrid_search(
        session=session,
        model_state=model_state,
        q=q.strip() if q and q.strip() else None,
        image=image,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
    )

    return paginate_ranked_products(
        session,
        product_ids,
        params,
    )

@router.get("/suggestions", response_model=list[ProductRead])
def get_product_suggestions(session: SessionDep):
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(func.random())
        .limit(10)
    )

    return session.exec(stmt).all()

@router.get("/{product_id}", response_model=ProductRead)
def get_product_detail(
    product_id: UUID,
    session: SessionDep,
):
    product = session.get(Product, product_id)

    if product is None or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm",
        )

    return product

@router.get("/{product_id}/related", response_model=list[ProductRead])
def get_related_products(
    product_id: UUID,
    session: SessionDep,
):
    product = session.get(Product, product_id)

    if product is None or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm",
        )

    if product.semantic_embedding is None:
        return []

    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.id != product_id,
            Product.semantic_embedding.is_not(None),
        )
        .order_by(
            Product.semantic_embedding.cosine_distance(
                product.semantic_embedding
            ).asc()
        )
        .limit(10)
    )

    return session.exec(stmt).all()

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
    return paginate_query(session, reviews)  # type: ignore


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