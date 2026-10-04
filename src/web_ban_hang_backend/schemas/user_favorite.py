from sqlmodel import SQLModel
from uuid import UUID
from datetime import datetime

class UserFavoriteRead(SQLModel):
    user_id: UUID
    product_id: UUID
    created_at: datetime
    
