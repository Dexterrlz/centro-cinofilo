from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.admin_user import AdminUser


class AdminUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        return (
            self.db.query(AdminUser)
            .filter(AdminUser.username == username, AdminUser.is_active == True)
            .first()
        )

    def create(self, username: str, password_hash: str) -> AdminUser:
        admin = AdminUser(username=username, password_hash=password_hash)
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        return admin

    def update_last_login(self, admin_id: int) -> None:
        admin = self.db.query(AdminUser).filter(AdminUser.id == admin_id).first()
        if admin:
            admin.last_login = datetime.now(timezone.utc)
            self.db.commit()

    def count(self) -> int:
        return self.db.query(AdminUser).count()
