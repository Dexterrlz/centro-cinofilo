import logging
from datetime import date, time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.booking_service import BookingService
from app.utils.auth import require_auth
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.date_it import register_date_filters

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)
limiter = Limiter(key_func=get_remote_address)


@router.post("/prenota/crea", response_class=HTMLResponse)
@limiter.limit("10/hour")
async def create_booking(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Crea la prenotazione per l'utente autenticato."""
    await validate_csrf(request)

    form = await request.form()
    discipline_id_raw = form.get("discipline_id", "")
    date_str = form.get("appointment_date", "")
    start_time_str = form.get("start_time", "")

    try:
        discipline_id = int(discipline_id_raw)
        appointment_date = date.fromisoformat(date_str)
        h, m = start_time_str.split(":")
        slot_time = time(int(h), int(m))
    except (ValueError, TypeError, AttributeError):
        return templates.TemplateResponse(
            request, "booking/confirm.html",
            {
                "errors": ["Dati di prenotazione non validi. Torna indietro e riprova."],
                "current_user": user,
                "csrf_token": get_csrf_token(request),
            },
            status_code=422,
        )

    result = BookingService(db).create_booking(
        discipline_id=discipline_id,
        appointment_date=appointment_date,
        start_time=slot_time,
        user_id=user.id,
    )

    if not result["success"]:
        from app.repositories.discipline_repository import DisciplineRepository
        discipline = DisciplineRepository(db).get_by_id(discipline_id)
        return templates.TemplateResponse(
            request, "booking/confirm.html",
            {
                "discipline": discipline,
                "appointment_date": appointment_date,
                "start_time": start_time_str,
                "errors": [result["message"]],
                "current_user": user,
                "csrf_token": get_csrf_token(request),
            },
            status_code=422,
        )

    return RedirectResponse(url=f"/prenotazione/{result['appointment'].cancellation_token}", status_code=303)


@router.post("/cancella/{token}", response_class=HTMLResponse)
async def cancel_booking(request: Request, token: str, db: Session = Depends(get_db)):
    """Processa la cancellazione di una prenotazione via link email (no auth richiesto)."""
    await validate_csrf(request)

    result = BookingService(db).cancel_booking(token)

    user_id = request.session.get("user_id")
    current_user = None
    if user_id:
        from app.repositories.user_repository import UserRepository
        current_user = UserRepository(db).get_by_id(user_id)

    if not result["success"]:
        from datetime import datetime as dt
        from app.repositories.appointment_repository import AppointmentRepository
        from app.models.appointment import AppointmentStatus

        appointment = AppointmentRepository(db).get_by_cancellation_token(token)
        already_cancelled = appointment and appointment.status == AppointmentStatus.cancelled
        can_cancel = False
        if appointment and not already_cancelled:
            apt_dt = dt.combine(appointment.appointment_date, appointment.start_time)
            can_cancel = (apt_dt - dt.now()).total_seconds() / 3600 >= 24

        return templates.TemplateResponse(
            request, "booking/cancel.html",
            {
                "appointment": appointment,
                "already_cancelled": already_cancelled,
                "can_cancel": can_cancel,
                "error": result["message"],
                "csrf_token": get_csrf_token(request),
                "current_user": current_user,
            },
            status_code=422,
        )

    return templates.TemplateResponse(
        request, "booking/cancel.html",
        {
            "appointment": result["appointment"],
            "already_cancelled": True,
            "can_cancel": False,
            "success": True,
            "current_user": current_user,
        },
    )
