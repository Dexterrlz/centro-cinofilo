from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id, User.is_active == True).first()

    def get_by_id_any(self, user_id: int) -> Optional[User]:
        """Recupera utente indipendentemente dallo stato (per admin)."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: str = "N/A",
        password_hash: Optional[str] = None,
        dog_name: Optional[str] = None,
        is_active: bool = False,
    ) -> User:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            dog_name=dog_name,
            email_verified=True,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_appointments_by_user(self, user_id: int, statuses: list) -> list:
        from app.models.appointment import Appointment
        return (
            self.db.query(Appointment)
            .options(joinedload(Appointment.discipline), joinedload(Appointment.instructor))
            .filter(
                Appointment.user_id == user_id,
                Appointment.status.in_(statuses),
            )
            .order_by(Appointment.appointment_date.asc(), Appointment.start_time.asc())
            .all()
        )

    def get_all_with_packages(self) -> List[User]:
        """Tutti gli utenti con pacchetti precaricati, ordinati per data registrazione decrescente."""
        return (
            self.db.query(User)
            .options(joinedload(User.packages))
            .order_by(User.created_at.desc())
            .all()
        )

    def approve(self, user: User) -> User:
        user.is_active = True
        if user.approved_at is None:
            user.approved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def disable(self, user: User) -> User:
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_all_active(self) -> List[User]:
        return (
            self.db.query(User)
            .filter(User.is_active == True)
            .order_by(User.last_name, User.first_name)
            .all()
        )

    def exists(self) -> bool:
        return self.db.query(User).count() > 0
