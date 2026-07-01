from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.instructor import Instructor


class InstructorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> Optional[Instructor]:
        return (
            self.db.query(Instructor)
            .filter(Instructor.username == username, Instructor.is_active == True)
            .first()
        )

    def get_by_id(self, instructor_id: int) -> Optional[Instructor]:
        return (
            self.db.query(Instructor)
            .options(joinedload(Instructor.disciplines))
            .filter(Instructor.id == instructor_id)
            .first()
        )

    def get_all_active_with_disciplines(self) -> List[Instructor]:
        """Istruttori attivi con le loro discipline precaricate, per lo step 1 del flusso prenotazione."""
        return (
            self.db.query(Instructor)
            .options(joinedload(Instructor.disciplines))
            .filter(Instructor.is_active == True)
            .order_by(Instructor.name)
            .all()
        )

    def get_by_email(self, email: str) -> Optional[Instructor]:
        return self.db.query(Instructor).filter(Instructor.email == email).first()

    def get_all(self) -> List[Instructor]:
        return self.db.query(Instructor).order_by(Instructor.name).all()

    def get_all_active_excluding(self, excluded_names: list) -> List[Instructor]:
        """Istruttori attivi escludendo quelli con i nomi indicati (per homepage)."""
        return (
            self.db.query(Instructor)
            .options(joinedload(Instructor.disciplines))
            .filter(
                Instructor.is_active == True,
                ~Instructor.name.in_(excluded_names),
            )
            .order_by(Instructor.name)
            .all()
        )

    def update_password(self, instructor_id: int, password_hash: str) -> Optional[Instructor]:
        instructor = self.get_by_id(instructor_id)
        if instructor:
            instructor.password_hash = password_hash
            self.db.commit()
            self.db.refresh(instructor)
        return instructor
