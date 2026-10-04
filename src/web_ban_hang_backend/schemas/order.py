from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

from web_ban_hang_backend.schemas.order_item import OrderItemRead


class OrderRead(SQLModel):
    id: UUID
    user_id: UUID
    address_id: UUID | None = None
    total_amount: int
    shipping_fee: int
    status: str
    note: str | None = None
    tracking_code: str | None = None
    shipping_provider: str | None = None

    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderRead):
    items: list[OrderItemRead]