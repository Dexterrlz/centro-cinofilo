import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.config import settings
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
                "unverified": result.get("unverified", False),
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
    password = form.get("password", "")
    password_confirm = form.get("password_confirm", "")
    dog_name = form.get("dog_name", "").strip() or None
    privacy = form.get("privacy")

    errors = []
    if not first_name:
        errors.append("Il nome e obbligatorio.")
    if not last_name:
        errors.append("Il cognome e obbligatorio.")
    if not email or "@" not in email:
        errors.append("Inserisci un indirizzo email valido.")
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

    result = AuthService(db).register_user(first_name, last_name, email, password, dog_name)
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

    return RedirectResponse(url="/verify-pending", status_code=303)


# ─── Verifica email ───────────────────────────────────────────────────────────

@router.get("/verify-pending", response_class=HTMLResponse)
async def verify_pending_page(request: Request):
    return templates.TemplateResponse(
        request, "auth/verify_pending.html",
        {"current_user": None},
    )


@router.get("/verify-email/{token}", response_class=HTMLResponse)
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    result = AuthService(db).verify_email(token)
    if not result["success"]:
        return templates.TemplateResponse(
            request, "auth/verify_pending.html",
            {"error": result["message"], "current_user": None},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "auth/verify_success.html",
        {"already_verified": result.get("already_verified", False), "current_user": None},
    )


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@router.get("/auth/google", response_class=HTMLResponse)
async def google_login(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        return RedirectResponse(url="/login?error=google_non_configurato", status_code=302)
    from app.utils.oauth import oauth
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        return RedirectResponse(url="/login?error=google_non_configurato", status_code=302)
    try:
        from app.utils.oauth import oauth
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo") or {}
        google_id = userinfo.get("sub")
        email = userinfo.get("email")
        first_name = userinfo.get("given_name") or userinfo.get("name", "Utente")
        last_name = userinfo.get("family_name") or ""

        if not google_id or not email:
            return RedirectResponse(url="/login?error=google_dati_mancanti", status_code=302)

        user = AuthService(db).get_or_create_google_user(google_id, email, first_name, last_name)
        request.session["user_id"] = user.id
        logger.info("Login Google per user_id=%s", user.id)
        return RedirectResponse(url="/", status_code=302)
    except Exception as exc:
        logger.error("Errore Google OAuth: %s", exc)
        return RedirectResponse(url="/login?error=google_errore", status_code=302)


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/login", status_code=303)


@router.get("/logout")
async def logout_get(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/login", status_code=302)
