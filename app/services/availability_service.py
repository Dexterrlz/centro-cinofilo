from datetime import date, time, timedelta, datetime
from typing import List
from sqlalchemy.orm import Session

from app.repositories.availability_rule_repository import AvailabilityRuleRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.blocked_date_repository import BlockedDateRepository

SLOT_DURATION = 30  # minuti
MAX_DAYS_AHEAD = 30


def _generate_slots(start: time, end: time) -> List[time]:
    """Genera slot da 30 minuti nell'intervallo [start, end)."""
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    while current < end_dt:
        slots.append(current.time())
        current += timedelta(minutes=SLOT_DURATION)
    return slots


class AvailabilityService:
    def __init__(self, db: Session):
        self.rule_repo = AvailabilityRuleRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.blocked_repo = BlockedDateRepository(db)

    def get_available_slots(self, discipline_id: int, requested_date: date) -> List[time]:
        """Restituisce gli slot liberi per una disciplina in una data."""
        today = date.today()

        if requested_date < today or requested_date > today + timedelta(days=MAX_DAYS_AHEAD):
            return []

        if self.blocked_repo.is_blocked(discipline_id, requested_date):
            return []

        day_of_week = requested_date.weekday()
        rules = self.rule_repo.get_by_discipline_and_day(discipline_id, day_of_week)
        if not rules:
            return []

        all_slots: set = set()
        for rule in rules:
            all_slots.update(_generate_slots(rule.start_time, rule.end_time))

        booked = set(self.appointment_repo.get_booked_times_for_discipline_date(discipline_id, requested_date))
        available = sorted(all_slots - booked)

        # Se è oggi, filtra gli orari già passati
        if requested_date == today:
            now = datetime.now().time()
            available = [s for s in available if s > now]

        return available

    def get_available_dates(self, discipline_id: int) -> List[date]:
        """Restituisce le date con almeno uno slot disponibile entro 30 giorni."""
        today = date.today()
        return [
            today + timedelta(days=i)
            for i in range(MAX_DAYS_AHEAD + 1)
            if self.get_available_slots(discipline_id, today + timedelta(days=i))
        ]

    def is_slot_available(self, discipline_id: int, check_date: date, slot_time: time) -> bool:
        return slot_time in self.get_available_slots(discipline_id, check_date)
