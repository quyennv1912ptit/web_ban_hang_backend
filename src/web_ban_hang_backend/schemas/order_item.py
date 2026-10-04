from datetime import datetime
from uuid import UUID
from decimal import Decimal

from sqlmodel import SQLModel, Field


class OrderItemRead(SQLModel):
    id: UUID
    order_id: UUID
    product_id: UUID | None = None
    product_name: str
    quantity: int
    price: Decimal

    created_at: datetime

class OrderItemCreate(SQLModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=100)