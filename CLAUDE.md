# \# ASD Diamoci la Zampa — Booking App

# 

# \## Descrizione progetto

# Web application professionale per prenotazioni online del centro cinofilo ASD Diamoci la Zampa.

# Architettura monolitica, ottimizzata mobile, a basso costo di mantenimento.

# Gli utenti devono essere autenticati per accedere alla piattaforma e poter prenotare.

# 

# \---

# 

# \## Stack tecnologico

# 

# \### Backend

# \- Python FastAPI

# \- SQLAlchemy (ORM)

# \- Pydantic (validazione)

# \- Alembic (migrazioni)

# \- authlib / httpx-oauth per Google OAuth2

# \- itsdangerous per token verifica email e sessioni

# \- bcrypt per hashing password

# \- slowapi per rate limiting

# \- starlette SessionMiddleware

# 

# \### Frontend

# \- Server Side Rendering con Jinja2

# \- HTMX per interazioni dinamiche

# \- TailwindCSS via CDN

# \- Zero framework JS pesanti (no React, no Vue)

# \- Mobile first sempre

# 

# \### Database

# \- PostgreSQL

# 

# \### Email

# \- Resend API per email transazionali

# 

# \### Deploy

# \- Render (Web Service + PostgreSQL)

# \- Variabili ambiente via `.env`

# 

# \---

# 

# \## Struttura cartelle

# 

# ```

# app/

# &#x20; routers/

# &#x20; services/

# &#x20; models/

# &#x20; repositories/

# &#x20; templates/

# &#x20;   auth/

# &#x20;   booking/

# &#x20;   admin/

# &#x20;   profile/

# &#x20; static/

# &#x20;   img/logo/

# &#x20; utils/

# alembic/

# tests/

# .env.example

# requirements.txt

# Dockerfile

# README.md

# ```

# 

# \---

# 

# \## Design system (colori ufficiali brand)

# 

# ```css

# :root {

# &#x20; --color-primary:     #FC5E02;   /\* arancio brand \*/

# &#x20; --color-primary-dark:#E04E00;

# &#x20; --color-black:       #000000;

# &#x20; --color-white:       #FFFFFF;

# &#x20; --color-gray-light:  #F5F5F5;

# &#x20; --color-gray-mid:    #E0E0E0;

# &#x20; --color-gray-text:   #666666;

# &#x20; --color-success:     #4CAF50;

# &#x20; --color-error:       #D32F2F;

# &#x20; --color-warning:     #F57C00;

# }

# ```

# 

# \- \*\*Font titoli:\*\* Poppins (wght 400, 600, 700)

# \- \*\*Font body/bottoni:\*\* Inter (wght 400, 500)

# \- \*\*Bottoni:\*\* border-radius 10px (NON pill-shaped)

# \- \*\*Navbar:\*\* sfondo nero, logo e link bianchi

# \- \*\*Texture:\*\* ink-splash a 6-8% opacity sul body

# 

# \---

# 

# \## Modello dati — Schema aggiornato

# 

# \### instructors

# \- id

# \- name (es. "Angelo")

# \- username (unique — usato per login admin)

# \- password\_hash

# \- is\_active (boolean, default true)

# \- created\_at

# 

# \### disciplines

# \- id

# \- name (es. "Agility", "Nosework")

# \- instructor\_id (FK instructors)

# \- slot\_duration\_minutes (30, 40 o 60 — NON modificabile da admin)

# \- is\_active (boolean — apertura/chiusura temporanea)

# \- active\_from (date nullable — per discipline stagionali, es. 01/06)

# \- active\_until (date nullable — es. 30/09)

# 

# \### packages

# \- id

# \- user\_id (FK users)

# \- discipline\_id (FK disciplines)

# \- instructor\_id (FK instructors)

# \- total\_lessons (integer, default 8 — TUTTE le discipline hanno pacchetti da 8)

# \- lessons\_completed (integer, default 0)

# \- is\_active (boolean — False = bloccato, aspetta rinnovo)

# \- activated\_at (datetime nullable)

# \- created\_at

# \- UNIQUE: (user\_id, discipline\_id, instructor\_id)

# 

# \### users

# \- id

# \- first\_name

# \- last\_name

# \- email (unique)

# \- dog\_name (nullable)

# \- password\_hash (nullable — null se Google OAuth)

# \- google\_id (nullable)

# \- email\_verified (boolean, default false)

# \- verification\_token (nullable)

# \- is\_active (boolean, default true)

# \- created\_at

# 

# \### appointments

# \- id

