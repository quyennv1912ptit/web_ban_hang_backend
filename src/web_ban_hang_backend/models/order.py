from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import DateTime, Numeric
from decimal import Decimal

class Order(SQLModel, table=True):
    __tablename__ = "orders" # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    addreess_id: UUID | None = Field(foreign_key="user_addresses.id", ondelete="SET NULL", index=True)
    total_amount: Decimal = Field(sa_type=Numeric(12, 0))
    shipping_fee: Decimal = Field(default=0, sa_type=Numeric(12, 0))
    status: str = "pending"
    note: str | None = None
    tracking_code: str | None = None
    shipping_provider: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))