from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Numeric

class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items" # pyright: ignore[reportAssignmentType]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="orders.id", ondelete="CASCADE", index=True)
    product_id: UUID | None = Field(foreign_key="products.id", ondelete="SET NULL", index=True)
    product_name: str
    quantity: int = 1
    price: Decimal = Field(sa_type=Numeric(12, 0))
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))