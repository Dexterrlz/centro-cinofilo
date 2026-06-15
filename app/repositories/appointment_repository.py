from datetime import date, time
from typing import List, Optional
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from app.models.appointment import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, appointment_id: int) -> Optional[Appointment]:
        return (
            self.db.query(Appointment)
            .options(joinedload(Appointment.user), joinedload(Appointment.discipline))
            .filter(Appointment.id == appointment_id)
            .first()
        )

    def get_by_cancellation_token(self, token: str) -> Optional[Appointment]:
        return (
            self.db.query(Appointment)
            .options(joinedload(Appointment.user), joinedload(Appointment.discipline))
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
    ) -> Appointment:
        appointment = Appointment(
            discipline_id=discipline_id,
            user_id=user_id,
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
            self.db.refresh(appointment)
        return appointment

    def get_all_filtered(
        self,
        status: Optional[AppointmentStatus] = None,
        discipline_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Appointment]:
        query = self.db.query(Appointment).options(
            joinedload(Appointment.user), joinedload(Appointment.discipline)
        )
        if status:
            query = query.filter(Appointment.status == status)
        if discipline_id:
            query = query.filter(Appointment.discipline_id == discipline_id)
        if date_from:
            query = query.filter(Appointment.appointment_date >= date_from)
        if date_to:
            query = query.filter(Appointment.appointment_date <= date_to)
        return query.order_by(Appointment.appointment_date.desc(), Appointment.start_time).all()

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
