import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from web_ban_hang_backend.models.product import Product

IMAGE_EMBED_DIM = 1024

class ProductImage(SQLModel, table=True):
    __tablename__ = "product_images"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "product_id", "position",
            name="product_images_product_id_position_key",
            deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="product_images_position_check"),
        CheckConstraint(
            "embedding_status IN ('pending', 'indexed', 'failed')",
            name="product_images_embedding_status_check",
        ),
        CheckConstraint(
            "embedding_status <> 'indexed' OR multimodal_embedding IS NOT NULL",
            name="product_images_indexed_has_vector_check",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    image_url: str
    caption: str | None = None
    position: int = 0

    storage_key: str | None = None
    multimodal_embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(IMAGE_EMBED_DIM))
    )
    embedding_status: str = Field(
        default="pending", sa_column_kwargs={"server_default": "pending"}
    )
    embedding_model: str | None = None
    embedding_error: str | None = None
    indexed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )

    product: "Product" = Relationship(back_populates="images")
