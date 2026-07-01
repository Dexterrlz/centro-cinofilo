from datetime import date, timedelta, datetime
from datetime import time as time_type

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.discipline_group_repository import DisciplineGroupRepository
from app.repositories.discipline_repository import DisciplineRepository
from app.repositories.instructor_repository import InstructorRepository
from app.repositories.package_repository import PackageRepository
from app.services.availability_service import (
    AvailabilityService,
    get_available_slots_for_group,
    get_booking_window,
)
from app.services.booking_service import BookingService
from app.utils.auth import require_auth
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.date_it import register_date_filters

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)

MAX_RANGE_DAYS = 13


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Homepage: tile Agility (gruppo), Swim Dog Sport, Santa e Simona."""
    agility_group = DisciplineGroupRepository(db).get_by_name("agility")
    direct_disciplines = DisciplineRepository(db).get_direct_without_group()
    hidden = ["Angelo", "Conny"]
    visible_instructors = InstructorRepository(db).get_all_active_excluding(hidden)
    visible_instructors = [i for i in visible_instructors if any(d.is_active for d in i.disciplines)]

    user_agility_package = None
    if agility_group:
        user_agility_package = PackageRepository(db).get_active_for_user_and_group(
            user.id, agility_group.id
        )
        if user_agility_package is None:
            # Cerca anche pacchetti esauriti per mostrare lo stato
            from app.models.package import Package
            user_agility_package = (
                db.query(Package)
                .filter(
                    Package.user_id == user.id,
                    Package.group_id == agility_group.id,
                )
                .order_by(Package.created_at.desc())
                .first()
            )

    return templates.TemplateResponse(
        request, "index.html",
        {
            "agility_group": agility_group,
            "direct_disciplines": direct_disciplines,
            "visible_instructors": visible_instructors,
            "user_agility_package": user_agility_package,
            "csrf_token": get_csrf_token(request),
            "current_user": user,
        },
    )


@router.get("/agility", response_class=HTMLResponse)
async def agility_slot_selection(
    request: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Pagina selezione slot per il gruppo Agility."""
    agility_group = DisciplineGroupRepository(db).get_by_name("agility")
    if not agility_group:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    window_start, window_end = get_booking_window()

    package = PackageRepository(db).get_active_for_user_and_group(user.id, agility_group.id)
    if package is None:
        from app.models.package import Package
        package = (
            db.query(Package)
            .filter(Package.user_id == user.id, Package.group_id == agility_group.id)
            .order_by(Package.created_at.desc())
            .first()
        )

    if package and (not package.is_active or package.lessons_completed >= package.total_lessons):
        return templates.TemplateResponse(
            request, "booking/agility_slots.html",
            {
                "group": agility_group,
                "package_exhausted": True,
                "package": package,
                "current_user": user,
                "csrf_token": get_csrf_token(request),
            },
        )

    slots = get_available_slots_for_group(
        db=db,
        group_id=agility_group.id,
        date_from=window_start,
        date_to=window_end,
    )

    return templates.TemplateResponse(
        request, "booking/agility_slots.html",
        {
            "group": agility_group,
            "slots": slots,
            "package": package,
            "window_start": window_start,
            "window_end": window_end,
            "has_availability": bool(slots),
            "csrf_token": get_csrf_token(request),
            "current_user": user,
        },
    )


@router.post("/agility/prenota", response_class=HTMLResponse)
async def agility_book(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Crea prenotazione Agility con assegnazione automatica istruttore."""
    await validate_csrf(request)

    form = await request.form()
    date_str = form.get("date", "")
    start_time_str = form.get("start_time", "")
    end_time_str = form.get("end_time", "")
    group_id_raw = form.get("group_id", "")

    try:
        appt_date = date.fromisoformat(date_str)
        h, m = start_time_str.split(":")
        start = time_type(int(h), int(m))
        h2, m2 = end_time_str.split(":")
        end = time_type(int(h2), int(m2))
        group_id = int(group_id_raw)
    except (ValueError, TypeError, AttributeError):
        return templates.TemplateResponse(
            request, "booking/agility_slots.html",
            {
                "error": "Dati di prenotazione non validi. Torna indietro e riprova.",
                "current_user": user,
                "csrf_token": get_csrf_token(request),
            },
            status_code=422,
        )

    result = BookingService(db).create_booking_for_group(
        group_id=group_id,
        appointment_date=appt_date,
        start_time=start,
        end_time=end,
        user_id=user.id,
    )

    if not result["success"]:
        agility_group = DisciplineGroupRepository(db).get_by_name("agility")
        window_start, window_end = get_booking_window()
        slots = get_available_slots_for_group(
            db=db, group_id=group_id,
            date_from=window_start, date_to=window_end,
        )
        return templates.TemplateResponse(
            request, "booking/agility_slots.html",
            {
                "group": agility_group,
                "slots": slots,
                "has_availability": bool(slots),
                "window_start": window_start,
                "window_end": window_end,
                "error": result["message"],
                "current_user": user,
                "csrf_token": get_csrf_token(request),
            },
            status_code=422,
        )

    return RedirectResponse(
        url=f"/prenotazione/{result['appointment'].cancellation_token}", status_code=303
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
                "error": "Questo orario non è più disponibile. Scegli un altro slot.",
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
    from datetime import datetime as dt
    from app.repositories.appointment_repository import AppointmentRepository
    from app.models.appointment import AppointmentStatus

    appointment = AppointmentRepository(db).get_by_cancellation_token(token)
    if not appointment:
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)

    already_cancelled = appointment.status == AppointmentStatus.cancelled
    hours_until = (
        (dt.combine(appointment.appointment_date, appointment.start_time) - dt.now()).total_seconds() / 3600
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
