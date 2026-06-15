import logging
import resend
from app.config import settings

logger = logging.getLogger(__name__)


def _sender() -> str:
    return f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"


class EmailService:

    @staticmethod
    def send_verification_email(email: str, first_name: str, verify_url: str) -> bool:
        """Invia email con link di verifica account."""
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": _sender(),
                "to": [email],
                "subject": f"Attiva il tuo account — {settings.APP_NAME}",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1f2937;">
  <h2 style="margin-bottom:8px;">Ciao {first_name},</h2>
  <p style="color:#4b5563;">Benvenuto in {settings.APP_NAME}! Clicca il pulsante qui sotto per attivare il tuo account.</p>
  <div style="margin:32px 0;">
    <a href="{verify_url}"
       style="display:inline-block;background:#059669;color:white;padding:14px 28px;border-radius:10px;text-decoration:none;font-size:16px;font-weight:600;">
      Attiva account
    </a>
  </div>
  <p style="color:#6b7280;font-size:14px;">Il link e valido per <strong>24 ore</strong>.</p>
  <p style="color:#6b7280;font-size:14px;">Se non hai creato un account, ignora questa email.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
  <p style="color:#9ca3af;font-size:12px;">{settings.APP_NAME}</p>
</div>""",
            })
            logger.info("Email verifica inviata a %s", email)
            return True
        except Exception as exc:
            logger.error("Errore invio email verifica a %s: %s", email, exc)
            return False

    @staticmethod
    def send_booking_confirmation(
        email: str,
        first_name: str,
        discipline_name: str,
        appointment_date: str,
        start_time: str,
        cancellation_token: str,
    ) -> bool:
        """Invia email di conferma prenotazione con link di cancellazione."""
        try:
            resend.api_key = settings.RESEND_API_KEY
            cancel_url = f"{settings.APP_URL}/cancella/{cancellation_token}"
            resend.Emails.send({
                "from": _sender(),
                "to": [email],
                "subject": f"Prenotazione confermata — {discipline_name}",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1f2937;">
  <h2>Prenotazione confermata!</h2>
  <p style="color:#4b5563;">Ciao {first_name}, la tua prenotazione e stata confermata.</p>
  <div style="background:#f0fdf4;border-left:4px solid #059669;border-radius:6px;padding:18px;margin:24px 0;">
    <p style="margin:0;"><strong>Disciplina:</strong> {discipline_name}</p>
    <p style="margin:8px 0 0;"><strong>Data:</strong> {appointment_date}</p>
    <p style="margin:8px 0 0;"><strong>Orario:</strong> {start_time}</p>
  </div>
  <p style="color:#6b7280;font-size:14px;">Puoi cancellare fino a 24 ore prima dell'appuntamento:</p>
  <a href="{cancel_url}" style="display:inline-block;background:#ef4444;color:white;padding:12px 22px;border-radius:8px;text-decoration:none;font-size:15px;margin-top:8px;">
    Cancella prenotazione
  </a>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0;">
  <p style="color:#9ca3af;font-size:12px;">{settings.APP_NAME}</p>
</div>""",
            })
            logger.info("Conferma prenotazione inviata a %s", email)
            return True
        except Exception as exc:
            logger.error("Errore invio conferma a %s: %s", email, exc)
            return False

    @staticmethod
    def send_cancellation_notice(
        email: str,
        first_name: str,
        discipline_name: str,
        appointment_date: str,
        start_time: str,
    ) -> bool:
        """Invia email di notifica cancellazione."""
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": _sender(),
                "to": [email],
                "subject": f"Prenotazione cancellata — {discipline_name}",
                "html": f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1f2937;">
  <h2>Prenotazione cancellata</h2>
  <p style="color:#4b5563;">Ciao {first_name}, la tua prenotazione e stata cancellata.</p>
  <div style="background:#fef2f2;border-left:4px solid #ef4444;border-radius:6px;padding:18px;margin:24px 0;">
    <p style="margin:0;"><strong>Disciplina:</strong> {discipline_name}</p>
    <p style="margin:8px 0 0;"><strong>Data:</strong> {appointment_date}</p>
    <p style="margin:8px 0 0;"><strong>Orario:</strong> {start_time}</p>
  </div>
  <a href="{settings.APP_URL}" style="display:inline-block;background:#059669;color:white;padding:12px 22px;border-radius:8px;text-decoration:none;font-size:15px;margin-top:8px;">
    Prenota di nuovo
  </a>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0;">
  <p style="color:#9ca3af;font-size:12px;">{settings.APP_NAME}</p>
</div>""",
            })
            logger.info("Notifica cancellazione inviata a %s", email)
            return True
        except Exception as exc:
            logger.error("Errore invio cancellazione a %s: %s", email, exc)
            return False
