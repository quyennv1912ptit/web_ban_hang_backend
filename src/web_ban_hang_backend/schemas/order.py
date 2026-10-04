from datetime import datetime
from uuid import UUID
from decimal import Decimal

from sqlmodel import SQLModel, Field

from web_ban_hang_backend.schemas.order_item import OrderItemRead, OrderItemCreate


class OrderRead(SQLModel):
    id: UUID
    user_id: UUID
    address_id: UUID | None = None
    total_amount: Decimal
    shipping_fee: Decimal
    status: str
    note: str | None = None
    tracking_code: str | None = None
    shipping_provider: str | None = None

    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderRead):
    items: list[OrderItemRead]

class OrderRequest(SQLModel):
    address_id: UUID
    note: str | None = Field(default=None, max_length=500)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=50)