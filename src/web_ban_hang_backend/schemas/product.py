from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import SQLModel, Field

from web_ban_hang_backend.schemas.category import CategoryRead
from web_ban_hang_backend.schemas.product_image import ProductImageRead

class ProductRead(SQLModel):
    id: UUID
    category_id: int | None = None
    name: str
    slug: str
    description: str | None = None
    price: Decimal
    original_price: Decimal | None = None

    attributes: dict[str, Any] = Field(default_factory=dict)

    is_active: bool = True
    stock_quantity: int = 0
    sold_count: int = 0
    average_rating: Decimal = Decimal("0")
    sku: str | None = None
    weight_grams: int = 0

    category: CategoryRead | None = None
    images: list[ProductImageRead] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime
    
from decimal import Decimal
from typing import Any
from sqlmodel import SQLModel, Field

class ProductCreate(SQLModel):
    category_id: int
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)

    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    original_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)

    attributes: dict[str, Any] = Field(default_factory=dict)  # người bán nhập

    stock_quantity: int = Field(default=0, ge=0)
    sku: str | None = Field(default=None, max_length=64)
    weight_grams: int = Field(default=0, ge=0)
    is_active: bool = True