import logging
from typing import Optional

import bcrypt
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.instructor_repository import InstructorRepository
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
_RESET_SALT = "admin-password-reset"
_RESET_TOKEN_MAX_AGE = 86400  # 24 ore


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InstructorRepository(db)

    def authenticate(self, username: str, password: str) -> dict:
        """Autentica un istruttore per l'accesso al pannello admin. Messaggio generico per sicurezza."""
        instructor = self.repo.get_by_username(username)

        if not instructor:
            logger.warning("Tentativo login admin fallito: username '%s' non trovato", username)
            return {"success": False, "message": "Credenziali non valide."}

        if not _check_password(password, instructor.password_hash):
            logger.warning("Tentativo login admin fallito: password errata per '%s'", username)
            return {"success": False, "message": "Credenziali non valide."}

        logger.info("Istruttore '%s' autenticato sul pannello admin", username)
        return {"success": True, "instructor": instructor}

    def change_password(self, instructor_id: int, current_password: str, new_password: str) -> dict:
        instructor = self.repo.get_by_id(instructor_id)
        if not instructor:
            return {"success": False, "message": "Istruttore non trovato."}
        if not _check_password(current_password, instructor.password_hash):
            return {"success": False, "message": "La password attuale non e corretta."}
        if len(new_password) < 8:
            return {"success": False, "message": "La nuova password deve essere di almeno 8 caratteri."}
        if not any(c.isdigit() for c in new_password):
            return {"success": False, "message": "La nuova password deve contenere almeno un numero."}

        self.repo.update_password(instructor_id, _hash_password(new_password))
        logger.info("Password admin aggiornata per instructor_id=%s", instructor_id)
        return {"success": True}

    def request_password_reset(self, username: str) -> None:
        """Invia un'email di reset se l'username esiste e ha un'email associata.
        Non rivela se l'username esiste, per sicurezza."""
        instructor = self.repo.get_by_username(username)
        if not instructor or not instructor.email:
            logger.info("Richiesta reset password admin per username non trovato o senza email: '%s'", username)
            return

        token = _serializer.dumps(instructor.id, salt=_RESET_SALT)
        reset_url = f"{settings.APP_URL}/admin/reset-password/{token}"
        EmailService.send_admin_password_reset(
            email=instructor.email, name=instructor.name, reset_url=reset_url
        )
        logger.info("Email reset password admin inviata a instructor_id=%s", instructor.id)

    def reset_password(self, token: str, new_password: str) -> dict:
        try:
            instructor_id = _serializer.loads(token, salt=_RESET_SALT, max_age=_RESET_TOKEN_MAX_AGE)
        except (SignatureExpired, BadSignature):
            return {"success": False, "message": "Il link di reset non e valido o e scaduto."}

        instructor = self.repo.get_by_id(instructor_id)
        if not instructor:
            return {"success": False, "message": "Istruttore non trovato."}
        if len(new_password) < 8:
            return {"success": False, "message": "La nuova password deve essere di almeno 8 caratteri."}
        if not any(c.isdigit() for c in new_password):
            return {"success": False, "message": "La nuova password deve contenere almeno un numero."}

        self.repo.update_password(instructor.id, _hash_password(new_password))
        logger.info("Password admin reimpostata per instructor_id=%s", instructor.id)
        return {"success": True}
