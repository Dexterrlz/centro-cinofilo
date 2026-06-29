import logging
from datetime import date, time, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import AppointmentStatus
from app.services.availability_service import build_daily_timeline
from app.repositories.package_repository import PackageRepository as PkgRepo
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.availability_rule_repository import AvailabilityRuleRepository
from app.repositories.blocked_date_repository import BlockedDateRepository
from app.repositories.discipline_repository import DisciplineRepository
from app.repositories.instructor_repository import InstructorRepository
from app.repositories.package_repository import PackageRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from app.services.booking_service import BookingService
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.date_it import register_date_filters
from app.utils.template_helpers import discipline_color

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)
templates.env.globals["discipline_color"] = discipline_color
limiter = Limiter(key_func=get_remote_address)

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def _require_admin(request: Request):
    """Restituisce username se autenticato, altrimenti None."""
    return request.session.get("admin_username")


def _current_instructor(request: Request, db: Session):
    """Restituisce l'oggetto Instructor dell'admin loggato, o None."""
    username = _require_admin(request)
    if not username:
        return None
    return InstructorRepository(db).get_by_username(username)


# ─── Login / Logout ───────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _require_admin(request):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
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
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


# ─── Password dimenticata ──────────────────────────────────────────────────────

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request, "admin/forgot_password.html",
        {"csrf_token": get_csrf_token(request)},
    )


@router.post("/forgot-password", response_class=HTMLResponse)
@limiter.limit("5/hour")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    await validate_csrf(request)
    form = await request.form()
    username = form.get("username", "").strip()

    if username:
        AdminService(db).request_password_reset(username)

    return templates.TemplateResponse(
        request, "admin/forgot_password.html",
        {
            "csrf_token": get_csrf_token(request),
            "sent": True,
        },
    )


@router.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(
        request, "admin/reset_password.html",
        {"csrf_token": get_csrf_token(request), "token": token},
    )


