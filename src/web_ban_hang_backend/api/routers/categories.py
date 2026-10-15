from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, Session
from typing import List

# Giả định import từ cấu trúc dự án của bạn (bạn cần điều chỉnh lại cho khớp)
from web_ban_hang_backend.core.database import SessionDep
from web_ban_hang_backend.models.category import Category
from web_ban_hang_backend.schemas.category import CategoryRead

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[CategoryRead])
def get_categories(session: SessionDep):
    """
    Lấy danh sách tất cả các danh mục (dành cho trang chủ và menu "Danh mục").
    """
    categories = session.exec(select(Category)).all()
    return categories

@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, session: SessionDep):
    """
    Lấy thông tin chi tiết của một danh mục cụ thể (tên, ảnh, mô tả).
    """
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy danh mục")
    return category