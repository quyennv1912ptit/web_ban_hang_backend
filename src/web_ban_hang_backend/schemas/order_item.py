from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class OrderItemRead(SQLModel):
    id: UUID
    order_id: UUID
    product_id: UUID | None = None
    product_name: str
    quantity: int
    price: int

    created_at: datetime