@router.post("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password(request: Request, token: str, db: Session = Depends(get_db)):
    await validate_csrf(request)
    form = await request.form()
    new_password = form.get("new_password", "")
    confirm_password = form.get("confirm_password", "")

    if new_password != confirm_password:
        return templates.TemplateResponse(
            request, "admin/reset_password.html",
            {"csrf_token": get_csrf_token(request), "token": token, "error": "Le password non corrispondono."},
            status_code=422,
        )

    result = AdminService(db).reset_password(token, new_password)
    if not result["success"]:
        return templates.TemplateResponse(
            request, "admin/reset_password.html",
            {"csrf_token": get_csrf_token(request), "token": token, "error": result["message"]},
            status_code=422,
        )

    return RedirectResponse(url="/admin/login?reset=ok", status_code=303)


# ─── Cambio password dal pannello ──────────────────────────────────────────────

@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(
        request, "admin/change_password.html",
        {"csrf_token": get_csrf_token(request), "admin_username": _require_admin(request)},
    )


@router.post("/change-password", response_class=HTMLResponse)
async def change_password(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)
    instructor = _current_instructor(request, db)
    if not instructor:
        return RedirectResponse(url="/admin/login", status_code=302)

    form = await request.form()
    current_password = form.get("current_password", "")
    new_password = form.get("new_password", "")
    confirm_password = form.get("confirm_password", "")

    if new_password != confirm_password:
        return templates.TemplateResponse(
            request, "admin/change_password.html",
            {
                "csrf_token": get_csrf_token(request),
                "admin_username": _require_admin(request),
                "error": "Le password non corrispondono.",
            },
            status_code=422,
        )

    result = AdminService(db).change_password(instructor.id, current_password, new_password)
    if not result["success"]:
        return templates.TemplateResponse(
            request, "admin/change_password.html",
            {
                "csrf_token": get_csrf_token(request),
                "admin_username": _require_admin(request),
                "error": result["message"],
            },
            status_code=422,
        )

    return templates.TemplateResponse(
        request, "admin/change_password.html",
        {
            "csrf_token": get_csrf_token(request),
            "admin_username": _require_admin(request),
            "success": True,
        },
    )


# ─── Dashboard ────────────────────────────────────────────────────────────────

_PAGE_TITLES = {
    "agenda": "Agenda",
    "prenotazioni": "Prenotazioni",
    "disponibilita": "Disponibilità",
    "date-bloccate": "Date bloccate",
    "discipline": "Discipline",
    "pacchetti": "Pacchetti",
    "utenti": "Utenti",
}


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_home(request: Request):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    section: str = "prenotazioni",
    db: Session = Depends(get_db),
):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    active_section = section if section in _PAGE_TITLES else "prenotazioni"
    page_title = _PAGE_TITLES[active_section]
    today = date.today()

    appointment_repo = AppointmentRepository(db)
    discipline_repo = DisciplineRepository(db)
    rule_repo = AvailabilityRuleRepository(db)
    blocked_repo = BlockedDateRepository(db)

    # Filtri prenotazioni (usati solo se active_section == "prenotazioni")
    status_filter = request.query_params.get("status")
    discipline_filter = request.query_params.get("discipline_id")
    date_from_str = request.query_params.get("date_from")
    date_to_str = request.query_params.get("date_to")
    user_search = (request.query_params.get("user_search") or "").strip()

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

    no_filters = not (status_filter or discipline_filter or date_from_str or date_to_str or user_search)
    if no_filters and active_section == "prenotazioni":
        monday = today - timedelta(days=today.weekday())
        date_from = monday
        date_to = monday + timedelta(days=13)

    appointments = appointment_repo.get_all_filtered(
        status=status_enum,
        discipline_id=discipline_id_filter,
        date_from=date_from,
        date_to=date_to,
        user_search=user_search or None,
    ) if active_section == "prenotazioni" else []

    disciplines = discipline_repo.get_all_active()
    disciplines_manageable = discipline_repo.get_all_manageable()
    rules = rule_repo.get_all()
    blocked_dates = blocked_repo.get_all()

    packages = PackageRepository(db).get_all_with_relations() if active_section == "pacchetti" else []
    packages_by_user = {}
    for p in packages:
        packages_by_user.setdefault(p.user, []).append(p)

    users = UserRepository(db).get_all_with_packages() if active_section == "utenti" else []

    stats = {
        "oggi": appointment_repo.count_by_date(today),
        "imminenti": appointment_repo.count_upcoming(),
        "totale": len(appointment_repo.get_all_filtered()),
    }

    return templates.TemplateResponse(
        request, "admin/dashboard.html",
        {
            "admin_username": _require_admin(request),
            "current_instructor": _current_instructor(request, db),
            "active_section": active_section,
            "page_title": page_title,
            "appointments": appointments,
            "disciplines": disciplines,
            "disciplines_manageable": disciplines_manageable,
            "rules": rules,
            "blocked_dates": blocked_dates,
            "packages_by_user": packages_by_user,
            "users": users,
            "stats": stats,
            "giorni": GIORNI,
            "statuses": list(AppointmentStatus),
            "today": today,
            "csrf_token": get_csrf_token(request),
            "filter_status": status_filter or "",
            "filter_discipline": discipline_filter or "",
            "filter_date_from": date_from.isoformat() if date_from and active_section == "prenotazioni" else "",
            "filter_date_to": date_to.isoformat() if date_to and active_section == "prenotazioni" else "",
            "filter_user_search": user_search,
        },
    )


# ─── Stato prenotazione (HTMX: aggiorna solo la riga, filtri preservati) ──────

