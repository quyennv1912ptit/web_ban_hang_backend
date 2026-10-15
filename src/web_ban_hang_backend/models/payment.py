from enum import Enum  # Import thêm Enum từ thư viện chuẩn của Python
from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from sqlalchemy import Numeric, DateTime
from decimal import Decimal
from datetime import datetime, timezone
# Bỏ import Literal

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

# 1. Chuyển đổi Literal thành class Enum (kế thừa str để lưu vào DB dưới dạng text)
class PaymentMethod(str, Enum):
    COD = "cod"
    VNPAY = "vnpay"
    MOMO = "momo"
    CREDIT_CARD = "credit_card"

class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class Payment(SQLModel, table=True):
    __tablename__ = "payments" # pyright: ignore[reportAssignmentType]
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="orders.id", unique=True, ondelete="CASCADE")
    
    payment_method: PaymentMethod
    # 2. Đặt giá trị mặc định bằng class Enum
    status: PaymentStatus = Field(default=PaymentStatus.UNPAID)
    
    transaction_id: str | None = None
    amount: Decimal = Field(sa_type=Numeric(12, 0))

    # 3. Lưu ý nhỏ: paid_at nên để mặc định là None vì lúc mới tạo đơn chưa được thanh toán
    paid_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    created_at: datetime = Field(
        default_factory=utcnow, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utcnow},
    )