from typing import Optional
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository


class NotAuthenticated(HTTPException):
    def __init__(self):
        super().__init__(status_code=307, detail="Non autenticato")


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return UserRepository(db).get_by_id(user_id)


async def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    user = await get_current_user(request, db)
    if user is None:
        raise NotAuthenticated()
    return user
