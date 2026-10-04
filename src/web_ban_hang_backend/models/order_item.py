from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="order_items_quantity_positive"),
        CheckConstraint("price >= 0", name="order_items_price_nonneg"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="orders.id", ondelete="CASCADE", index=True)
    product_id: UUID | None = Field(
        default=None, foreign_key="products.id", ondelete="SET NULL", index=True
    )
    product_name: str
    quantity: int = 1
    price: Decimal = Field(sa_type=Numeric(12, 0))

    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))