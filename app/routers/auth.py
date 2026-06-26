import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService
from app.utils.auth import get_current_user
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.date_it import register_date_filters

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)
limiter = Limiter(key_func=get_remote_address)


# ─── Login ────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        request, "auth/login.html",
        {"csrf_token": get_csrf_token(request), "error": error, "current_user": None},
    )


@router.post("/login", response_class=HTMLResponse)
@limiter.limit("10/hour")
async def login(request: Request, db: Session = Depends(get_db)):
    await validate_csrf(request)
    form = await request.form()
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")

    if not email or not password:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"csrf_token": get_csrf_token(request), "error": "Inserisci email e password.", "current_user": None},
            status_code=422,
        )

    result = AuthService(db).login_with_password(email, password)
    if not result["success"]:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {
                "csrf_token": get_csrf_token(request),
                "error": result["message"],
                "pending": result.get("pending", False),
                "current_user": None,
            },
            status_code=401,
        )

    request.session["user_id"] = result["user"].id
    logger.info("Sessione aperta per user_id=%s", result["user"].id)
    return RedirectResponse(url="/", status_code=303)


# ─── Registrazione ────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request, "auth/register.html",
        {"csrf_token": get_csrf_token(request), "current_user": None},
    )


@router.post("/register", response_class=HTMLResponse)
@limiter.limit("5/hour")
async def register(request: Request, db: Session = Depends(get_db)):
    await validate_csrf(request)
    form = await request.form()
    first_name = form.get("first_name", "").strip()
    last_name = form.get("last_name", "").strip()
    email = form.get("email", "").strip().lower()
    phone = form.get("phone", "").strip()
    password = form.get("password", "")
    password_confirm = form.get("password_confirm", "")
    dog_name = form.get("dog_name", "").strip() or None
    privacy = form.get("privacy")

    errors = []
    if not first_name:
        errors.append("Il nome è obbligatorio.")
    if not last_name:
        errors.append("Il cognome è obbligatorio.")
    if not email or "@" not in email:
        errors.append("Inserisci un indirizzo email valido.")
    if not phone:
        errors.append("Il numero di telefono è obbligatorio.")
    if len(password) < 8:
        errors.append("La password deve essere di almeno 8 caratteri.")
    if not any(c.isdigit() for c in password):
        errors.append("La password deve contenere almeno un numero.")
    if password != password_confirm:
        errors.append("Le password non corrispondono.")
    if not privacy:
        errors.append("Devi accettare la privacy policy per procedere.")

    if errors:
        return templates.TemplateResponse(
            request, "auth/register.html",
            {
                "csrf_token": get_csrf_token(request),
                "errors": errors,
                "form_data": dict(form),
                "current_user": None,
            },
            status_code=422,
        )

    result = AuthService(db).register_user(first_name, last_name, email, phone, password, dog_name)
    if not result["success"]:
        return templates.TemplateResponse(
            request, "auth/register.html",
            {
                "csrf_token": get_csrf_token(request),
                "errors": [result["message"]],
                "form_data": dict(form),
                "current_user": None,
            },
            status_code=422,
        )

    return RedirectResponse(url=f"/register/pending?phone={phone}", status_code=303)


@router.get("/register/pending", response_class=HTMLResponse)
async def register_pending_page(request: Request):
    phone = request.query_params.get("phone", "")
    return templates.TemplateResponse(
        request, "auth/register_pending.html",
        {"current_user": None, "phone": phone},
    )


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/login", status_code=303)


@router.get("/logout")
async def logout_get(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/login", status_code=302)
