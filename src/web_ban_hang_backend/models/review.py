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
        CheckConstraint("rating BETWEEN 1 AND 5", name="reviews_rating_check"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    product_id: UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    # DB cho phép NULL và đặt SET NULL khi xóa đơn -> kiểu phải là Optional.
    # Nếu muốn bắt buộc "chỉ review khi đã mua", kiểm tra ở tầng API.
    order_id: UUID | None = Field(
        default=None, foreign_key="orders.id", ondelete="SET NULL", index=True
    )
    rating: int
    comment: str | None = None

    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utcnow},
    )