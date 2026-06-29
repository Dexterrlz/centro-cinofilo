from datetime import date, time, timedelta, datetime
from typing import List, Set, Tuple
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.availability_rule_repository import AvailabilityRuleRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.blocked_date_repository import BlockedDateRepository
from app.repositories.discipline_repository import DisciplineRepository

MIN_ADVANCE_HOURS = 12
DEFAULT_SLOT_DURATION = 30  # minuti, fallback per discipline senza slot_duration_minutes


def get_booking_window(today: date = None) -> Tuple[date, date]:
    """
    Ritorna (start_date, end_date) della finestra prenotabile.
    Mostra sempre le prossime 2 settimane complete (Lunedì-Domenica), uguali per tutti gli utenti.
    Ogni Sabato a mezzanotte la finestra avanza alla settimana successiva.
    """
    today = today or date.today()
    current_monday = today - timedelta(days=today.weekday())
    if today.weekday() >= 5:  # Sabato=5, Domenica=6: la settimana corrente è già "chiusa"
        current_monday += timedelta(days=7)
    start = current_monday
    end = start + timedelta(days=13)
    return start, end


def generate_slots(start: time, end: time, duration_minutes: int) -> List[time]:
    """Genera gli slot di orario nell'intervallo [start, end) in base alla durata della disciplina."""
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    duration = timedelta(minutes=duration_minutes)
    while current + duration <= end_dt:
        slots.append(current.time())
        current += duration
    return slots


def get_suggested_slots(
    available_slots: List[time], booked_times_same_day: List[time], duration_minutes: int
) -> Set[time]:
    """
    Marca come 'consigliati' i 2 slot immediatamente successivi a ogni prenotazione
    già esistente nel giorno, per ridurre i buchi nel calendario dell'istruttore.
    """
    sorted_slots = sorted(available_slots)
    duration = timedelta(minutes=duration_minutes)
    suggested: Set[time] = set()

    for booked_start in booked_times_same_day:
        booked_end = (datetime.combine(date.today(), booked_start) + duration).time()
        for i, slot in enumerate(sorted_slots):
            if slot == booked_end:
                suggested.add(slot)
                if i + 1 < len(sorted_slots):
                    suggested.add(sorted_slots[i + 1])

    return suggested


def instructor_is_available(
    instructor_id: int, appointment_date: date, start_time: time, duration_minutes: int, db: Session
) -> bool:
    """
    Verifica che l'istruttore non abbia lezioni che si sovrappongono con lo slot
    richiesto (start_time -> start_time + duration_minutes), considerando la durata
    reale di ogni sua disciplina, non solo quella corrente. Si applica IN AGGIUNTA
    al vincolo UNIQUE su (discipline_id, appointment_date, start_time), non lo sostituisce.
    """
    proposed_start = datetime.combine(appointment_date, start_time)
    proposed_end = proposed_start + timedelta(minutes=duration_minutes)

    existing = (
        db.query(Appointment)
        .filter(
            Appointment.instructor_id == instructor_id,
            Appointment.appointment_date == appointment_date,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.confirmed]),
        )
        .all()
    )

    for appt in existing:
        appt_start = datetime.combine(appointment_date, appt.start_time)
        appt_end = datetime.combine(appointment_date, appt.end_time)
        if proposed_start < appt_end and proposed_end > appt_start:
            return False

    return True


