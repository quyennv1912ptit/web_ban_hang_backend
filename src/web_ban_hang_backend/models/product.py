import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, DateTime, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from web_ban_hang_backend.models.category import Category
    from web_ban_hang_backend.models.product_image import ProductImage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(SQLModel, table=True):
    __tablename__ = "products"  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category_id: int | None = Field(
        default=None, foreign_key="categories.id", ondelete="SET NULL", index=True
    )
    name: str
    slug: str = Field(unique=True, index=True)
    description: str | None = None
    price: Decimal = Field(sa_type=Numeric(12, 0), ge=0)
    original_price: Decimal | None = Field(default=None, sa_type=Numeric(12, 0))

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )

    search_vector: Any | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed(
                "to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(description, ''))",
                persisted=True,
            ),
        ),
    )

    semantic_embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(1024))
    )

    is_active: bool = True
    stock_quantity: int = 0
    sold_count: int = 0
    average_rating: Decimal = Field(default=Decimal("0"), sa_type=Numeric(3, 2))
    sku: str | None = Field(default=None, unique=True)
    weight_grams: int | None = 0

    category: Optional["Category"] = Relationship(back_populates="products")
    images: list["ProductImage"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "passive_deletes": True},
    )
  
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))