@router.post("/appointments/{appointment_id}/status", response_class=HTMLResponse)
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
        return HTMLResponse(
            '<tr><td colspan="5" class="px-4 py-3 text-red-600 text-sm">Stato non valido.</td></tr>',
            status_code=422,
        )

    if new_status == AppointmentStatus.completed:
        result = BookingService(db).complete_lesson(appointment_id)
        appointment = result["appointment"] if result["success"] else None
    else:
        repo = AppointmentRepository(db)
        appointment = repo.update_status(appointment_id, new_status)

    if not appointment:
        return HTMLResponse(
            '<tr><td colspan="5" class="px-4 py-3 text-red-600 text-sm">Prenotazione non trovata.</td></tr>',
            status_code=404,
        )

    logger.info(
        "Admin ha aggiornato stato prenotazione id=%s a %s", appointment_id, new_status
    )

    return templates.TemplateResponse(
        request, "admin/_appointment_row.html",
        {
            "a": appointment,
            "statuses": list(AppointmentStatus),
            "csrf_token": get_csrf_token(request),
        },
    )


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
        return RedirectResponse(url=f"/admin/dashboard?section=disponibilita&error={str(exc)}", status_code=303)

    AvailabilityRuleRepository(db).create(discipline_id, day_of_week, start_time, end_time)
    logger.info("Regola disponibilità aggiunta: disciplina=%s giorno=%s", discipline_id, day_of_week)
    return RedirectResponse(url="/admin/dashboard?section=disponibilita", status_code=303)


@router.post("/disponibilita/{rule_id}/elimina", response_class=HTMLResponse)
async def delete_availability_rule(
    request: Request, rule_id: int, db: Session = Depends(get_db)
):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    AvailabilityRuleRepository(db).delete(rule_id)
    logger.info("Regola disponibilità eliminata: id=%s", rule_id)
    return RedirectResponse(url="/admin/dashboard?section=disponibilita", status_code=303)


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
        return RedirectResponse(url="/admin/dashboard?section=date-bloccate&error=data_invalida", status_code=303)

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
    return RedirectResponse(url="/admin/dashboard?section=date-bloccate", status_code=303)


@router.post("/date-bloccate/{blocked_id}/elimina", response_class=HTMLResponse)
async def delete_blocked_date(
    request: Request, blocked_id: int, db: Session = Depends(get_db)
):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    BlockedDateRepository(db).delete(blocked_id)
    logger.info("Data bloccata eliminata: id=%s", blocked_id)
    return RedirectResponse(url="/admin/dashboard?section=date-bloccate", status_code=303)


