from fastapi import APIRouter, Query, HTTPException, status
from sqlmodel import select, col
from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.schemas.order import OrderRead, OrderDetail
from web_ban_hang_backend.schemas.order_item import OrderItemRead
from web_ban_hang_backend.models.order_item import OrderItem
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from uuid import UUID

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=Page[OrderRead])
def get_orders_history(current_user: CurrentUser, session: SessionDep, order_status: OrderStatus | None = Query(default=None, alias="status")):
    query = select(Order).where(Order.user_id == current_user.id)
    if order_status:
        query = query.where(Order.status == order_status.value)
    query = query.order_by(col(Order.created_at).desc(), col(Order.id))

    return paginate(session, query) # type: ignore

@router.get("/{order_id}", response_model=OrderDetail)
def get_order_info(order_id: UUID, current_user: CurrentUser, session: SessionDep):
    order = session.exec(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    ).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn đặt hàng")

    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderDetail(
        **order.model_dump(),
        items=[OrderItemRead.model_validate(item) for item in items],
)

@router.post("/")
def create_order():
    pass

@router.put("/{id}")
def update_order_info(id: str):
    pass

@router.delete("/{id}")
def cancel_order(id: str):
    pass