# PROMPT INIZIALE — DA INCOLLARE IN CLAUDE CODE

---

Crea da zero la web application completa descritta nel CLAUDE.md.

## Ordine di esecuzione obbligatorio

Procedi in questo ordine esatto, completando ogni fase prima di passare alla successiva:

### FASE 1 — Struttura progetto
Crea tutta la struttura di cartelle:
```
app/routers/ app/services/ app/models/ app/repositories/
app/templates/ app/static/css/ app/static/js/ app/utils/
alembic/ tests/
```

### FASE 2 — Dipendenze e configurazione
- `requirements.txt` completo
- `.env.example` con tutte le variabili documentate
- `app/config.py` con settings Pydantic BaseSettings
- `app/database.py` con engine SQLAlchemy e session

### FASE 3 — Modelli database
Crea tutti i modelli SQLAlchemy in `app/models/`:
- `discipline.py`
- `customer.py`
- `appointment.py` — con Enum status (pending/confirmed/cancelled/completed/no_show)
- `availability_rule.py`
- `blocked_date.py`
- `otp_code.py`
- `admin_user.py`

Vincolo UNIQUE obbligatorio su appointments(discipline_id, appointment_date, start_time).

### FASE 4 — Migrazioni Alembic
- Inizializza Alembic
- Crea migrazione iniziale con schema completo

### FASE 5 — Repository layer
Crea `app/repositories/` con un file per ogni modello.
Tutta la logica di accesso DB deve stare qui, mai nei router.

### FASE 6 — Servizi
Crea `app/services/`:
- `booking_service.py` — logica prenotazioni con gestione race conditions e transazioni
- `otp_service.py` — generazione, invio, verifica OTP
- `email_service.py` — invio email con Resend API (OTP, conferma, cancellazione)
- `availability_service.py` — calcolo slot disponibili da availability_rules
- `admin_service.py` — autenticazione admin

### FASE 7 — Router FastAPI
Crea `app/routers/`:
- `public.py` — homepage, selezione disciplina, selezione slot, form utente, OTP
- `bookings.py` — creazione, conferma, cancellazione prenotazioni
- `admin.py` — login admin, dashboard, gestione disponibilità, blocco date, gestione prenotazioni

Rate limiting su: OTP (max 3/ora per email), prenotazioni (max 5/ora per IP), login admin (max 10/ora per IP).

### FASE 8 — Templates Jinja2
Crea `app/templates/`:
- `base.html` — layout base con TailwindCSS CDN, HTMX CDN, meta mobile
- `index.html` — homepage con card discipline grandi
- `booking/select_slot.html` — calendario + slot disponibili
- `booking/user_form.html` — form dati utente (nome, cognome, email, telefono, privacy checkbox)
- `booking/otp_verify.html` — inserimento OTP
- `booking/confirmed.html` — conferma finale
- `booking/cancel.html` — cancellazione prenotazione
- `admin/login.html` — login admin
- `admin/dashboard.html` — pannello admin completo
- `privacy.html` — pagina privacy policy

Design: mobile first, minimal, professionale. Bottoni grandi. Nessun popup. Colori neutri alto contrasto.
Errori sempre in linguaggio umano. MAI messaggi tecnici visibili.

### FASE 9 — App principale
- `app/main.py` — FastAPI app con tutti i router, middleware CSRF, logging, gestione errori globale
- `Dockerfile` funzionante
- `README.md` professionale in italiano con istruzioni deploy Render e Railway

## Vincoli tecnici da rispettare in ogni file

- Gestione race conditions nelle prenotazioni con `SELECT FOR UPDATE` o equivalent
- OTP: scade dopo 10 minuti, monouso
- Validazione input Pydantic su tutti gli endpoint
- Errori HTTP restituiti con messaggi user-friendly (mai stack trace)
- Logging su: creazione/cancellazione prenotazioni, OTP inviati/verificati, errori email, login admin falliti
- CSRF token su tutti i form
- Password admin hashata con bcrypt al primo setup

## Note finali

Scrivi codice pronto per produzione MVP.
Nessun TODO, nessuna print() di debug.
Commenta le parti non ovvie.
Se hai dubbi su una scelta implementativa, scegli sempre la soluzione più semplice e manutenibile.
