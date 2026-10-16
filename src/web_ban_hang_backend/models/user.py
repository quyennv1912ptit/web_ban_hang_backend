import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, text
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        CheckConstraint("role IN ('customer', 'admin')", name="users_role_check"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    firebase_uid: str = Field(unique=True, index=True)
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None
    role: str = Field(default="customer")
    is_active: bool = Field(
        default=True, sa_column_kwargs={"server_default": text("true")}
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )