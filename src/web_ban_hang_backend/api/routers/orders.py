from fastapi import APIRouter, Query, HTTPException, status
from sqlmodel import select, col
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from uuid import UUID
from decimal import Decimal
from collections import defaultdict
import logging
from typing import Optional

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.payment import Payment, PaymentStatus, PaymentMethod # Cần import model Payment
from web_ban_hang_backend.schemas.order import OrderRead, OrderDetail, OrderRequest
from web_ban_hang_backend.schemas.order_item import OrderItemRead, OrderItemCreate
from web_ban_hang_backend.models.order_item import OrderItem
from web_ban_hang_backend.models.user_address import UserAddress
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
    responses={404: {"description": "Not found"}},
)

# --- Thêm Schema mới cho Cập nhật đơn hàng và Tạo đơn hàng ---
class OrderUpdateSchema(BaseModel):
    address_id: Optional[UUID] = None
    note: Optional[str] = None

class CreateOrderRequest(OrderRequest):
    payment_method: PaymentMethod = PaymentMethod.COD

# --- GET /orders ---
@router.get("/", response_model=Page[OrderRead])
def get_orders_history(current_user: CurrentUser, session: SessionDep, order_status: OrderStatus | None = Query(default=None, alias="status")):
    # Đã thêm lọc hidden_by_user == False
    query = select(Order).where(Order.user_id == current_user.id, Order.hidden_by_user == False)
    if order_status:
        query = query.where(Order.status == order_status.value)
    query = query.order_by(col(Order.created_at).desc(), col(Order.id))
    
    return paginate(session, query) # type: ignore


@router.get("/{order_id}", response_model=OrderDetail)
def get_order_info(order_id: UUID, current_user: CurrentUser, session: SessionDep):
    order = session.exec(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    ).first()
    
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn đặt hàng")
        
    return OrderDetail(
        **order.model_dump(),
        items=[OrderItemRead.model_validate(item) for item in order.items]
    )

# --- POST /orders ---
@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(data: CreateOrderRequest, current_user: CurrentUser, session: SessionDep):
    address = session.exec(
        select(UserAddress)
        .where(
            UserAddress.user_id == current_user.id,
            UserAddress.id == data.address_id
        )
    ).first()

    if not address:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy địa chỉ giao hàng")

    # Gộp các dòng trùng sản phẩm
    quantities: dict[UUID, int] = defaultdict(int)
    for item in data.items:
        quantities[item.product_id] += item.quantity
        
    products = session.exec(
        select(Product)
        .where(col(Product.id).in_(list(quantities)))
        .order_by(col(Product.id))
        .with_for_update()
    ).all()
    
    if len(products) != len(quantities):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Có sản phẩm không tồn tại")

    order = Order(
        user_id=current_user.id,
        address_id=address.id,
        total_amount=Decimal("0"),
        shipping_fee=Decimal("0"), # Sẽ tính lại bên dưới
        note=data.note,
    )
    
    order_items: list[OrderItem] = []
    subtotal = Decimal("0")
    
    products_dict = {p.id: p for p in products}
    
    for product_id, qty in quantities.items():
        product = products_dict.get(product_id)
        if not product or not product.is_active:
             raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Sản phẩm '{product.name if product else product_id}' hiện không bán"
            )
        if product.stock_quantity < qty:
             raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Sản phẩm '{product.name}' không đủ hàng"
            )
            
        product.stock_quantity -= qty
        session.add(product)
        order_items.append(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                quantity=qty,
                price=product.price,
            )
        )
        subtotal += product.price * qty

    # Logic tính phí ship: miễn phí nếu đơn từ 199K
    shipping_fee = Decimal("0") if subtotal >= Decimal("199000") else Decimal("30000")
    order.shipping_fee = shipping_fee
    order.total_amount = subtotal + shipping_fee

    session.add(order)
    session.add_all(order_items)
    session.flush() # Flush để lấy order.id cho Payment
    
    # Tạo bản ghi Payment
    payment = Payment(
        order_id=order.id,
        amount=order.total_amount,
        payment_method=data.payment_method,
        status=PaymentStatus.PENDING
    )
    session.add(payment)

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi tạo đơn hàng")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Không thể tạo đơn hàng. Vui lòng thử lại!"
        )
        
    session.refresh(order)
    return order

