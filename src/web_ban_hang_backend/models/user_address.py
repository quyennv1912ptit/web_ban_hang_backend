from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import DateTime

class UserAddress(SQLModel, table=True):
    __tablename__ = "user_addresses" # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    receiver_name: str
    phone: str
    address_line: str
    ward: str | None = None
    district: str | None = None
    city: str | None = None
    is_default: bool = False

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
