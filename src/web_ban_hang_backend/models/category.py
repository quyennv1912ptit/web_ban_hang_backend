from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from web_ban_hang_backend.models.product import Product


class Category(SQLModel, table=True):
    __tablename__ = "categories"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)
    parent_id: int | None = Field(
        default=None, foreign_key="categories.id", ondelete="SET NULL", index=True
    )
    
    icon: str | None = None

    products: list["Product"] = Relationship(back_populates="category")