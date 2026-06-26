import logging
from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def register_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        password: str,
        dog_name: Optional[str] = None,
    ) -> dict:
        if self.repo.get_by_email(email):
            return {"success": False, "message": "Esiste gia un account con questa email."}

        user = self.repo.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password_hash=_hash_password(password),
            dog_name=dog_name or None,
            is_active=False,
        )

        logger.info("Nuovo utente registrato (in attesa approvazione): %s", email)
        return {"success": True, "user": user}

    def login_with_password(self, email: str, password: str) -> dict:
        user = self.repo.get_by_email(email)
        if not user or not user.password_hash:
            return {"success": False, "message": "Email o password non corretti."}

        if not _check_password(password, user.password_hash):
            return {"success": False, "message": "Email o password non corretti."}

        if not user.is_active:
            if user.approved_at is None:
                return {
                    "success": False,
                    "message": "Il tuo account è in attesa di approvazione. Lo staff ti contatterà quando sarà attivo.",
                    "pending": True,
                }
            else:
                return {
                    "success": False,
                    "message": "Il tuo account è stato disabilitato. Contatta lo staff per assistenza.",
                }

        logger.info("Login effettuato: %s", email)
        return {"success": True, "user": user}

    def update_profile(self, user_id: int, first_name: str, last_name: str, dog_name: Optional[str]) -> Optional[User]:
        user = self.repo.get_by_id(user_id)
        if not user:
            return None
        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.dog_name = dog_name.strip() if dog_name else None
        self.db.commit()
        self.db.refresh(user)
        logger.info("Profilo aggiornato per user_id=%s", user_id)
        return user

    def change_password(self, user_id: int, current_password: str, new_password: str) -> dict:
        user = self.repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "Utente non trovato."}
        if not user.password_hash:
            return {"success": False, "message": "Account non valido."}
        if not _check_password(current_password, user.password_hash):
            return {"success": False, "message": "La password attuale non e corretta."}
        if len(new_password) < 8:
            return {"success": False, "message": "La nuova password deve essere di almeno 8 caratteri."}
        if not any(c.isdigit() for c in new_password):
            return {"success": False, "message": "La nuova password deve contenere almeno un numero."}
        user.password_hash = _hash_password(new_password)
        self.db.commit()
        logger.info("Password aggiornata per user_id=%s", user_id)
        return {"success": True}
