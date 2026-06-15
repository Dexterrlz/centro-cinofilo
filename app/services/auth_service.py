import logging
import secrets
from typing import Optional

import bcrypt
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
_VERIFY_SALT = "email-verification"
_TOKEN_MAX_AGE = 86400  # 24 ore


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_verification_token(email: str) -> str:
    return _serializer.dumps(email, salt=_VERIFY_SALT)


def _decode_verification_token(token: str) -> Optional[str]:
    try:
        return _serializer.loads(token, salt=_VERIFY_SALT, max_age=_TOKEN_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def register_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        dog_name: Optional[str] = None,
    ) -> dict:
        if self.repo.get_by_email(email):
            return {"success": False, "message": "Esiste gia un account con questa email."}

        token = _make_verification_token(email)
        user = self.repo.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=_hash_password(password),
            dog_name=dog_name or None,
            email_verified=False,
            verification_token=token,
        )

        verify_url = f"{settings.APP_URL}/verify-email/{token}"
        sent = EmailService.send_verification_email(email, first_name, verify_url)
        if not sent:
            logger.warning("Email verifica non inviata per %s", email)

        logger.info("Nuovo utente registrato: %s", email)
        return {"success": True, "user": user}

    def verify_email(self, token: str) -> dict:
        email = _decode_verification_token(token)
        if not email:
            return {"success": False, "message": "Il link di verifica non e valido o e scaduto."}

        user = self.repo.get_by_verification_token(token)
        if not user:
            return {"success": False, "message": "Link non valido."}

        if user.email_verified:
            return {"success": True, "already_verified": True}

        self.repo.verify_email(user)
        logger.info("Email verificata per %s", user.email)
        return {"success": True, "already_verified": False}

    def login_with_password(self, email: str, password: str) -> dict:
        user = self.repo.get_by_email(email)
        if not user or not user.password_hash:
            return {"success": False, "message": "Email o password non corretti."}

        if not _check_password(password, user.password_hash):
            return {"success": False, "message": "Email o password non corretti."}

        if not user.email_verified:
            return {
                "success": False,
                "message": "Controlla la tua email per attivare l'account prima di accedere.",
                "unverified": True,
            }

        if not user.is_active:
            return {"success": False, "message": "Account disabilitato. Contattaci per assistenza."}

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
            return {"success": False, "message": "Account Google: gestisci la password direttamente da Google."}
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

    def get_or_create_google_user(self, google_id: str, email: str, first_name: str, last_name: str) -> User:
        user = self.repo.get_by_google_id(google_id)
        if user:
            return user

        user = self.repo.get_by_email(email)
        if user:
            self.repo.link_google(user, google_id)
            if not user.email_verified:
                self.repo.verify_email(user)
            return user

        user = self.repo.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            google_id=google_id,
            email_verified=True,
        )
        logger.info("Nuovo utente via Google: %s", email)
        return user
