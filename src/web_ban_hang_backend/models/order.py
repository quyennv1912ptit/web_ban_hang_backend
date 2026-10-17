from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from web_ban_hang_backend.models.order_item import OrderItem

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"

_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in OrderStatus)

class Order(SQLModel, table=True):
    __tablename__ = "orders"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="orders_status_check"),
        CheckConstraint("total_amount >= 0", name="orders_total_amount_check"),
        CheckConstraint("shipping_fee >= 0", name="orders_shipping_fee_check"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    address_id: UUID | None = Field(
        default=None, foreign_key="user_addresses.id", ondelete="SET NULL", index=True
    )
    items: list["OrderItem"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    hidden_by_user: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    total_amount: Decimal = Field(sa_type=Numeric(12, 0))
    shipping_fee: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 0))
    status: str = Field(default=OrderStatus.PENDING.value)
    note: str | None = None
    tracking_code: str | None = None
    shipping_provider: str | None = None

    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utcnow},
    )
