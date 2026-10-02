from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from sqlalchemy import Numeric, DateTime
from decimal import Decimal
from datetime import datetime, timezone
from typing import Literal

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

PaymentMethod = Literal["cod", "vnpay", "momo", "credit_card"]
PaymentStatus = Literal["unpaid", "processing", "completed", "failed", "refunded"]

class Payment(SQLModel, table=True):
    __tablename__ = "payments" # pyright: ignore[reportAssignmentType]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="orders.id", unique=True, ondelete="CASCADE")
    payment_method: PaymentMethod
    status: PaymentStatus = "unpaid"
    transaction_id: str | None = None
    amount: Decimal = Field(sa_type=Numeric(12, 0))

    paid_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))

    created_at: datetime = Field(
        default_factory=utcnow, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utcnow},
    )