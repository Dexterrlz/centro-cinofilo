import logging
import bcrypt
from sqlalchemy.orm import Session

from app.repositories.admin_user_repository import AdminUserRepository

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: Session):
        self.repo = AdminUserRepository(db)

    def authenticate(self, username: str, password: str) -> dict:
        """Autentica admin. Messaggio di errore generico per sicurezza."""
        admin = self.repo.get_by_username(username)

        if not admin:
            logger.warning("Tentativo login fallito: username '%s' non trovato", username)
            return {"success": False, "message": "Credenziali non valide."}

        if not bcrypt.checkpw(password.encode("utf-8"), admin.password_hash.encode("utf-8")):
            logger.warning("Tentativo login fallito: password errata per '%s'", username)
            return {"success": False, "message": "Credenziali non valide."}

        self.repo.update_last_login(admin.id)
        logger.info("Admin '%s' autenticato", username)
        return {"success": True, "admin": admin}

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def create_admin(self, username: str, password: str):
        password_hash = self.hash_password(password)
        return self.repo.create(username, password_hash)

    def admin_exists(self) -> bool:
        return self.repo.count() > 0
