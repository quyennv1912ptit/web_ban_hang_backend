from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.cart_item import CartItem
from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.cart import Cart


router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
    responses={404: {"description": "Not found"}},
)

# Schemas để nhận dữ liệu từ request body
class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, gt=0)

class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)

@router.get("/")
def get_all_products_in_cart(current_user: CurrentUser, session: SessionDep):
    """Lấy các sản phẩm trong giỏ"""
    # BƯỚC 1: Tìm Cart của User
    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    if not cart:
        return [] # Nếu chưa có giỏ hàng thì trả về mảng rỗng
        
    # BƯỚC 2: Tìm CartItem bằng cart_id
    items = session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id)
    ).all()
    return items


@router.post("/", status_code=status.HTTP_201_CREATED)
def add_products_to_cart(data: CartItemCreate, current_user: CurrentUser, session: SessionDep):
    """Thêm sản phẩm (product_id, quantity), cộng dồn nếu đã có."""
    product = session.get(Product, data.product_id)
    if not product or not product.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không tồn tại hoặc đã ngừng bán")
        
    # BƯỚC 1: Tìm Cart của User (chưa có thì tạo)
    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        session.add(cart)
        session.commit()
        session.refresh(cart)

    # BƯỚC 2: Kiểm tra xem sản phẩm đã có trong giỏ hàng chưa (dùng cart_id)
    item = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == data.product_id
        )
    ).first()

    # Tính toán số lượng mới
    new_quantity = (item.quantity + data.quantity) if item else data.quantity
    
    # Tồn kho được lưu trực tiếp trong cột stock_quantity.
    stock = product.stock_quantity
    if new_quantity > stock:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Vượt quá số lượng tồn kho (Còn {stock} sản phẩm)")

    if item:
        item.quantity = new_quantity
    else:
        item = CartItem(cart_id=cart.id, product_id=data.product_id, quantity=data.quantity)
        session.add(item)

    session.commit()
    session.refresh(item)
    return item


@router.put("/{product_id}")
def update_products_in_cart(product_id: UUID, data: CartItemUpdate, current_user: CurrentUser, session: SessionDep):
    """Đổi số lượng, kiểm tra tồn kho."""
    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Giỏ hàng trống")

    item = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id
        )
    ).first()

    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không có trong giỏ hàng")

    # Kiểm tra tồn kho từ cột stock_quantity.
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không tồn tại")
    stock = product.stock_quantity
    if data.quantity > stock:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không đủ số lượng tồn kho")

    item.quantity = data.quantity
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_products_from_cart(product_id: UUID, current_user: CurrentUser, session: SessionDep):
    """Xóa một sản phẩm khỏi giỏ."""
    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    if not cart:
        return # Nếu không có giỏ thì không cần làm gì

    item = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id
        )
    ).first()

    if item:
        session.delete(item)
        session.commit()


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(current_user: CurrentUser, session: SessionDep):
    """Xóa toàn bộ giỏ hàng, gọi sau khi đặt hàng thành công."""
    cart = session.exec(select(Cart).where(Cart.user_id == current_user.id)).first()
    if not cart:
        return

    items = session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id)
    ).all()

    for item in items:
        session.delete(item)
        
    session.commit()
