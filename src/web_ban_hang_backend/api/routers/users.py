from fastapi import APIRouter
from web_ban_hang_backend.schemas.user import UserSync, UserRead
from web_ban_hang_backend.core.auth import TokenDep, CurrentUser
from web_ban_hang_backend.core.database import SessionDep
from sqlmodel import select
from web_ban_hang_backend.models.user import User
from sqlalchemy.exc import IntegrityError

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
            # Request khác vừa tạo user này trước ta: rollback rồi đọc lại
            session.rollback()
            user = session.exec(select(User).where(User.firebase_uid == uid)).one()
        else:
            session.refresh(user)

    return user

@router.get("/me", response_model=UserRead)
def get_user_info(current_user: CurrentUser):
    return current_user


@router.get("/addresses")
async def get_user_addresses():
    pass

@router.post("/addresses")
async def add_user_addresses():
    pass

@router.put("/addresses/{address_id}")
async def update_user_addresses(address_id: str):
    pass

@router.delete("/addresses/{address_id}")
async def delete_user_addresses(address_id: str):
    pass


@router.get("/favorites")
async def get_user_favorites():
    pass

@router.post("/favorites/{product_id}")
async def add_user_favorites(product_id: str):
    pass

@router.delete("/favorites/{product_id}")
async def delete_user_favorites(product_id: str):
    pass