from datetime import date
from datetime import time as time_type

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.discipline_repository import DisciplineRepository
from app.services.availability_service import AvailabilityService
from app.utils.auth import require_auth
from app.utils.csrf import get_csrf_token
from app.utils.date_it import register_date_filters

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    disciplines = DisciplineRepository(db).get_all_active()
    return templates.TemplateResponse(
        request, "index.html",
        {"disciplines": disciplines, "csrf_token": get_csrf_token(request), "current_user": user},
    )


@router.post("/prenota/slots", response_class=HTMLResponse)
async def get_slots_partial(
    request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    """Endpoint HTMX: restituisce la griglia di slot per data e disciplina."""
    form = await request.form()
    try:
        discipline_id = int(form.get("discipline_id", ""))
        requested_date = date.fromisoformat(form.get("date", ""))
    except (ValueError, TypeError):
        return HTMLResponse("<p class='text-red-500 text-sm p-4'>Dati non validi.</p>", status_code=400)

    slots = AvailabilityService(db).get_available_slots(discipline_id, requested_date)
    return templates.TemplateResponse(
        request, "booking/slots_partial.html",
        {"slots": slots, "discipline_id": discipline_id, "selected_date": requested_date},
    )


@router.get("/prenota/conferma", response_class=HTMLResponse)
async def booking_confirm_page(
    request: Request,
    discipline_id: int,
    appointment_date: str,
    start_time: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        parsed_date = date.fromisoformat(appointment_date)
    except ValueError:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    discipline = DisciplineRepository(db).get_by_id(discipline_id)
    if not discipline:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    try:
        h, m = start_time.split(":")
        slot_time = time_type(int(h), int(m))
    except (ValueError, AttributeError):
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    availability = AvailabilityService(db)
    if not availability.is_slot_available(discipline_id, parsed_date, slot_time):
        return templates.TemplateResponse(
            request, "booking/select_slot.html",
            {
                "discipline": discipline,
                "available_dates": availability.get_available_dates(discipline_id),
                "error": "Questo orario non e piu disponibile. Scegli un altro slot.",
                "csrf_token": get_csrf_token(request),
                "current_user": user,
            },
        )

    return templates.TemplateResponse(
        request, "booking/confirm.html",
        {
            "discipline": discipline,
            "appointment_date": parsed_date,
            "start_time": start_time,
            "current_user": user,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.get("/prenotazione/{token}", response_class=HTMLResponse)
async def booking_confirmed_page(request: Request, token: str, db: Session = Depends(get_db)):
    from app.repositories.appointment_repository import AppointmentRepository
    appointment = AppointmentRepository(db).get_by_cancellation_token(token)
    if not appointment:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)
    user_id = request.session.get("user_id")
    current_user = None
    if user_id:
        from app.repositories.user_repository import UserRepository
        current_user = UserRepository(db).get_by_id(user_id)
    return templates.TemplateResponse(
        request, "booking/confirmed.html",
        {"appointment": appointment, "current_user": current_user},
    )


@router.get("/cancella/{token}", response_class=HTMLResponse)
async def cancel_page(request: Request, token: str, db: Session = Depends(get_db)):
    from datetime import datetime
    from app.repositories.appointment_repository import AppointmentRepository
    from app.models.appointment import AppointmentStatus

    appointment = AppointmentRepository(db).get_by_cancellation_token(token)
    if not appointment:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    already_cancelled = appointment.status == AppointmentStatus.cancelled
    hours_until = (
        (datetime.combine(appointment.appointment_date, appointment.start_time) - datetime.now()).total_seconds() / 3600
    )
    can_cancel = not already_cancelled and hours_until >= 24

    user_id = request.session.get("user_id")
    current_user = None
    if user_id:
        from app.repositories.user_repository import UserRepository
        current_user = UserRepository(db).get_by_id(user_id)

    return templates.TemplateResponse(
        request, "booking/cancel.html",
        {
            "appointment": appointment,
            "already_cancelled": already_cancelled,
            "can_cancel": can_cancel,
            "csrf_token": get_csrf_token(request),
            "current_user": current_user,
        },
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {"current_user": None})


# Deve stare DOPO le route statiche /prenota/... per non catturarle come discipline_id
@router.get("/prenota/{discipline_id}", response_class=HTMLResponse)
async def select_slot_page(
    request: Request, discipline_id: int,
    user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    discipline = DisciplineRepository(db).get_by_id(discipline_id)
    if not discipline or not discipline.is_active:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    available_dates = AvailabilityService(db).get_available_dates(discipline_id)
    return templates.TemplateResponse(
        request, "booking/select_slot.html",
        {
            "discipline": discipline,
            "available_dates": available_dates,
            "csrf_token": get_csrf_token(request),
            "current_user": user,
        },
    )