# --- PUT /orders/{order_id} ---
@router.put("/{order_id}", response_model=OrderRead, status_code=status.HTTP_200_OK)
def update_order_info(data: OrderUpdateSchema, current_user: CurrentUser, session: SessionDep, order_id: UUID):
    order = session.exec(
        select(Order)
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id
        )
    ).first()
    
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn hàng")
        
    if order.status != OrderStatus.PENDING.value:
         raise HTTPException(
            status.HTTP_409_CONFLICT, "Chỉ có thể sửa đơn hàng đang chờ xử lý"
        )
         
    if data.address_id:
        address = session.exec(
            select(UserAddress)
            .where(
                UserAddress.id == data.address_id,
                UserAddress.user_id == current_user.id
            )
        ).first()
        if not address:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy địa chỉ giao hàng")
        order.address_id = data.address_id
        
    if data.note is not None:
        order.note = data.note

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi tạo đơn hàng")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Không thể sửa đơn hàng. Vui lòng thử lại!"
        )

    session.refresh(order)
    return order


@router.post("/{order_id}/cancel", response_model=OrderRead)
def cancel_pending_order(order_id: UUID, current_user: CurrentUser, session: SessionDep):
    order = session.exec(
        select(Order)
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id
        )
    ).first()
    
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn hàng")
        
    if order.status != OrderStatus.PENDING.value:
         raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ có thể hủy đơn hàng đang chờ"
        )
         
    items = session.exec(
        select(OrderItem)
        .where(
            OrderItem.order_id == order.id
        )
    ).all()
    
    product_ids = [i.product_id for i in items if i.product_id]
    
    products = {
        p.id: p
        for p in session.exec(
            select(Product)
            .where(col(Product.id).in_(product_ids))
            .order_by(col(Product.id))
            .with_for_update() # Khóa các dòng này cho đến khi transaction kết thúc
        ).all()
    }
    
    for item in items:
        product = products.get(item.product_id) if item.product_id else None
        if product:
            product.stock_quantity += item.quantity
            
    order.status = OrderStatus.CANCELLED.value
    
    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi hủy đơn hàng")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Không thể hủy đơn hàng. Vui lòng thử lại!"
        )
        
    session.refresh(order)
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def hide_order(order_id: UUID, current_user: CurrentUser, session: SessionDep):
    order = session.exec(
        select(Order)
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id
        )
    ).first()
    
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn hàng")
        
    if order.status not in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ có thể xóa đơn đã giao hoặc đã hủy. Với đơn đang xử lý, hãy hủy đơn trước."
        )
        
    order.hidden_by_user = True
    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi xóa đơn hàng")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Không thể xóa đơn hàng. Vui lòng thử lại!")


# --- POST /orders/{order_id}/pay (MỚI) ---
@router.post("/{order_id}/pay")
def mock_pay_order(order_id: UUID, current_user: CurrentUser, session: SessionDep):
    """Giả lập thanh toán: đánh dấu Payment là đã trả."""
    order = session.exec(select(Order).where(Order.id == order_id, Order.user_id == current_user.id)).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn đặt hàng")
    
    payment = session.exec(select(Payment).where(Payment.order_id == order.id)).first()
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy thông tin thanh toán")

    payment.status = PaymentStatus.PAID
    order.status = OrderStatus.PROCESSING.value  # Đổi trạng thái đơn để bắt đầu chuẩn bị hàng
    
    session.commit()
    return {"message": "Thanh toán giả lập thành công"}