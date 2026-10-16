from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from uuid import UUID

# Import các dependency và model theo cấu trúc thư mục của ông
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.core.auth import get_current_user
from web_ban_hang_backend.models.product import Product
# Import file chứa model UserFavorite vừa tạo
from web_ban_hang_backend.models.user_favorite import UserFavorite

router = APIRouter(prefix="/favorites", tags=["Favorites"])

@router.get("/")
def get_user_favorites(session: SessionDep, current_user = Depends(get_current_user)):
    """Lấy danh sách sản phẩm yêu thích của user đang đăng nhập"""
    statement = (
        select(Product)
        .join(UserFavorite, UserFavorite.product_id == Product.id)
        .where(UserFavorite.user_id == current_user.id)
    )
    products = session.exec(statement).all()
    return products

@router.post("/{product_id}/toggle")
def toggle_favorite(product_id: UUID, session: SessionDep, current_user = Depends(get_current_user)):
    """Thả tim/Bỏ thả tim sản phẩm"""
    # 1. Kiểm tra sản phẩm có tồn tại không
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

    # 2. Tìm xem user đã yêu thích sản phẩm này chưa
    statement = select(UserFavorite).where(
        UserFavorite.user_id == current_user.id, 
        UserFavorite.product_id == product_id
    )
    existing_favorite = session.exec(statement).first()

    # 3. Xử lý Toggle (Có rồi thì xóa, chưa có thì thêm)
    if existing_favorite:
        session.delete(existing_favorite)
        session.commit()
        return {"message": "Đã bỏ khỏi danh sách yêu thích", "is_favorited": False}
    else:
        new_favorite = UserFavorite(user_id=current_user.id, product_id=product_id)
        session.add(new_favorite)
        session.commit()
        return {"message": "Đã thêm vào danh sách yêu thích", "is_favorited": True}