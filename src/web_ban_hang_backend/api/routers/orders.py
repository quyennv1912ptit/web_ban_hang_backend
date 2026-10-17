from fastapi import APIRouter, Query, HTTPException, status
from sqlmodel import select, col
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from uuid import UUID
from decimal import Decimal
from collections import defaultdict
import logging
from typing import Optional
from datetime import datetime, timezone

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.order import Order, OrderStatus
from web_ban_hang_backend.models.payment import Payment, PaymentStatus, PaymentMethod
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

class OrderUpdateSchema(BaseModel):
    address_id: Optional[UUID] = None
    note: Optional[str] = None

class CreateOrderRequest(OrderRequest):
    payment_method: PaymentMethod = PaymentMethod.COD

@router.get("/", response_model=Page[OrderRead])
def get_orders_history(current_user: CurrentUser, session: SessionDep, order_status: OrderStatus | None = Query(default=None, alias="status")):
    query = select(Order).where(Order.user_id == current_user.id)
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
        shipping_fee=Decimal("0"),
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
        product.sold_count += qty
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

    shipping_fee = Decimal("0") if subtotal >= Decimal("199000") else Decimal("30000")
    order.shipping_fee = shipping_fee
    order.total_amount = subtotal + shipping_fee

    try:
        session.add(order)
        session.add_all(order_items)
        session.flush()

        payment = Payment(
            order_id=order.id,
            amount=order.total_amount,
            payment_method=data.payment_method.value,
            status=PaymentStatus.UNPAID.value,
        )
        session.add(payment)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi tạo đơn hàng")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Không thể tạo đơn hàng. Vui lòng thử lại!"
        )
        
    session.refresh(order)
    return order

@router.put("/{order_id}", response_model=OrderRead, status_code=status.HTTP_200_OK)
def update_order_info(data: OrderUpdateSchema, current_user: CurrentUser, session: SessionDep, order_id: UUID):
    order = session.exec(
        select(Order)
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id
        )
        .with_for_update()
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
        .with_for_update()
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
            .with_for_update() 
        ).all()
    }
    
    for item in items:
        product = products.get(item.product_id) if item.product_id else None
        if product:
            product.stock_quantity += item.quantity
            product.sold_count = max(0, product.sold_count - item.quantity)
            
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
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Database hiện không có cột ẩn đơn hàng; thao tác này chưa được hỗ trợ.",
    )

@router.post("/{order_id}/pay")
def mock_pay_order(order_id: UUID, current_user: CurrentUser, session: SessionDep):
    """Giả lập thanh toán: đánh dấu Payment là đã trả."""
    order = session.exec(
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
    ).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy đơn đặt hàng")
    
    payment = session.exec(
        select(Payment).where(Payment.order_id == order.id).with_for_update()
    ).first()
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy thông tin thanh toán")

    if payment.status == PaymentStatus.COMPLETED.value:
        return {"message": "Đơn hàng đã được thanh toán"}
    if order.status != OrderStatus.PENDING.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Chỉ có thể thanh toán đơn hàng đang chờ xử lý",
        )
    if payment.payment_method == PaymentMethod.COD.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Đơn hàng thanh toán khi nhận hàng không cần thanh toán trực tuyến",
        )
    if payment.status != PaymentStatus.UNPAID.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Trạng thái thanh toán hiện tại không thể thanh toán",
        )

    payment.status = PaymentStatus.COMPLETED.value
    payment.paid_at = datetime.now(timezone.utc)
    order.status = OrderStatus.PROCESSING.value
    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi thanh toán đơn hàng")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Không thể thanh toán đơn hàng. Vui lòng thử lại!",
        )
    return {"message": "Thanh toán giả lập thành công"}