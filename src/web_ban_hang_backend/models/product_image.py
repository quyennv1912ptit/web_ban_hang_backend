import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from web_ban_hang_backend.models.product import Product

class ProductImage(SQLModel, table=True):
    __tablename__ = "product_images"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("product_id", "position"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_id: uuid.UUID = Field(
        foreign_key="products.id", ondelete="CASCADE", index=True
    )
    original_url: str
    cropped_url: str | None = None
    caption: str | None = None
    position: int = 0

    multimodal_embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(768))
    )

    product: "Product" = Relationship(back_populates="images")