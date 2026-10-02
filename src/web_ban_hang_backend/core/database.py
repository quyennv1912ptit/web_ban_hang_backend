from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, create_engine

from web_ban_hang_backend.config import settings

engine = create_engine(settings.DB_URL, pool_pre_ping=True)

# Tạo session và tự động giải phóng sau khi đã thao tác với database
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# Tạo dependency
SessionDep = Annotated[Session, Depends(get_session)]