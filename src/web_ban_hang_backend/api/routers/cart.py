from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from web_ban_hang_backend.core.auth import CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.cart import Cart
from web_ban_hang_backend.models.cart_item import CartItem
from web_ban_hang_backend.models.product import Product

router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
    responses={404: {"description": "Not found"}},
)

class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=100)

class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100)

def get_user_cart(session: SessionDep, user_id: UUID, *, create: bool) -> Cart | None:
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id).with_for_update()
    ).first()
    if cart is not None or not create:
        return cart

    cart = Cart(user_id=user_id)
    session.add(cart)
    try:
        session.flush()
    except IntegrityError:
        # Another request may have created this user's unique cart concurrently.
        session.rollback()
        cart = session.exec(
            select(Cart).where(Cart.user_id == user_id).with_for_update()
        ).first()
        if cart is None:
            raise
    return cart

@router.get("/")
def get_all_products_in_cart(current_user: CurrentUser, session: SessionDep):
    """Lấy các sản phẩm trong giỏ"""
    cart = get_user_cart(session, current_user.id, create=False)
    if cart is None:
        return []
    return session.exec(select(CartItem).where(CartItem.cart_id == cart.id)).all()

@router.post("/", status_code=status.HTTP_201_CREATED)
def add_products_to_cart(
    data: CartItemCreate, current_user: CurrentUser, session: SessionDep
):
    product = session.get(Product, data.product_id)
    if not product or not product.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không tồn tại hoặc đã ngừng bán")

    cart = get_user_cart(session, current_user.id, create=True)
    assert cart is not None
    item = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == data.product_id,
        )
    ).first()

    new_quantity = item.quantity + data.quantity if item else data.quantity
    
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
def update_products_in_cart(
    product_id: UUID,
    data: CartItemUpdate,
    current_user: CurrentUser,
    session: SessionDep,
):
    """Đổi số lượng, kiểm tra tồn kho."""
    cart = get_user_cart(session, current_user.id, create=False)
    if cart is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Giỏ hàng trống")

    item = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    ).first()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không có trong giỏ hàng")

    product = session.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không tồn tại hoặc đã ngừng bán")
        
    stock = product.stock_quantity
    if data.quantity > stock:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm không đủ số lượng tồn kho")

    item.quantity = data.quantity
    session.commit()
    session.refresh(item)
    return item

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_products_from_cart(
    product_id: UUID, current_user: CurrentUser, session: SessionDep
):
    """Xóa một sản phẩm khỏi giỏ."""
    cart = get_user_cart(session, current_user.id, create=False)
    if cart is None:
        return
    item = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    ).first()
    if item:
        session.delete(item)
        session.commit()

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(current_user: CurrentUser, session: SessionDep):
    """Xóa toàn bộ giỏ hàng, gọi sau khi đặt hàng thành công."""
    cart = get_user_cart(session, current_user.id, create=False)
    if cart is None:
        return
    items = session.exec(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    for item in items:
        session.delete(item)
    session.commit()