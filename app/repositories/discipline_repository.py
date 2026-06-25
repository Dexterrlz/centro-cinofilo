from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.discipline import Discipline


class DisciplineRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_active(self) -> List[Discipline]:
        return (
            self.db.query(Discipline)
            .options(joinedload(Discipline.instructor))
            .filter(Discipline.is_active == True, Discipline.instructor_id.isnot(None))
            .all()
        )

    def get_all_manageable(self) -> List[Discipline]:
        """Tutte le discipline reali (con istruttore), attive o chiuse temporaneamente.
        Usato nella tab admin 'Discipline' per poter riattivare quelle chiuse."""
        return (
            self.db.query(Discipline)
            .options(joinedload(Discipline.instructor))
            .filter(Discipline.instructor_id.isnot(None))
            .order_by(Discipline.name)
            .all()
        )

    def get_all(self) -> List[Discipline]:
        return self.db.query(Discipline).all()

    def get_by_id(self, discipline_id: int) -> Optional[Discipline]:
        return self.db.query(Discipline).filter(Discipline.id == discipline_id).first()

    def create(self, name: str, description: str = None, color: str = "#3B82F6") -> Discipline:
        discipline = Discipline(name=name, description=description, color=color)
        self.db.add(discipline)
        self.db.commit()
        self.db.refresh(discipline)
        return discipline

    def update(self, discipline_id: int, **kwargs) -> Optional[Discipline]:
        discipline = self.get_by_id(discipline_id)
        if discipline:
            for key, value in kwargs.items():
                setattr(discipline, key, value)
            self.db.commit()
            self.db.refresh(discipline)
        return discipline

    def count(self) -> int:
        return self.db.query(Discipline).count()