# \- user\_id (FK users)

# \- discipline\_id (FK disciplines)

# \- instructor\_id (FK instructors)

# \- package\_id (FK packages, nullable)

# \- appointment\_date

# \- start\_time

# \- end\_time

# \- status (enum: pending, confirmed, cancelled, completed, no\_show)

# \- created\_at

# \- UNIQUE: (discipline\_id, instructor\_id, appointment\_date, start\_time)

# 

# \### availability\_rules

# \- id

# \- discipline\_id (FK disciplines)

# \- instructor\_id (FK instructors)

# \- weekday (0=Lunedì … 6=Domenica)

# \- start\_time

# \- end\_time

# 

# \### blocked\_dates

# \- id

# \- discipline\_id (FK disciplines, nullable — null = blocco globale)

# \- blocked\_date

# \- reason

# \- is\_global (boolean, default false — true = blocco ferie tutto il centro)

# 

# \---

# 

# \## Istruttori e discipline (configurazione fissa)

# 

# | Istruttore | Disciplina           | Durata slot | Lezioni/pacchetto |

# |------------|----------------------|-------------|-------------------|

# | Angelo     | Agility              | 30 min      | 8                 |

# | Angelo     | Swim Dog Sport       | 40 min      | 8 (stagionale)    |

# | Connie     | Agility              | 30 min      | 8                 |

# | Santa      | Educazione di Base   | 60 min      | 8                 |

# | Santa      | Hoopers              | 30 min      | 8                 |

# | Santa      | Rally Obedience      | 30 min      | 8                 |

# | Simona     | Educazione di Base   | 60 min      | 8                 |

# | Simona     | Nosework             | 30 min      | 8                 |

# 

# \*\*Swim Dog Sport:\*\* stagionale (attivo 01/06 → 30/09), griglia 40 min (09:00, 09:40, 10:20…)

# \*\*Educazione di Base:\*\* griglia 60 min

# \*\*Tutte le altre:\*\* griglia 30 min

# 

# \---

# 

# \## Logica prenotazioni

# 

# \### Flusso utente

# 1\. Login → scelta istruttore → scelta disciplina → range picker date → lista slot → prenota

# 

# \### Regole temporali

# \- Prenotabile fino a \*\*12h prima\*\* dello slot (preavviso minimo)

# \- Cancellabile fino a \*\*24h prima\*\* dello slot

# \- \*\*Max 2 prenotazioni per settimana\*\* per combinazione utente+disciplina+istruttore

# 

# \### Finestra prenotazione — settimane sincronizzate per tutti

# \- Visibili sempre le \*\*prossime 2 settimane\*\* complete (Lunedì → Domenica)

# \- Ogni \*\*Sabato alle 00:00\*\* si apre automaticamente la settimana successiva

# \- Tutti gli utenti vedono le stesse date nello stesso momento (nessun vantaggio individuale)

# 

# \### Slot consigliati (anti-buco)

# \- Se esiste già una prenotazione in un giorno, i \*\*2 slot immediatamente successivi\*\* vengono evidenziati in verde con badge "Slot consigliato"

# \- Obiettivo: ridurre i buchi nel calendario dell'istruttore

# 

# \### Pacchetti

# \- Ogni combinazione utente+istruttore+disciplina ha il proprio pacchetto indipendente

# \- Il contatore `lessons\_completed` scala \*\*solo\*\* quando admin segna status = `completed`

# \- Quando `lessons\_completed >= total\_lessons` → `package.is\_active = False` automaticamente

# \- Il blocco è \*\*specifico per combinazione\*\* (altre discipline/istruttori non vengono bloccate)

# \- Solo admin può riattivare un pacchetto dopo pagamento esterno (contanti/bonifico)

# \- Un utente con pacchetto esaurito su Agility con Angelo può ancora prenotare Nosework con Simona

# 

# \### Griglie slot per disciplina

# ```python

# SLOT\_DURATION = {

# &#x20;   "Agility":             30,

# &#x20;   "Hoopers":             30,

# &#x20;   "Rally Obedience":     30,

# &#x20;   "Nosework":            30,

# &#x20;   "Swim Dog Sport":      40,

# &#x20;   "Educazione di Base":  60,

# }

# ```

# La durata slot è fissa nel codice — NON configurabile dall'admin.

# 

# \---

# 

# \## Autenticazione utente

# 

# \### Prima schermata

# \- Utenti non autenticati → redirect automatico a `/login`

# \- Nessuna pagina accessibile senza autenticazione

# 

# \### Registrazione (`/register`)

