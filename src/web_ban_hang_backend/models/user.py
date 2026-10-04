from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from sqlalchemy import DateTime
import uuid

class User(SQLModel, table=True):
    __tablename__ = "users"  # pyright: ignore[reportAssignmentType]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    firebase_uid: str = Field(unique=True, index=True)
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None
    role: str = Field(default="customer")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True)
    )