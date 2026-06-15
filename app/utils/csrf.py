import secrets
from fastapi import HTTPException, Request, status


CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    """Restituisce il token CSRF dalla sessione, creandolo se non esiste."""
    if CSRF_SESSION_KEY not in request.session:
        request.session[CSRF_SESSION_KEY] = secrets.token_hex(32)
    return request.session[CSRF_SESSION_KEY]


async def validate_csrf(request: Request) -> None:
    """Valida il token CSRF per le richieste POST.
    Controlla prima l'header X-CSRF-Token (HTMX), poi il campo form.
    """
    session_token = request.session.get(CSRF_SESSION_KEY)

    form_token = request.headers.get("X-CSRF-Token")

    if not form_token:
        try:
            form_data = await request.form()
            form_token = form_data.get("csrf_token")
        except Exception:
            pass

    if not session_token or not form_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token di sicurezza mancante. Ricarica la pagina e riprova.",
        )

    if not secrets.compare_digest(session_token, form_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token di sicurezza non valido. Ricarica la pagina e riprova.",
        )
