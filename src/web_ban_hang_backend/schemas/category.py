from sqlmodel import SQLModel

class CategoryRead(SQLModel):
    id: int
    name: str
    slug: str
    parent_id: int | None
    icon: str | None = None