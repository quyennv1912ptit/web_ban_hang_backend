import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from web_ban_hang_backend.core.auth import CurrentUser, TokenDep
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.user import User
from web_ban_hang_backend.models.user_address import UserAddress
from web_ban_hang_backend.models.user_favorite import UserFavorite
from web_ban_hang_backend.schemas.user import UserRead, UserSync
from web_ban_hang_backend.schemas.user_address import (
    UserAddressRead,
    UserAddressRequest,
)
from web_ban_hang_backend.schemas.user_favorite import UserFavoriteRead

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)


@router.post("/sync", response_model=UserRead)
def sync_user_profile(data: UserSync, decoded: TokenDep, session: SessionDep):
    uid = decoded["uid"]
    user = session.exec(select(User).where(User.firebase_uid == uid)).first()

    if user is None:
        user = User(
            firebase_uid=uid,
            email=decoded.get("email"),
            display_name=data.display_name or decoded.get("name"),
            photo_url=decoded.get("picture"),
            phone_number=data.phone_number or decoded.get("phone_number"),
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            user = session.exec(select(User).where(User.firebase_uid == uid)).one()
        else:
            session.refresh(user)

    return user


@router.get("/me", response_model=UserRead)
def get_user_info(current_user: CurrentUser):
    return current_user


def _get_own_address(session, user_id, address_id: UUID, action: str) -> UserAddress:
    address = session.exec(
        select(UserAddress).where(
            UserAddress.user_id == user_id,
            UserAddress.id == address_id,
        )
    ).first()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy địa chỉ hoặc không có quyền {action}",
        )
    return address


@router.get("/addresses", response_model=list[UserAddressRead])
def get_user_addresses(current_user: CurrentUser, session: SessionDep):
    return session.exec(
        select(UserAddress).where(UserAddress.user_id == current_user.id)
    ).all()


@router.post(
    "/addresses",
    response_model=UserAddressRead,
    status_code=status.HTTP_201_CREATED,
)
def add_user_addresses(
    data: UserAddressRequest, current_user: CurrentUser, session: SessionDep
):
    address = UserAddress(**data.model_dump(), user_id=current_user.id)
    session.add(address)

    try:
        session.commit()
        session.refresh(address)
        return address
    except Exception:
        session.rollback()
        logger.exception("Lỗi thêm địa chỉ")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tạo địa chỉ. Vui lòng thử lại!",
        )


@router.put("/addresses/{address_id}", response_model=UserAddressRead)
def update_user_addresses(
    address_id: UUID,
    data: UserAddressRequest,
    current_user: CurrentUser,
    session: SessionDep,
):
    address = _get_own_address(session, current_user.id, address_id, "sửa")

    address.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(address)

    try:
        session.commit()
        session.refresh(address)
        return address
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi cập nhật địa chỉ")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể cập nhật địa chỉ. Vui lòng thử lại!",
        )


@router.delete("/addresses/{address_id}")
def delete_user_addresses(
    address_id: UUID, current_user: CurrentUser, session: SessionDep
):
    address = _get_own_address(session, current_user.id, address_id, "xóa")

    session.delete(address)
    try:
        session.commit()
        return {"message": "Xóa địa chỉ thành công", "id": address_id}
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi xóa địa chỉ")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa địa chỉ. Vui lòng thử lại!",
        )


@router.get("/favorites", response_model=list[UserFavoriteRead])
def get_user_favorites(current_user: CurrentUser, session: SessionDep):
    return session.exec(
        select(UserFavorite).where(UserFavorite.user_id == current_user.id)
    ).all()


@router.post(
    "/favorites/{product_id}",
    response_model=UserFavoriteRead,
    status_code=status.HTTP_201_CREATED,
)
def add_user_favorites(
    product_id: UUID, current_user: CurrentUser, session: SessionDep
):
    user_favorite = UserFavorite(user_id=current_user.id, product_id=product_id)
    session.add(user_favorite)

    try:
        session.commit()
        session.refresh(user_favorite)
        return user_favorite
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sản phẩm đã có trong mục yêu thích hoặc không tồn tại",
        )
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi thêm sản phẩm vào mục yêu thích")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể thêm sản phẩm vào mục yêu thích. Vui lòng thử lại!",
        )


@router.delete("/favorites/{product_id}")
def delete_user_favorites(
    product_id: UUID, current_user: CurrentUser, session: SessionDep
):
    user_favorite = session.exec(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.product_id == product_id,
        )
    ).first()

    if not user_favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sản phẩm không có trong mục yêu thích",
        )

    session.delete(user_favorite)
    try:
        session.commit()
        return {
            "message": "Xóa sản phẩm khỏi mục yêu thích thành công",
            "id": product_id,
        }
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi xóa sản phẩm khỏi mục yêu thích")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa sản phẩm khỏi mục yêu thích. Vui lòng thử lại!",
        )