@router.post("/ferie-globali", response_class=HTMLResponse)
async def add_global_holiday(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    form = await request.form()
    try:
        date_from = date.fromisoformat(form.get("date_from", ""))
        date_to = date.fromisoformat(form.get("date_to", ""))
        if date_to < date_from:
            raise ValueError("La data di fine deve essere successiva o uguale a quella di inizio.")
    except ValueError:
        return RedirectResponse(url="/admin/dashboard?section=date-bloccate&error=range_non_valido", status_code=303)

    reason = form.get("reason", "").strip() or None

    count = BlockedDateRepository(db).create_global_range(date_from, date_to, reason)
    logger.info("Blocco ferie globale creato: %s -> %s (%s giorni)", date_from, date_to, count)
    return RedirectResponse(url="/admin/dashboard?section=date-bloccate", status_code=303)


# ─── Discipline: apertura/chiusura e periodo stagionale ───────────────────────

@router.post("/disciplines/{discipline_id}/toggle", response_class=HTMLResponse)
async def toggle_discipline(request: Request, discipline_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    repo = DisciplineRepository(db)
    discipline = repo.get_by_id(discipline_id)
    if discipline:
        repo.update(discipline_id, is_active=not discipline.is_active)
        logger.info(
            "Disciplina id=%s %s da admin", discipline_id,
            "riattivata" if not discipline.is_active else "chiusa temporaneamente",
        )
    return RedirectResponse(url="/admin/dashboard?section=discipline", status_code=303)


@router.post("/disciplines/{discipline_id}/stagionale", response_class=HTMLResponse)
async def set_seasonal_period(request: Request, discipline_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    form = await request.form()
    active_from_str = form.get("active_from", "").strip()
    active_until_str = form.get("active_until", "").strip()

    try:
        active_from = date.fromisoformat(active_from_str) if active_from_str else None
        active_until = date.fromisoformat(active_until_str) if active_until_str else None
    except ValueError:
        return RedirectResponse(url="/admin/dashboard?section=discipline&error=data_invalida", status_code=303)

    DisciplineRepository(db).update(discipline_id, active_from=active_from, active_until=active_until)
    logger.info("Periodo stagionale aggiornato per disciplina id=%s: %s -> %s", discipline_id, active_from, active_until)
    return RedirectResponse(url="/admin/dashboard?section=discipline", status_code=303)


# ─── Pacchetti ──────────────────────────────────────────────────────────────────

@router.post("/packages/{package_id}/renew", response_class=HTMLResponse)
async def renew_package(request: Request, package_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    PackageRepository(db).renew(package_id)
    logger.info("Pacchetto id=%s rinnovato da admin", package_id)
    return RedirectResponse(url="/admin/dashboard?section=pacchetti", status_code=303)


@router.post("/packages/{package_id}/block", response_class=HTMLResponse)
async def block_package(request: Request, package_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    PackageRepository(db).set_active(package_id, False)
    logger.info("Pacchetto id=%s bloccato da admin", package_id)
    return RedirectResponse(url="/admin/dashboard?section=pacchetti", status_code=303)


@router.post("/packages/{package_id}/unlock", response_class=HTMLResponse)
async def unlock_package(request: Request, package_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    await validate_csrf(request)

    PackageRepository(db).set_active(package_id, True)
    logger.info("Pacchetto id=%s sbloccato da admin", package_id)
    return RedirectResponse(url="/admin/dashboard?section=pacchetti", status_code=303)


# ─── Pacchetti: creazione manuale e modifica inline ────────────────────────────

@router.get("/pacchetti/crea", response_class=HTMLResponse)
async def admin_crea_pacchetto_form(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    users = UserRepository(db).get_all_active()
    disciplines = DisciplineRepository(db).get_all_manageable()
    return templates.TemplateResponse(
        request, "admin/crea_pacchetto.html",
        {
            "admin_username": _require_admin(request),
            "current_instructor": _current_instructor(request, db),
            "active_section": "pacchetti",
            "page_title": "Crea pacchetto",
            "users": users,
            "disciplines": disciplines,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/pacchetti/crea", response_class=HTMLResponse)
async def admin_crea_pacchetto(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    await validate_csrf(request)

    form = await request.form()
    error = None
    user_id = discipline_id = lessons_completed = None
    try:
        user_id = int(form.get("user_id", ""))
        discipline_id = int(form.get("discipline_id", ""))
        lessons_completed = int(form.get("lessons_completed", 0))
    except (ValueError, TypeError):
        error = "Dati del form non validi."

    if not error:
        discipline = DisciplineRepository(db).get_by_id(discipline_id)
        if not discipline:
            error = "Disciplina non trovata."
        else:
            try:
                PackageRepository(db).create_manual(
                    user_id=user_id,
                    discipline_id=discipline_id,
                    instructor_id=discipline.instructor_id,
                    lessons_completed=lessons_completed,
                    total_lessons=8,
                )
                logger.info(
                    "Admin ha creato pacchetto manuale: user_id=%s discipline_id=%s lezioni=%s",
                    user_id, discipline_id, lessons_completed,
                )
                return RedirectResponse(
                    url="/admin/dashboard?section=pacchetti&success=Pacchetto+creato",
                    status_code=303,
                )
            except ValueError as exc:
                error = str(exc)

    users = UserRepository(db).get_all_active()
    disciplines = DisciplineRepository(db).get_all_manageable()
    return templates.TemplateResponse(
        request, "admin/crea_pacchetto.html",
        {
            "admin_username": _require_admin(request),
            "current_instructor": _current_instructor(request, db),
            "active_section": "pacchetti",
            "page_title": "Crea pacchetto",
            "users": users,
            "disciplines": disciplines,
            "error": error,
            "csrf_token": get_csrf_token(request),
        },
        status_code=422,
    )


@router.post("/pacchetti/{package_id}/modifica", response_class=HTMLResponse)
async def admin_modifica_pacchetto(
    request: Request, package_id: int, db: Session = Depends(get_db)
):
    if not _require_admin(request):
        return HTMLResponse("Non autorizzato.", status_code=401)
    await validate_csrf(request)

    form = await request.form()
    try:
        lessons_completed = int(form.get("lessons_completed", ""))
    except (ValueError, TypeError):
        return HTMLResponse('<div class="error-inline">Valore non valido.</div>', status_code=400)

    try:
        pkg = PackageRepository(db).update_lessons_completed(package_id, lessons_completed)
    except ValueError as exc:
        return HTMLResponse(f'<div class="error-inline">{exc}</div>', status_code=400)

    logger.info("Admin ha aggiornato lezioni pacchetto id=%s → %s", package_id, lessons_completed)

    from sqlalchemy.orm import joinedload as jl
    from app.models.package import Package as PkgModel
    pkg = (
        db.query(PkgModel)
        .options(jl(PkgModel.user), jl(PkgModel.discipline), jl(PkgModel.instructor))
        .filter(PkgModel.id == package_id)
        .first()
    )
    return templates.TemplateResponse(
        request, "admin/_package_row.html",
        {
            "p": pkg,
            "csrf_token": get_csrf_token(request),
        },
    )


# ─── Utenti ────────────────────────────────────────────────────────────────────

@router.get("/agenda", response_class=HTMLResponse)
async def agenda(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    date_str = request.query_params.get("selected_date")
    instructor_id_str = request.query_params.get("instructor_id")

    try:
        view_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        view_date = date.today()

    instr_repo = InstructorRepository(db)
    all_instructors = instr_repo.get_all()

    instructor_id = int(instructor_id_str) if instructor_id_str and instructor_id_str.isdigit() else None
    if instructor_id:
        viewed = instr_repo.get_by_id(instructor_id)
    else:
        viewed = _current_instructor(request, db)

    if not viewed and all_instructors:
        viewed = all_instructors[0]

    if not viewed:
        return RedirectResponse(url="/admin/dashboard", status_code=302)


    timeline = build_daily_timeline(db, viewed, view_date)
    expiring = PkgRepo(db).get_expiring_by_instructor(viewed.id, threshold=2)

    prev_date = (view_date - timedelta(days=1)).isoformat()
    next_date = (view_date + timedelta(days=1)).isoformat()

    return templates.TemplateResponse(
        request, "admin/agenda.html",
        {
            "admin_username": _require_admin(request),
            "current_instructor": _current_instructor(request, db),
            "active_section": "agenda",
            "page_title": "Agenda",
            "viewed_instructor": viewed,
            "all_instructors": all_instructors,
            "selected_date": view_date,
            "prev_date": prev_date,
            "next_date": next_date,
            "timeline": timeline,
            "expiring_packages": expiring,
            "today": date.today(),
            "csrf_token": get_csrf_token(request),
        },
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    return RedirectResponse(url="/admin/dashboard?section=utenti", status_code=302)


@router.post("/users/{user_id}/toggle", response_class=HTMLResponse)
async def toggle_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return HTMLResponse("Non autorizzato.", status_code=401)

    await validate_csrf(request)

    repo = UserRepository(db)
    user = repo.get_by_id_any(user_id)
    if not user:
        return HTMLResponse("Utente non trovato.", status_code=404)

    if user.is_active:
        repo.disable(user)
        logger.info("Admin ha disabilitato user_id=%s", user_id)
    else:
        repo.approve(user)
        logger.info("Admin ha abilitato user_id=%s", user_id)

    return templates.TemplateResponse(
        request, "admin/_user_row.html",
        {
            "u": user,
            "csrf_token": get_csrf_token(request),
        },
    )
