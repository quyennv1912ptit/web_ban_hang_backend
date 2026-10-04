from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "user_id", "product_id", "order_id",
            name="reviews_user_id_product_id_order_id_key",
        ),
        CheckConstraint("rating BETWEEN 1 AND 5", name="reviews_rating_range"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    product_id: UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    order_id: UUID = Field(foreign_key="orders.id")
    rating: int
    comment: str | None = None

    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utcnow},
    )