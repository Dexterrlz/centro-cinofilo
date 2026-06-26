"""
Email service disabilitato.
Le notifiche avvengono tramite approvazione manuale admin.
"""
import logging

logger = logging.getLogger(__name__)


class EmailService:

    @staticmethod
    def send_verification_email(email: str, first_name: str, verify_url: str) -> bool:
        logger.info("[EMAIL DISABILITATA] Verifica account per %s", email)
        return True

    @staticmethod
    def send_booking_confirmation(
        email: str,
        first_name: str,
        discipline_name: str,
        appointment_date: str,
        start_time: str,
        cancellation_token: str,
    ) -> bool:
        logger.info("[EMAIL DISABILITATA] Conferma prenotazione per %s", email)
        return True

    @staticmethod
    def send_cancellation_notice(
        email: str,
        first_name: str,
        discipline_name: str,
        appointment_date: str,
        start_time: str,
    ) -> bool:
        logger.info("[EMAIL DISABILITATA] Cancellazione prenotazione per %s", email)
        return True

    @staticmethod
    def send_package_exhausted_notice(email: str, first_name: str, discipline_name: str) -> bool:
        logger.info("[EMAIL DISABILITATA] Pacchetto esaurito per %s", email)
        return True

    @staticmethod
    def send_admin_password_reset(email: str, name: str, reset_url: str) -> bool:
        logger.info("[EMAIL DISABILITATA] Reset password admin per %s", email)
        return True
