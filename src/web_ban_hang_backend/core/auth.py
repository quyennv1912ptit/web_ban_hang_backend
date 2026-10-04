from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from sqlmodel import select

from .database import SessionDep
from web_ban_hang_backend.models.user import User

bearer = HTTPBearer()

def verify_token(
    cred: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]
) -> dict:
    try:
        return auth.verify_id_token(cred.credentials)
    except Exception as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ"
        ) from e


TokenDep = Annotated[dict, Depends(verify_token)]


def get_current_user(decoded: TokenDep, session: SessionDep) -> User:
    user = session.exec(
        select(User).where(User.firebase_uid == decoded["uid"])
    ).first()

    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Tài khoản không tồn tại hoặc chưa được đồng bộ",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

def get_admin_user(current_user: CurrentUser) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bạn không có quyền truy cập chức năng này"
        )
    return current_user

AdminUser = Annotated[User, Depends(get_admin_user)]