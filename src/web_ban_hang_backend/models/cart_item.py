from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import DateTime, UniqueConstraint

class CartItem(SQLModel, table=True):
    __tablename__ = "cart_items" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="cart_items_cart_id_product_id_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cart_id: UUID = Field(foreign_key="carts.id", ondelete="CASCADE", index=True)
    product_id: UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    quantity: int = 1
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))