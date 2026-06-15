from datetime import date
from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.models.blocked_date import BlockedDate


class BlockedDateRepository:
    def __init__(self, db: Session):
        self.db = db

    def is_blocked(self, discipline_id: int, check_date: date) -> bool:
        result = (
            self.db.query(BlockedDate)
            .filter(
                BlockedDate.blocked_date == check_date,
                or_(
                    BlockedDate.all_disciplines == True,
                    BlockedDate.discipline_id == discipline_id,
                ),
            )
            .first()
        )
        return result is not None

    def get_all(self) -> List[BlockedDate]:
        return (
            self.db.query(BlockedDate)
            .options(joinedload(BlockedDate.discipline))
            .order_by(BlockedDate.blocked_date.desc())
            .all()
        )

    def get_by_id(self, blocked_id: int) -> Optional[BlockedDate]:
        return self.db.query(BlockedDate).filter(BlockedDate.id == blocked_id).first()

    def create(
        self,
        blocked_date: date,
        discipline_id: int = None,
        reason: str = None,
        all_disciplines: bool = False,
    ) -> BlockedDate:
        bd = BlockedDate(
            blocked_date=blocked_date,
            discipline_id=discipline_id,
            reason=reason,
            all_disciplines=all_disciplines,
        )
        self.db.add(bd)
        self.db.commit()
        self.db.refresh(bd)
        return bd

    def delete(self, blocked_id: int) -> bool:
        bd = self.get_by_id(blocked_id)
        if bd:
            self.db.delete(bd)
            self.db.commit()
            return True
        return False
