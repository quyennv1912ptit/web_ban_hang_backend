from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import DateTime, UniqueConstraint

class Review(SQLModel, table=True):
    __tablename__ = "reviews" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "order_id", name="reiews_user_id_product_id_order_id_key")
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    product_id: UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    order_id: UUID | None = Field(foreign_key="orders.id", ondelete="SET NULL", index=True)
    rating: int
    comment: str | None = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))