# Campi obbligatori: Nome, Cognome, Email, Password (min 8 caratteri, 1 numero), Conferma password

# Campi opzionali: Nome del cane

# Flusso: form → email verifica (token itsdangerous 24h) → click link → account attivo → login

# 

# \### Login (`/login`)

# \- Email + Password

# \- Accedi con Google (OAuth2)

# \- Account non verificato → messaggio chiaro, no accesso

# 

# \### Sessioni

# \- Cookie firmato httponly, secure in produzione, samesite=lax

# \- Scadenza: 7 giorni con rinnovo automatico

# 

# \---

# 

# \## Admin multi-utente

# 

# \- \*\*4 account separati:\*\* Angelo, Connie, Santa, Simona

# \- Stesse viste e permessi per tutti (nessuna restrizione per ruolo)

# \- Sessioni concorrenti permesse (no lock su logout altrui)

# \- Login admin: `/admin/login` con credenziali Instructor (username + password)

# \- Cambio password dal pannello + reset via email ("password dimenticata")

# 

# \### Funzioni admin

# \- Gestione disponibilità (giorni e orari per disciplina — durata slot read-only)

# \- Apertura/chiusura temporanea disciplina

# \- Configurazione periodo stagionale per disciplina (active\_from / active\_until)

# \- Blocco ferie globale (tutte le discipline, range date con motivo)

# \- Vista prenotazioni con filtri

# \- Segnare lezione come completed / no\_show / cancelled

# \- Vista pacchetti utente con barra progresso (X/8 lezioni)

# \- Rinnova pacchetto (reset lessons\_completed=0, is\_active=True)

# \- Blocca/sblocca pacchetto manualmente

# 

# \---

# 

# \## Email transazionali (Resend)

# 

# \- Verifica account (link token)

# \- Conferma prenotazione

# \- Cancellazione prenotazione

# \- Pacchetto esaurito (avviso all'utente)

# \- Reset password admin

# \- Mittente: `DiamociLaZampa <noreply@seicoenergia.it>` (dominio verificato temporaneo)

# 

# \---

# 

# \## Regole di sviluppo

# 

# \### Generali

# \- Architettura monolitica — nessun microservizio, nessun WebSocket

# \- Codice commentato in italiano dove utile

# \- Nessun TODO, nessuna print() di debug in produzione

# \- Gestione errori sempre con messaggi in italiano e linguaggio umano

# 

# \### Backend

# \- Repository pattern per accesso DB

# \- Transazioni DB per operazioni critiche (race conditions prenotazioni)

# \- Rate limiting: login 10/ora per IP, registrazione 5/ora per IP, prenotazioni 10/ora per utente

# \- CSRF protection su tutti i form

# \- Logging: registrazioni, login falliti, prenotazioni, cancellazioni, errori email, login admin

# 

# \### Frontend

# \- Mobile first — touch target minimo 48px

# \- Errori in linguaggio umano (mai stack trace, mai codici HTTP visibili)

# \- HTMX per aggiornamenti parziali

# \- Tutto in italiano — nessuna stringa in inglese visibile all'utente

# 

# \### Middleware obbligatori

# \- SessionMiddleware

# \- CSRF middleware

# \- Rate limiting (slowapi)

# \- Auth middleware su ogni route protetta

# 

# \---

# 

# \## Variabili ambiente (.env.example)

# 

# ```

# DATABASE\_URL=

# SECRET\_KEY=

# RESEND\_API\_KEY=

# GOOGLE\_CLIENT\_ID=

# GOOGLE\_CLIENT\_SECRET=

# GOOGLE\_REDIRECT\_URI=

# BASE\_URL=

# ENVIRONMENT=development

# ```

# 

# \---

# 

# \## Profilo utente (`/profile`)

# 

# \- Modifica dati (nome, cognome, nome cane)

# \- Cambio password (solo per utenti non-Google)

# \- Le mie prenotazioni: future (confirmed/pending) + storico (completed)

# \- I miei pacchetti: barra progresso X/8 per ogni combinazione attiva

# 

# \---

# 

# \## Privacy

# \- Checkbox privacy obbligatoria in registrazione

# \- Pagina `/privacy`

# \- Solo cookie essenziali + sessione

# 

# \---

# 

# \## Deploy (Render)

# \- Web Service: `pip install -r requirements.txt \&\& alembic upgrade head` → `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

# \- PostgreSQL: piano a pagamento (non Free — scade dopo 30 giorni)

# \- Dominio custom: `prenotazioni.asdiamocilazampa.it` via CNAME

