from sqlmodel import SQLModel
from uuid import UUID

class ProductImageRead(SQLModel):
    id: UUID
    image_url: str
    caption: str | None = None
    position: int = 0
    embedding_status: str
    embedding_error: str | None = None
