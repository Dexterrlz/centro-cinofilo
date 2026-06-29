from datetime import date, time
from typing import List, Optional
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from app.models.appointment import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, appointment_id: int) -> Optional[Appointment]:
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.discipline),
                joinedload(Appointment.instructor),
            )
            .filter(Appointment.id == appointment_id)
            .first()
        )

    def get_by_cancellation_token(self, token: str) -> Optional[Appointment]:
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.discipline),
                joinedload(Appointment.instructor),
            )
            .filter(Appointment.cancellation_token == token)
            .first()
        )

    def get_booked_times_for_discipline_date(
        self, discipline_id: int, appointment_date: date
    ) -> List[time]:
        rows = (
            self.db.query(Appointment.start_time)
            .filter(
                and_(
                    Appointment.discipline_id == discipline_id,
                    Appointment.appointment_date == appointment_date,
                    Appointment.status.in_(
                        [AppointmentStatus.pending, AppointmentStatus.confirmed]
                    ),
                )
            )
            .all()
        )
        return [r.start_time for r in rows]

    def get_booked_times_for_instructor_date(
        self, instructor_id: int, appointment_date: date
    ) -> List[time]:
        rows = (
            self.db.query(Appointment.start_time)
            .filter(
                and_(
                    Appointment.instructor_id == instructor_id,
                    Appointment.appointment_date == appointment_date,
                    Appointment.status.in_(
                        [AppointmentStatus.pending, AppointmentStatus.confirmed]
                    ),
                )
            )
            .all()
        )
        return [r.start_time for r in rows]

    def count_active_in_week_for_combo(
        self,
        user_id: int,
        discipline_id: int,
        instructor_id: int,
        week_start: date,
        week_end: date,
    ) -> int:
        return (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.user_id == user_id,
                    Appointment.discipline_id == discipline_id,
                    Appointment.instructor_id == instructor_id,
                    Appointment.appointment_date >= week_start,
                    Appointment.appointment_date <= week_end,
                    Appointment.status.in_(
                        [AppointmentStatus.pending, AppointmentStatus.confirmed]
                    ),
                )
            )
            .count()
        )

    def get_slot_with_lock(
        self, discipline_id: int, appointment_date: date, start_time: time
    ) -> Optional[Appointment]:
        """Legge lo slot con SELECT FOR UPDATE per prevenire double booking."""
        return (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.discipline_id == discipline_id,
                    Appointment.appointment_date == appointment_date,
                    Appointment.start_time == start_time,
                    Appointment.status.in_(
                        [AppointmentStatus.pending, AppointmentStatus.confirmed]
                    ),
                )
            )
            .with_for_update()
            .first()
        )

    def create(
        self,
        discipline_id: int,
        user_id: int,
        appointment_date: date,
        start_time: time,
        end_time: time,
        cancellation_token: str,
        instructor_id: Optional[int] = None,
        package_id: Optional[int] = None,
    ) -> Appointment:
        appointment = Appointment(
            discipline_id=discipline_id,
            user_id=user_id,
            instructor_id=instructor_id,
            package_id=package_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.confirmed,
            cancellation_token=cancellation_token,
        )
        self.db.add(appointment)
        return appointment

    def update_status(self, appointment_id: int, status: AppointmentStatus) -> Optional[Appointment]:
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if appointment:
            appointment.status = status
            self.db.commit()
        return self.get_by_id(appointment_id) if appointment else None

    def get_by_slot(
        self,
        discipline_id: int,
        instructor_id: int,
        appointment_date: date,
        start_time: time,
    ) -> Optional[Appointment]:
        """Recupera la prenotazione per uno specifico slot (per la vista agenda)."""
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.package),
            )
            .filter(
                Appointment.discipline_id == discipline_id,
                Appointment.instructor_id == instructor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.start_time == start_time,
                Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.confirmed]),
            )
            .first()
        )

    def get_all_filtered(
        self,
        status: Optional[AppointmentStatus] = None,
        discipline_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        user_search: Optional[str] = None,
    ) -> List[Appointment]:
        from app.models.user import User

        query = self.db.query(Appointment).options(
            joinedload(Appointment.user),
            joinedload(Appointment.discipline),
            joinedload(Appointment.instructor),
        )
        if status:
            query = query.filter(Appointment.status == status)
        if discipline_id:
            query = query.filter(Appointment.discipline_id == discipline_id)
        if date_from:
            query = query.filter(Appointment.appointment_date >= date_from)
        if date_to:
            query = query.filter(Appointment.appointment_date <= date_to)
        if user_search:
            term = f"%{user_search}%"
            query = query.join(User).filter(
                or_(User.first_name.ilike(term), User.last_name.ilike(term))
            )
        return query.order_by(Appointment.appointment_date.asc(), Appointment.start_time.asc()).all()

    def count_by_date(self, target_date: date) -> int:
        return (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.appointment_date == target_date,
                    Appointment.status.in_(
                        [AppointmentStatus.pending, AppointmentStatus.confirmed]
                    ),
                )
            )
            .count()
        )

    def count_upcoming(self) -> int:
        from datetime import datetime
        today = datetime.now().date()
        return (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.appointment_date >= today,
                    Appointment.status.in_(
                        [AppointmentStatus.pending, AppointmentStatus.confirmed]
                    ),
                )
            )
            .count()
        )
