from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.discipline_group import DisciplineGroup
from app.models.discipline import Discipline


class DisciplineGroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Optional[DisciplineGroup]:
        return self.db.query(DisciplineGroup).filter(DisciplineGroup.name == name).first()

    def get_by_id(self, group_id: int) -> Optional[DisciplineGroup]:
        return (
            self.db.query(DisciplineGroup)
            .options(
                joinedload(DisciplineGroup.disciplines)
                .joinedload(Discipline.instructor)
            )
            .filter(DisciplineGroup.id == group_id)
            .first()
        )

    def get_all(self) -> List[DisciplineGroup]:
        return (
            self.db.query(DisciplineGroup)
            .options(
                joinedload(DisciplineGroup.disciplines)
                .joinedload(Discipline.instructor)
            )
            .all()
        )
