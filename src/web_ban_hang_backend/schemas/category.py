from sqlmodel import SQLModel
from typing import Optional

class CategoryRead(SQLModel):
    id: int
    name: str
    slug: str
    parent_id: int | None
    icon: str | None = None

class CategoryCreate(SQLModel):
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None