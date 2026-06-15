# Centro Cinofilo — Sistema di Prenotazioni

Web application per la gestione delle prenotazioni online di un centro cinofilo.

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0
- **Frontend**: Jinja2 SSR, HTMX, TailwindCSS
- **Database**: PostgreSQL
- **Email**: Resend API
- **Deploy**: Render / Railway (Docker)

---

## Avvio locale

### 1. Prerequisiti

- Python 3.11+
- PostgreSQL locale o remoto (es. Supabase)

### 2. Clona e configura

```bash
# Copia il file di configurazione
cp .env.example .env
```

Modifica `.env` con i tuoi valori:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/cinofilo
SECRET_KEY=chiave_segreta_casuale_lunga
RESEND_API_KEY=re_xxx
EMAIL_FROM=noreply@tuodominio.it
ADMIN_INITIAL_PASSWORD=password_sicura
```

### 3. Installa dipendenze

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# oppure: venv\Scripts\activate # Windows
pip install -r requirements.txt
```

### 4. Migrazioni database

```bash
alembic upgrade head
```

### 5. Avvia il server

```bash
uvicorn app.main:app --reload
```

L'applicazione sarà disponibile su [http://localhost:8000](http://localhost:8000).

---

## Primo avvio — Creazione admin

Al primo avvio, se `ADMIN_INITIAL_PASSWORD` è impostato in `.env`, l'admin viene creato automaticamente con:
- **Username**: valore di `ADMIN_INITIAL_USERNAME` (default: `admin`)
- **Password**: valore di `ADMIN_INITIAL_PASSWORD`

**Importante**: dopo il primo avvio, rimuovi `ADMIN_INITIAL_PASSWORD` dal `.env` per sicurezza.

Il pannello admin è accessibile su `/admin/login`.

---

## Deploy su Render

1. Crea un nuovo servizio **Web Service** su [render.com](https://render.com)
2. Collega il repository GitHub
3. Configura:
   - **Environment**: Docker
   - **Build Command**: *(automatico dal Dockerfile)*
   - **Start Command**: *(definito nel Dockerfile)*
4. Aggiungi tutte le variabili d'ambiente dalla sezione **Environment Variables**
5. Crea un database **PostgreSQL** su Render e copia la connection string in `DATABASE_URL`

### Variabili d'ambiente Render

| Variabile | Valore |
|-----------|--------|
| `DATABASE_URL` | Connection string PostgreSQL |
| `SECRET_KEY` | Stringa casuale sicura (es. 32 byte hex) |
| `RESEND_API_KEY` | API key da [resend.com](https://resend.com) |
| `EMAIL_FROM` | Email mittente verificata su Resend |
| `APP_URL` | URL pubblico del servizio (es. `https://cinofilo.onrender.com`) |
| `ADMIN_INITIAL_PASSWORD` | Solo primo deploy, poi rimuovere |
| `DEBUG` | `false` |

---

## Deploy su Railway

1. Installa [Railway CLI](https://docs.railway.app/develop/cli): `npm i -g @railway/cli`
2. Login: `railway login`
3. Crea progetto: `railway init`
4. Aggiungi PostgreSQL: dal pannello Railway → **New** → **Database** → **PostgreSQL**
5. Configura le variabili: `railway variables set SECRET_KEY=... RESEND_API_KEY=...`
6. Deploy: `railway up`

Railway rileva automaticamente il Dockerfile.

---

## Struttura del progetto

```
app/
  main.py              # Entry point FastAPI
  config.py            # Configurazione Pydantic Settings
  database.py          # Engine SQLAlchemy e sessione
  models/              # Modelli SQLAlchemy
  repositories/        # Accesso al database (repository pattern)
  services/            # Business logic
  routers/             # Router FastAPI (public, bookings, admin)
  templates/           # Template Jinja2
  static/              # File statici (CSS, JS)
  utils/               # Utility (CSRF)
alembic/               # Migrazioni database
tests/                 # Test
```

---

## Funzionalità principali

### Prenotazione utente
- Selezione disciplina → selezione data → selezione slot → dati utente → verifica OTP → conferma
- OTP via email (6 cifre, valido 10 minuti, max 3/ora per email)
- Cancellazione tramite link email (fino a 24 ore prima)

### Pannello admin (`/admin`)
- Gestione prenotazioni con filtri (disciplina, stato, date)
- Aggiornamento stato prenotazione (confermata, completata, no-show)
- Configurazione fasce orarie per disciplina e giorno della settimana
- Blocco date specifiche

### Sicurezza
- CSRF token su tutti i form
- Rate limiting: OTP (3/ora per email), prenotazioni (5/ora per IP), login admin (10/ora per IP)
- Password admin hashata con bcrypt
- Sessioni firmate con `itsdangerous`
- Nessun messaggio tecnico esposto agli utenti

---

## Generare una SECRET_KEY sicura

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
