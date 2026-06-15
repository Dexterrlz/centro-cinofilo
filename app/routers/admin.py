import logging
from datetime import date, time, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import AppointmentStatus
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.availability_rule_repository import AvailabilityRuleRepository
from app.repositories.blocked_date_repository import BlockedDateRepository
from app.repositories.discipline_repository import DisciplineRepository
from app.services.admin_service import AdminService
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.date_it import register_date_filters

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)
limiter = Limiter(key_func=get_remote_address)

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def _require_admin(request: Request):
    """Restituisce username se autenticato, altrimenti None."""
    return request.session.get("admin_username")


# ─── Login / Logout ───────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _require_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse(
        request, "admin/login.html",
        {"csrf_token": get_csrf_token(request)},
    )


@router.post("/login", response_class=HTMLResponse)
@limiter.limit("10/hour")
async def login(request: Request, db: Session = Depends(get_db)):
    await validate_csrf(request)

    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")

    service = AdminService(db)
    result = service.authenticate(username, password)

    if not result["success"]:
        return templates.TemplateResponse(
            request, "admin/login.html",
            {"error": result["message"], "csrf_token": get_csrf_token(request)},
            status_code=401,
        )

    request.session["admin_username"] = username
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    today = date.today()
    appointment_repo = AppointmentRepository(db)
    discipline_repo = DisciplineRepository(db)
    rule_repo = AvailabilityRuleRepository(db)
    blocked_repo = BlockedDateRepository(db)

    # Parametri filtro prenotazioni
    status_filter = request.query_params.get("status")
    discipline_filter = request.query_params.get("discipline_id")
    date_from_str = request.query_params.get("date_from")
    date_to_str = request.query_params.get("date_to")

    try:
        date_from = date.fromisoformat(date_from_str) if date_from_str else None
    except ValueError:
        date_from = None
    try:
        date_to = date.fromisoformat(date_to_str) if date_to_str else None
    except ValueError:
        date_to = None

    status_enum = None
    if status_filter:
        try:
            status_enum = AppointmentStatus(status_filter)
        except ValueError:
            pass

    discipline_id_filter = int(discipline_filter) if discipline_filter and discipline_filter.isdigit() else None

    appointments = appointment_repo.get_all_filtered(
        status=status_enum,
        discipline_id=discipline_id_filter,
        date_from=date_from,
        date_to=date_to,
    )

    disciplines = discipline_repo.get_all()
    rules = rule_repo.get_all()
    blocked_dates = blocked_repo.get_all()

    stats = {
        "oggi": appointment_repo.count_by_date(today),
        "imminenti": appointment_repo.count_upcoming(),
        "totale": len(appointment_repo.get_all_filtered()),
    }

    return templates.TemplateResponse(
        request, "admin/dashboard.html",
        {
            "admin_username": _require_admin(request),
            "appointments": appointments,
            "disciplines": disciplines,
            "rules": rules,
            "blocked_dates": blocked_dates,
            "stats": stats,
            "giorni": GIORNI,
            "statuses": list(AppointmentStatus),
            "today": today,
            "csrf_token": get_csrf_token(request),
            "filter_status": status_filter or "",
            "filter_discipline": discipline_filter or "",
            "filter_date_from": date_from_str or "",
            "filter_date_to": date_to_str or "",
        },
    )


# ─── Stato prenotazione ───────────────────────────────────────────────────────

@router.post("/prenotazioni/{appointment_id}/stato", response_class=HTMLResponse)
async def update_appointment_status(
    request: Request, appointment_id: int, db: Session = Depends(get_db)
):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    form = await request.form()
    new_status_str = form.get("status", "")

    try:
        new_status = AppointmentStatus(new_status_str)
    except ValueError:
        return RedirectResponse(url="/admin?error=stato_invalido", status_code=303)

    repo = AppointmentRepository(db)
    appointment = repo.update_status(appointment_id, new_status)

    if not appointment:
        return RedirectResponse(url="/admin?error=prenotazione_non_trovata", status_code=303)

    logger.info(
        "Admin ha aggiornato stato prenotazione id=%s a %s", appointment_id, new_status
    )
    return RedirectResponse(url="/admin", status_code=303)


# ─── Disponibilità ────────────────────────────────────────────────────────────

@router.post("/disponibilita", response_class=HTMLResponse)
async def add_availability_rule(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    form = await request.form()
    try:
        discipline_id = int(form.get("discipline_id", ""))
        day_of_week = int(form.get("day_of_week", ""))
        start_str = form.get("start_time", "")
        end_str = form.get("end_time", "")

        sh, sm = start_str.split(":")
        eh, em = end_str.split(":")
        start_time = time(int(sh), int(sm))
        end_time = time(int(eh), int(em))

        if start_time >= end_time:
            raise ValueError("L'orario di inizio deve essere prima di quello di fine.")
        if day_of_week < 0 or day_of_week > 6:
            raise ValueError("Giorno non valido.")

    except (ValueError, TypeError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    AvailabilityRuleRepository(db).create(discipline_id, day_of_week, start_time, end_time)
    logger.info("Regola disponibilità aggiunta: disciplina=%s giorno=%s", discipline_id, day_of_week)
    return RedirectResponse(url="/admin#disponibilita", status_code=303)


@router.post("/disponibilita/{rule_id}/elimina", response_class=HTMLResponse)
async def delete_availability_rule(
    request: Request, rule_id: int, db: Session = Depends(get_db)
):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    AvailabilityRuleRepository(db).delete(rule_id)
    logger.info("Regola disponibilità eliminata: id=%s", rule_id)
    return RedirectResponse(url="/admin#disponibilita", status_code=303)


# ─── Date bloccate ────────────────────────────────────────────────────────────

@router.post("/date-bloccate", response_class=HTMLResponse)
async def add_blocked_date(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    form = await request.form()
    try:
        blocked_date = date.fromisoformat(form.get("blocked_date", ""))
    except ValueError:
        return RedirectResponse(url="/admin?error=data_invalida#date-bloccate", status_code=303)

    discipline_id_raw = form.get("discipline_id", "")
    discipline_id = int(discipline_id_raw) if discipline_id_raw.isdigit() else None
    all_disciplines = discipline_id is None
    reason = form.get("reason", "").strip() or None

    BlockedDateRepository(db).create(
        blocked_date=blocked_date,
        discipline_id=discipline_id,
        reason=reason,
        all_disciplines=all_disciplines,
    )
    logger.info("Data bloccata aggiunta: %s", blocked_date)
    return RedirectResponse(url="/admin#date-bloccate", status_code=303)


@router.post("/date-bloccate/{blocked_id}/elimina", response_class=HTMLResponse)
async def delete_blocked_date(
    request: Request, blocked_id: int, db: Session = Depends(get_db)
):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    BlockedDateRepository(db).delete(blocked_id)
    logger.info("Data bloccata eliminata: id=%s", blocked_id)
    return RedirectResponse(url="/admin#date-bloccate", status_code=303)
