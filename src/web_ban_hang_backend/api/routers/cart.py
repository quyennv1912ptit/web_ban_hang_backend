from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.cart_item import CartItem
from web_ban_hang_backend.models.product import Product

router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
    responses={404: {"description": "Not found"}},
)

# Schemas để nhận dữ liệu từ request body
class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int


@router.get("/")
def get_all_products_in_cart(current_user: CurrentUser, session: SessionDep):
    """Lấy các sản phẩm trong giỏ, kèm giá và tồn kho hiện tại (thông qua relationship)."""
    items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()
    return items


@router.post("/", status_code=status.HTTP_201_CREATED)
def add_products_to_cart(data: CartItemCreate, current_user: CurrentUser, session: SessionDep):
    """Thêm sản phẩm (product_id, quantity), cộng dồn nếu đã có."""
    product = session.get(Product, data.product_id)
    if not product or not product.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không tồn tại hoặc đã ngừng bán")
    
    # Kiểm tra xem sản phẩm đã có trong giỏ hàng chưa
    item = session.exec(
        select(CartItem).where(
            CartItem.user_id == current_user.id, 
            CartItem.product_id == data.product_id
        )
    ).first()

    # Tính toán số lượng mới
    new_quantity = (item.quantity + data.quantity) if item else data.quantity
    
    # Kiểm tra tồn kho
    if new_quantity > product.stock_quantity:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vượt quá số lượng tồn kho của sản phẩm")

    if item:
        item.quantity = new_quantity
    else:
        item = CartItem(user_id=current_user.id, product_id=data.product_id, quantity=data.quantity)
        session.add(item)
    
    session.commit()
    session.refresh(item)
    return item


@router.put("/{product_id}")
def update_products_in_cart(product_id: UUID, data: CartItemUpdate, current_user: CurrentUser, session: SessionDep):
    """Đổi số lượng, kiểm tra tồn kho."""
    item = session.exec(
        select(CartItem).where(
            CartItem.user_id == current_user.id, 
            CartItem.product_id == product_id
        )
    ).first()
    
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không có trong giỏ hàng")

    # Kiểm tra tồn kho
    product = session.get(Product, product_id)
    if data.quantity > product.stock_quantity:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không đủ số lượng tồn kho")

    item.quantity = data.quantity
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_products_from_cart(product_id: UUID, current_user: CurrentUser, session: SessionDep):
    """Xóa một sản phẩm khỏi giỏ."""
    item = session.exec(
        select(CartItem).where(
            CartItem.user_id == current_user.id, 
            CartItem.product_id == product_id
        )
    ).first()
    
    if item:
        session.delete(item)
        session.commit()


# Route này được bổ sung theo requirement ban đầu để xóa toàn bộ giỏ khi đặt hàng thành công
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(current_user: CurrentUser, session: SessionDep):
    """Xóa toàn bộ giỏ hàng, gọi sau khi đặt hàng thành công."""
    items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()
    
    for item in items:
        session.delete(item)
    session.commit()