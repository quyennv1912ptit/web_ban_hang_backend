from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


_METHOD_VALUES = ", ".join(f"'{m.value}'" for m in PaymentMethod)
_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in PaymentStatus)


class Payment(SQLModel, table=True):
    __tablename__ = "payments"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        CheckConstraint(
            f"payment_method IN ({_METHOD_VALUES})", name="payments_payment_method_check"
        ),
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="payments_status_check"),
        CheckConstraint("amount >= 0", name="payments_amount_check"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="orders.id", unique=True, ondelete="CASCADE")

    # Cột DB là TEXT + CHECK nên model lưu str thường (giống Order.status).
    # Nếu khai báo kiểu Enum, SQLModel sẽ dùng kiểu enum của SQLAlchemy và ghi TÊN
    # thành viên ("COD") thay vì giá trị ("cod") -> vi phạm CHECK của DB.
    # Dùng PaymentMethod / PaymentStatus ở schema API để kiểm tra đầu vào.
    payment_method: str
    status: str = Field(default=PaymentStatus.UNPAID.value)

    transaction_id: str | None = None
    amount: Decimal = Field(sa_type=Numeric(12, 0))
    paid_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utcnow},
    )