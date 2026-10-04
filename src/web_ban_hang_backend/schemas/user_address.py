from sqlmodel import SQLModel
from uuid import UUID
from datetime import datetime

class UserAddressRead(SQLModel):
    id: UUID
    user_id: UUID
    receiver_name: str
    phone: str
    address_line: str
    ward: str | None = None
    district: str | None = None
    city: str | None = None
    is_default: bool = False
    created_at: datetime
    updated_at: datetime

class UserAddressRequest(SQLModel):
    receiver_name: str
    phone: str
    address_line: str
    ward: str | None = None
    district: str | None = None
    city: str | None = None
    is_default: bool = False
