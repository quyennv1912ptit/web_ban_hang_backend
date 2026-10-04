from sqlmodel import SQLModel
from uuid import UUID

class ProductImageRead(SQLModel):
    id: UUID
    product_id: UUID
    original_url: str
    cropped_url: str | None = None
    caption: str | None = None
    position: int = 0