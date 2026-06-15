import logging
import secrets
from datetime import date, time, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.models.appointment import AppointmentStatus
from app.services.availability_service import AvailabilityService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

CANCELLATION_LIMIT_HOURS = 24


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)
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

            if not self.availability_service.is_slot_available(discipline_id, appointment_date, start_time):
                return {"success": False, "message": "Questo orario non e disponibile."}

            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "Utente non trovato."}

            end_time = (
                datetime.combine(appointment_date, start_time) + timedelta(minutes=30)
            ).time()
            cancellation_token = secrets.token_urlsafe(32)

            appointment = self.appointment_repo.create(
                discipline_id=discipline_id,
                user_id=user_id,
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

        if hours_until < CANCELLATION_LIMIT_HOURS:
            return {
                "success": False,
                "message": f"Non e possibile cancellare con meno di {CANCELLATION_LIMIT_HOURS} ore di anticipo.",
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
