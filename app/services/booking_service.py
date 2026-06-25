import logging
import secrets
from datetime import date, time, datetime, timedelta
from typing import Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.discipline_repository import DisciplineRepository
from app.repositories.package_repository import PackageRepository
from app.repositories.user_repository import UserRepository
from app.models.appointment import AppointmentStatus
from app.services.availability_service import (
    AvailabilityService,
    MIN_ADVANCE_HOURS,
    DEFAULT_SLOT_DURATION,
    instructor_is_available,
)
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

CANCEL_ADVANCE_HOURS = 24   # cancellabile fino a 24h prima dello slot
MAX_LESSONS_PER_WEEK = 2    # per combinazione utente+disciplina+istruttore


def _week_bounds(d: date) -> Tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)
        self.discipline_repo = DisciplineRepository(db)
        self.package_repo = PackageRepository(db)
        self.user_repo = UserRepository(db)
        self.availability_service = AvailabilityService(db)

    def create_booking(
        self,
        discipline_id: int,
        appointment_date: date,
        start_time: time,
        user_id: int,
    ) -> dict:
        """Crea una prenotazione con SELECT FOR UPDATE per prevenire double booking."""
        try:
            existing = self.appointment_repo.get_slot_with_lock(
                discipline_id, appointment_date, start_time
            )
            if existing:
                return {
                    "success": False,
                    "message": "Questo orario e appena stato prenotato da qualcun altro. Scegli un altro slot.",
                }

            discipline = self.discipline_repo.get_by_id(discipline_id)
            if not discipline or not discipline.is_active:
                return {"success": False, "message": "Questa disciplina non e al momento prenotabile."}

            appointment_dt = datetime.combine(appointment_date, start_time)
            if appointment_dt < datetime.now() + timedelta(hours=MIN_ADVANCE_HOURS):
                return {
                    "success": False,
                    "message": f"Le prenotazioni richiedono almeno {MIN_ADVANCE_HOURS} ore di preavviso.",
                }

            if not self.availability_service.is_slot_available(discipline_id, appointment_date, start_time):
                return {"success": False, "message": "Questo orario non e disponibile."}

            duration = discipline.slot_duration_minutes or DEFAULT_SLOT_DURATION
            if discipline.instructor_id and not instructor_is_available(
                discipline.instructor_id, appointment_date, start_time, duration, self.db
            ):
                return {
                    "success": False,
                    "message": "L'istruttore non e disponibile in questo orario su un'altra disciplina.",
                }

            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "Utente non trovato."}

            instructor_id = discipline.instructor_id
            package = None

            if instructor_id:
                week_start, week_end = _week_bounds(appointment_date)
                weekly_count = self.appointment_repo.count_active_in_week_for_combo(
                    user_id, discipline_id, instructor_id, week_start, week_end
                )
                if weekly_count >= MAX_LESSONS_PER_WEEK:
                    return {
                        "success": False,
                        "message": f"Hai gia raggiunto il massimo di {MAX_LESSONS_PER_WEEK} prenotazioni settimanali per questa disciplina.",
                    }

                package = self.package_repo.get_by_combo(user_id, discipline_id, instructor_id)
                if package is None:
                    package = self.package_repo.create(user_id, discipline_id, instructor_id)
                elif not package.is_active or package.lessons_completed >= package.total_lessons:
                    return {
                        "success": False,
                        "message": "Il tuo pacchetto per questa disciplina e esaurito o bloccato. Contatta il centro per rinnovarlo.",
                    }

            end_time = (datetime.combine(appointment_date, start_time) + timedelta(minutes=duration)).time()
            cancellation_token = secrets.token_urlsafe(32)

            appointment = self.appointment_repo.create(
                discipline_id=discipline_id,
                user_id=user_id,
                instructor_id=instructor_id,
                package_id=package.id if package else None,
                appointment_date=appointment_date,
                start_time=start_time,
                end_time=end_time,
                cancellation_token=cancellation_token,
            )
            self.db.commit()
            self.db.refresh(appointment)
            self.db.refresh(appointment.discipline)
            self.db.refresh(appointment.user)

            logger.info(
                "Prenotazione creata: id=%s disciplina=%s data=%s ora=%s user=%s",
                appointment.id,
                appointment.discipline.name,
                appointment_date,
                start_time,
                user.email,
            )

            EmailService.send_booking_confirmation(
                email=user.email,
                first_name=user.first_name,
                discipline_name=appointment.discipline.name,
                appointment_date=appointment_date.strftime("%d/%m/%Y"),
                start_time=start_time.strftime("%H:%M"),
                cancellation_token=cancellation_token,
            )

            return {"success": True, "appointment": appointment}

        except IntegrityError:
            self.db.rollback()
            logger.warning(
                "Race condition su disciplina=%s data=%s ora=%s",
                discipline_id, appointment_date, start_time,
            )
            return {
                "success": False,
                "message": "Questo orario e stato appena prenotato. Scegli un altro slot.",
            }
        except Exception as exc:
            self.db.rollback()
            logger.error("Errore creazione prenotazione: %s", exc)
            return {"success": False, "message": "Si e verificato un errore. Riprova."}

    def cancel_booking(self, cancellation_token: str) -> dict:
        """Cancella una prenotazione tramite token, rispettando il limite di 24 ore."""
        appointment = self.appointment_repo.get_by_cancellation_token(cancellation_token)

        if not appointment:
            return {"success": False, "message": "Prenotazione non trovata."}

        if appointment.status == AppointmentStatus.cancelled:
            return {"success": False, "message": "Questa prenotazione e gia stata cancellata."}

        if appointment.status not in (AppointmentStatus.pending, AppointmentStatus.confirmed):
            return {"success": False, "message": "Non e possibile cancellare questa prenotazione."}

        appointment_dt = datetime.combine(appointment.appointment_date, appointment.start_time)
        hours_until = (appointment_dt - datetime.now()).total_seconds() / 3600

        if hours_until < CANCEL_ADVANCE_HOURS:
            return {
                "success": False,
                "message": f"Non e possibile cancellare con meno di {CANCEL_ADVANCE_HOURS} ore di anticipo.",
            }

        self.appointment_repo.update_status(appointment.id, AppointmentStatus.cancelled)

        logger.info("Prenotazione cancellata: id=%s user=%s", appointment.id, appointment.user.email)

        EmailService.send_cancellation_notice(
            email=appointment.user.email,
            first_name=appointment.user.first_name,
            discipline_name=appointment.discipline.name,
            appointment_date=appointment.appointment_date.strftime("%d/%m/%Y"),
            start_time=appointment.start_time.strftime("%H:%M"),
        )

        return {"success": True, "appointment": appointment}

    def complete_lesson(self, appointment_id: int) -> dict:
        """Segna una lezione come completata e scala il contatore del pacchetto associato.
        Il contatore avanza SOLO qui, mai alla prenotazione."""
        appointment = self.appointment_repo.get_by_id(appointment_id)
        if not appointment:
            return {"success": False, "message": "Prenotazione non trovata."}

        if appointment.status == AppointmentStatus.completed:
            return {"success": True, "appointment": appointment}

        appointment.status = AppointmentStatus.completed

        if appointment.package_id:
            package = self.package_repo.get_by_id(appointment.package_id)
            if package:
                package.lessons_completed += 1
                if package.lessons_completed >= package.total_lessons:
                    package.is_active = False
                    EmailService.send_package_exhausted_notice(
                        email=appointment.user.email,
                        first_name=appointment.user.first_name,
                        discipline_name=appointment.discipline.name,
                    )

        self.db.commit()
        self.db.refresh(appointment)

        logger.info("Lezione completata: appointment_id=%s", appointment_id)

        return {"success": True, "appointment": appointment}
