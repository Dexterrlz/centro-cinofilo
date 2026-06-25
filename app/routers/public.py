from datetime import date, timedelta
from datetime import time as time_type

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.discipline_repository import DisciplineRepository
from app.repositories.instructor_repository import InstructorRepository
from app.repositories.package_repository import PackageRepository
from app.services.availability_service import AvailabilityService, get_booking_window
from app.utils.auth import require_auth
from app.utils.csrf import get_csrf_token
from app.utils.date_it import register_date_filters

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)

MAX_RANGE_DAYS = 13  # ampiezza massima della finestra prenotabile (2 settimane)


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Step 1 del flusso prenotazione: scelta istruttore."""
    instructors = InstructorRepository(db).get_all_active_with_disciplines()
    instructors = [i for i in instructors if any(d.is_active for d in i.disciplines)]
    return templates.TemplateResponse(
        request, "index.html",
        {"instructors": instructors, "csrf_token": get_csrf_token(request), "current_user": user},
    )


@router.get("/istruttore/{instructor_id}", response_class=HTMLResponse)
async def select_discipline_page(
    request: Request, instructor_id: int,
    user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    """Step 2 del flusso prenotazione: scelta disciplina per l'istruttore selezionato."""
    instructor = InstructorRepository(db).get_by_id(instructor_id)
    if not instructor or not instructor.is_active:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    package_repo = PackageRepository(db)
    disciplines = []
    for d in sorted(instructor.disciplines, key=lambda x: x.name):
        if not d.is_active:
            continue
        package = package_repo.get_by_combo(user.id, d.id, instructor_id)
        status = None
        if package:
            status = "exhausted" if (not package.is_active or package.lessons_completed >= package.total_lessons) else "active"
        disciplines.append({"discipline": d, "package": package, "status": status})

    return templates.TemplateResponse(
        request, "booking/select_discipline.html",
        {
            "instructor": instructor,
            "disciplines": disciplines,
            "csrf_token": get_csrf_token(request),
            "current_user": user,
        },
    )


@router.post("/prenota/slots", response_class=HTMLResponse)
async def get_slots_partial(
    request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    """Endpoint HTMX: restituisce gli slot disponibili nel range di date, raggruppati per giorno."""
    form = await request.form()
    try:
        discipline_id = int(form.get("discipline_id", ""))
        date_from = date.fromisoformat(form.get("date_from", ""))
        date_to = date.fromisoformat(form.get("date_to", ""))
    except (ValueError, TypeError):
        return HTMLResponse("<p class='text-red-500 text-sm p-4'>Dati non validi.</p>", status_code=400)

    if date_to < date_from or (date_to - date_from).days > MAX_RANGE_DAYS:
        return HTMLResponse("<p class='text-red-500 text-sm p-4'>Intervallo di date non valido.</p>", status_code=400)

    availability = AvailabilityService(db)
    days = []
    current = date_from
    while current <= date_to:
        slots = availability.get_available_slots(discipline_id, current)
        if slots:
            suggested = availability.get_suggested_slots_for_date(discipline_id, current)
            days.append({
                "date": current,
                "slots": [{"time": s, "is_suggested": s in suggested} for s in slots],
            })
        current += timedelta(days=1)

    return templates.TemplateResponse(
        request, "booking/slots_partial.html",
        {
            "days": days,
            "discipline_id": discipline_id,
            "date_from": date_from,
            "date_to": date_to,
        },
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
        window_start, window_end = get_booking_window()
        available_dates = availability.get_available_dates(discipline_id)
        return templates.TemplateResponse(
            request, "booking/select_slot.html",
            {
                "discipline": discipline,
                "min_date": available_dates[0] if available_dates else window_start,
                "max_date": available_dates[-1] if available_dates else window_end,
                "window_start": window_start,
                "window_end": window_end,
                "has_availability": bool(available_dates),
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
    """Step 3 del flusso prenotazione: range picker date."""
    discipline = DisciplineRepository(db).get_by_id(discipline_id)
    if not discipline or not discipline.is_active:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    if discipline.instructor_id:
        package = PackageRepository(db).get_by_combo(user.id, discipline_id, discipline.instructor_id)
        if package and (not package.is_active or package.lessons_completed >= package.total_lessons):
            return templates.TemplateResponse(
                request, "booking/select_slot.html",
                {
                    "discipline": discipline,
                    "package_exhausted": True,
                    "csrf_token": get_csrf_token(request),
                    "current_user": user,
                },
            )

    availability = AvailabilityService(db)
    available_dates = availability.get_available_dates(discipline_id)
    window_start, window_end = get_booking_window()

    return templates.TemplateResponse(
        request, "booking/select_slot.html",
        {
            "discipline": discipline,
            "min_date": available_dates[0] if available_dates else window_start,
            "max_date": available_dates[-1] if available_dates else window_end,
            "window_start": window_start,
            "window_end": window_end,
            "has_availability": bool(available_dates),
            "csrf_token": get_csrf_token(request),
            "current_user": user,
        },
    )