class AvailabilityService:
    def __init__(self, db: Session):
        self.db = db
        self.rule_repo = AvailabilityRuleRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.blocked_repo = BlockedDateRepository(db)
        self.discipline_repo = DisciplineRepository(db)

    def _is_within_season(self, discipline, requested_date: date) -> bool:
        if not discipline.active_from or not discipline.active_until:
            return True
        target = (requested_date.month, requested_date.day)
        start = (discipline.active_from.month, discipline.active_from.day)
        end = (discipline.active_until.month, discipline.active_until.day)
        return start <= target <= end

    def get_available_slots(self, discipline_id: int, requested_date: date) -> List[time]:
        """Restituisce gli slot liberi per una disciplina in una data, rispettando finestra
        prenotabile, preavviso minimo e periodo stagionale."""
        discipline = self.discipline_repo.get_by_id(discipline_id)
        if not discipline or not discipline.is_active:
            return []

        window_start, window_end = get_booking_window()
        if requested_date < window_start or requested_date > window_end:
            return []

        if not self._is_within_season(discipline, requested_date):
            return []

        if self.blocked_repo.is_blocked(discipline_id, requested_date):
            return []

        day_of_week = requested_date.weekday()
        rules = self.rule_repo.get_by_discipline_and_day(discipline_id, day_of_week)
        if not rules:
            return []

        duration = discipline.slot_duration_minutes or DEFAULT_SLOT_DURATION
        all_slots: set = set()
        for rule in rules:
            all_slots.update(generate_slots(rule.start_time, rule.end_time, duration))

        booked = set(self.appointment_repo.get_booked_times_for_discipline_date(discipline_id, requested_date))
        available = sorted(all_slots - booked)

        if discipline.instructor_id:
            available = [
                s for s in available
                if instructor_is_available(discipline.instructor_id, requested_date, s, duration, self.db)
            ]

        min_bookable_dt = datetime.now() + timedelta(hours=MIN_ADVANCE_HOURS)
        available = [s for s in available if datetime.combine(requested_date, s) >= min_bookable_dt]

        return available

    def get_suggested_slots_for_date(self, discipline_id: int, requested_date: date) -> Set[time]:
        """Restituisce gli orari 'consigliati' (anti-buco) per la data richiesta."""
        discipline = self.discipline_repo.get_by_id(discipline_id)
        if not discipline or not discipline.instructor_id:
            return set()

        available = self.get_available_slots(discipline_id, requested_date)
        if not available:
            return set()

        booked_instructor_day = self.appointment_repo.get_booked_times_for_instructor_date(
            discipline.instructor_id, requested_date
        )
        if not booked_instructor_day:
            return set()

        duration = discipline.slot_duration_minutes or DEFAULT_SLOT_DURATION
        return get_suggested_slots(available, booked_instructor_day, duration)

    def get_available_dates(self, discipline_id: int) -> List[date]:
        """Restituisce le date con almeno uno slot disponibile entro la finestra prenotabile."""
        window_start, window_end = get_booking_window()
        start = max(window_start, date.today())
        days = (window_end - start).days
        if days < 0:
            return []
        return [
            start + timedelta(days=i)
            for i in range(days + 1)
            if self.get_available_slots(discipline_id, start + timedelta(days=i))
        ]

    def is_slot_available(self, discipline_id: int, check_date: date, slot_time: time) -> bool:
        return slot_time in self.get_available_slots(discipline_id, check_date)


def build_daily_timeline(db: Session, instructor, target_date: date) -> list:
    """
    Costruisce la timeline giornaliera per un istruttore.
    Ritorna lista di gruppi: [{'period': 'mattina', 'slots': [...]}, ...]
    """
    rule_repo = AvailabilityRuleRepository(db)
    appt_repo = AppointmentRepository(db)
    disc_repo = DisciplineRepository(db)

    disciplines = disc_repo.get_by_instructor(instructor.id)
    weekday = target_date.weekday()
    all_slots = []
    seen = set()

    for discipline in disciplines:
        rules = rule_repo.get_by_discipline_and_day(discipline.id, weekday)
        if not rules:
            continue

        duration = discipline.slot_duration_minutes or DEFAULT_SLOT_DURATION

        for rule in rules:
            for slot_start in generate_slots(rule.start_time, rule.end_time, duration):
                key = (slot_start, discipline.id)
                if key in seen:
                    continue
                seen.add(key)

                slot_end = (
                    datetime.combine(target_date, slot_start) + timedelta(minutes=duration)
                ).time()
                appointment = appt_repo.get_by_slot(
                    discipline.id, instructor.id, target_date, slot_start
                )

                package = None
                lessons_left = None

                if appointment:
                    package = appointment.package
                    if package:
                        lessons_left = package.total_lessons - package.lessons_completed

                all_slots.append({
                    "start": slot_start,
                    "end": slot_end,
                    "discipline": discipline,
                    "is_free": appointment is None,
                    "appointment": appointment,
                    "package": package,
                    "lessons_left": lessons_left,
                })

    all_slots.sort(key=lambda s: (s["start"], s["discipline"].name))

    def get_period(t):
        if t < time(13, 0):
            return "mattina"
        if t < time(18, 0):
            return "pomeriggio"
        return "sera"

    grouped = {}
    for slot in all_slots:
        period = get_period(slot["start"])
        grouped.setdefault(period, []).append(slot)

    return [
        {"period": period, "slots": grouped[period]}
        for period in ["mattina", "pomeriggio", "sera"]
        if period in grouped
    ]
