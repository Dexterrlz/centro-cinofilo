import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import AppointmentStatus
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.package_repository import PackageRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.utils.auth import require_auth
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.date_it import register_date_filters

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile")
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)


@router.get("", response_class=HTMLResponse)
async def profile_page(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    packages = PackageRepository(db).get_all_for_user_with_group(user.id)
    return templates.TemplateResponse(
        request, "profile/index.html",
        {"current_user": user, "csrf_token": get_csrf_token(request), "packages": packages},
    )


@router.post("", response_class=HTMLResponse)
async def update_profile(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    await validate_csrf(request)
    form = await request.form()
    first_name = form.get("first_name", "").strip()
    last_name = form.get("last_name", "").strip()
    dog_name = form.get("dog_name", "").strip() or None

    if not first_name or not last_name:
        return HTMLResponse(
            '<div class="alert alert-error">Nome e cognome sono obbligatori.</div>',
            status_code=422,
        )

    result = AuthService(db).update_profile(user.id, first_name, last_name, dog_name)
    if not result:
        return HTMLResponse('<div class="alert alert-error">Errore durante il salvataggio. Riprova.</div>', status_code=500)

    response = HTMLResponse('<div class="alert alert-success">✓ Profilo aggiornato con successo!</div>')
    response.headers["HX-Trigger"] = "profileUpdated"
    return response


@router.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    repo = UserRepository(db)
    now = datetime.now()

    upcoming_raw = repo.get_appointments_by_user(
        user.id,
        [AppointmentStatus.confirmed, AppointmentStatus.pending],
    )
    upcoming = [
        {
            "appointment": a,
            "can_cancel": (datetime.combine(a.appointment_date, a.start_time) - now).total_seconds() / 3600 > 24,
        }
        for a in sorted(upcoming_raw, key=lambda x: (x.appointment_date, x.start_time))
    ]

    past_raw = repo.get_appointments_by_user(user.id, [AppointmentStatus.completed])
    past = sorted(past_raw, key=lambda x: (x.appointment_date, x.start_time), reverse=True)

    packages = PackageRepository(db).get_all_for_user_with_group(user.id)

    return templates.TemplateResponse(
        request, "profile/bookings.html",
        {
            "current_user": user,
            "upcoming": upcoming,
            "past": past,
            "packages": packages,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/bookings/{appointment_id}/cancel", response_class=HTMLResponse)
async def cancel_booking_from_profile(
    request: Request,
    appointment_id: int,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    await validate_csrf(request)

    repo = AppointmentRepository(db)
    appointment = repo.get_by_id(appointment_id)

    if not appointment:
        return HTMLResponse('<div class="alert alert-error">Prenotazione non trovata.</div>', status_code=404)

    if appointment.user_id != user.id:
        return HTMLResponse('<div class="alert alert-error">Non autorizzato.</div>', status_code=403)

    if appointment.status not in (AppointmentStatus.confirmed, AppointmentStatus.pending):
        return HTMLResponse(
            '<div class="alert alert-error">Questa prenotazione non puo essere cancellata.</div>',
            status_code=422,
        )

    hours_until = (
        datetime.combine(appointment.appointment_date, appointment.start_time) - datetime.now()
    ).total_seconds() / 3600

    if hours_until < 24:
        return HTMLResponse(
            '<div class="alert alert-error">Non puoi cancellare una lezione a meno di 24 ore dall\'inizio.</div>',
            status_code=422,
        )

    repo.update_status(appointment_id, AppointmentStatus.cancelled)
    logger.info("Prenotazione %s cancellata da profilo utente user_id=%s", appointment_id, user.id)

    response = HTMLResponse('<div class="alert alert-success">✓ Prenotazione cancellata.</div>')
    response.headers["HX-Redirect"] = "/profile/bookings"
    return response


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "profile/change_password.html",
        {
            "current_user": user,
            "csrf_token": get_csrf_token(request),
            "is_google_user": not bool(user.password_hash),
        },
    )


@router.post("/change-password", response_class=HTMLResponse)
async def update_password(request: Request, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    await validate_csrf(request)
    form = await request.form()
    current_password = form.get("current_password", "")
    new_password = form.get("new_password", "")
    confirm_password = form.get("confirm_password", "")

    if new_password != confirm_password:
        return HTMLResponse(
            '<div class="alert alert-error">Le password non corrispondono.</div>',
            status_code=422,
        )

    result = AuthService(db).change_password(user.id, current_password, new_password)
    if not result["success"]:
        return HTMLResponse(
            f'<div class="alert alert-error">{result["message"]}</div>',
            status_code=422,
        )

    return HTMLResponse(
        '<div class="alert alert-success">✓ Password aggiornata con successo!</div>'
        '<script>document.getElementById("pwd-form").reset();</script>'
    )
