from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import StringConstraints
from sqlmodel import Field, SQLModel

PhoneNumber = Annotated[str, StringConstraints(pattern=r"^(0|\+84)\d{9}$")]

class UserSync(SQLModel):
    display_name: str | None = Field(default=None, max_length=100)
    phone_number: PhoneNumber | None = None

class UserRead(SQLModel):
    id: UUID
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None
    role: str
    created_at: datetime