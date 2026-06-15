from datetime import time
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.availability_rule import AvailabilityRule


class AvailabilityRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_discipline(self, discipline_id: int) -> List[AvailabilityRule]:
        return (
            self.db.query(AvailabilityRule)
            .filter(
                AvailabilityRule.discipline_id == discipline_id,
                AvailabilityRule.is_active == True,
            )
            .order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time)
            .all()
        )

    def get_by_discipline_and_day(self, discipline_id: int, day_of_week: int) -> List[AvailabilityRule]:
        return (
            self.db.query(AvailabilityRule)
            .filter(
                AvailabilityRule.discipline_id == discipline_id,
                AvailabilityRule.day_of_week == day_of_week,
                AvailabilityRule.is_active == True,
            )
            .all()
        )

    def get_all(self) -> List[AvailabilityRule]:
        return (
            self.db.query(AvailabilityRule)
            .options(joinedload(AvailabilityRule.discipline))
            .order_by(AvailabilityRule.discipline_id, AvailabilityRule.day_of_week)
            .all()
        )

    def get_by_id(self, rule_id: int) -> Optional[AvailabilityRule]:
        return self.db.query(AvailabilityRule).filter(AvailabilityRule.id == rule_id).first()

    def create(
        self, discipline_id: int, day_of_week: int, start_time: time, end_time: time
    ) -> AvailabilityRule:
        rule = AvailabilityRule(
            discipline_id=discipline_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete(self, rule_id: int) -> bool:
        rule = self.get_by_id(rule_id)
        if rule:
            self.db.delete(rule)
            self.db.commit()
            return True
        return False
