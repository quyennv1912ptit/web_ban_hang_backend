from sqlmodel import SQLModel, Field
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import DateTime

class UserFavorite(SQLModel, table=True):
    __tablename__ = "user_favorites" # pyright: ignore[reportAssignmentType]

    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", primary_key=True)
    product_id: UUID = Field(foreign_key="products.id", ondelete="CASCADE", primary_key=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))