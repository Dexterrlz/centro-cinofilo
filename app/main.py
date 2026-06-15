import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import SessionLocal
from app.routers import admin, bookings, public
from app.routers import auth as auth_router
from app.routers import profile as profile_router
from app.utils.auth import NotAuthenticated
from app.utils.csrf import get_csrf_token
from app.utils.date_it import register_date_filters

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory="app/templates")
register_date_filters(templates)


def _seed_initial_data():
    """Popola i dati iniziali al primo avvio (discipline e admin)."""
    db = SessionLocal()
    try:
        from app.repositories.discipline_repository import DisciplineRepository
        from app.services.admin_service import AdminService

        disc_repo = DisciplineRepository(db)
        if disc_repo.count() == 0:
            initial_disciplines = [
                ("Agility", "Percorso ad ostacoli per cane e conduttore", "#F59E0B"),
                ("Dog Training 1", "Addestramento base", "#3B82F6"),
                ("Dog Training 2", "Addestramento intermedio", "#8B5CF6"),
                ("Dog Training 3", "Addestramento avanzato", "#10B981"),
            ]
            for name, desc, color in initial_disciplines:
                disc_repo.create(name=name, description=desc, color=color)
            logger.info("Discipline iniziali create.")

        admin_service = AdminService(db)
        if settings.ADMIN_INITIAL_PASSWORD and not admin_service.admin_exists():
            admin_service.create_admin(
                username=settings.ADMIN_INITIAL_USERNAME or "admin",
                password=settings.ADMIN_INITIAL_PASSWORD,
            )
            logger.info("Admin iniziale creato: username='%s'", settings.ADMIN_INITIAL_USERNAME)

    except Exception as exc:
        logger.error("Errore seed dati iniziali: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_initial_data()
    yield
    logger.info("Applicazione terminata.")


app = FastAPI(
    title="Centro Cinofilo — Booking",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

# SessionMiddleware deve essere aggiunta per ULTIMA (diventa outer layer)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="session",
    max_age=7 * 24 * 3600,
    https_only=not settings.DEBUG,
    same_site="lax",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(profile_router.router)
app.include_router(public.router)
app.include_router(bookings.router)
app.include_router(admin.router)


# ─── Gestione globale errori ──────────────────────────────────────────────────

@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "errors/404.html",
        {"csrf_token": get_csrf_token(request), "current_user": None},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error("Errore interno: %s", exc)
    return templates.TemplateResponse(
        request, "errors/500.html",
        {"csrf_token": get_csrf_token(request), "current_user": None},
        status_code=500,
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return templates.TemplateResponse(
        request, "errors/500.html",
        {
            "csrf_token": get_csrf_token(request),
            "current_user": None,
            "error_msg": "Troppe richieste. Attendi qualche minuto e riprova.",
        },
        status_code=429,
    )
