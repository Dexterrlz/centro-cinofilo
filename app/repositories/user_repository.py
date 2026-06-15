from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id, User.is_active == True).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_google_id(self, google_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.google_id == google_id).first()

    def get_by_verification_token(self, token: str) -> Optional[User]:
        return self.db.query(User).filter(User.verification_token == token).first()

    def create(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password_hash: Optional[str] = None,
        google_id: Optional[str] = None,
        dog_name: Optional[str] = None,
        email_verified: bool = False,
        verification_token: Optional[str] = None,
    ) -> User:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=password_hash,
            google_id=google_id,
            dog_name=dog_name,
            email_verified=email_verified,
            verification_token=verification_token,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def verify_email(self, user: User) -> User:
        user.email_verified = True
        user.verification_token = None
        self.db.commit()
        self.db.refresh(user)
        return user

    def link_google(self, user: User, google_id: str) -> User:
        user.google_id = google_id
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_appointments_by_user(self, user_id: int, statuses: list) -> list:
        from app.models.appointment import Appointment
        from sqlalchemy.orm import joinedload
        return (
            self.db.query(Appointment)
            .options(joinedload(Appointment.discipline))
            .filter(
                Appointment.user_id == user_id,
                Appointment.status.in_(statuses),
            )
            .order_by(Appointment.appointment_date.asc(), Appointment.start_time.asc())
            .all()
        )

    def exists(self) -> bool:
        return self.db.query(User).count() > 0
