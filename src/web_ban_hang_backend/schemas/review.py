from sqlmodel import SQLModel, Field
from uuid import UUID
from datetime import datetime


class ReviewCreate(SQLModel):
    order_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewUpdate(SQLModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewRead(SQLModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    order_id: UUID
    rating: int
    comment: str | None = None
    created_at: datetime
    updated_at: datetime