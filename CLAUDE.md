# Centro Cinofilo — Booking App

## Descrizione progetto

Web application professionale per prenotazioni online di un centro cinofilo.
MVP leggero, monolitico, ottimizzato mobile, a basso costo di mantenimento.
Gli utenti devono essere autenticati per accedere alla piattaforma e poter prenotare.

## Stack tecnologico

### Backend

* Python FastAPI
* SQLAlchemy (ORM)
* Pydantic (validazione)
* Alembic (migrazioni)
* authlib o httpx-oauth per Google OAuth2
* itsdangerous per token di verifica email e sessioni

### Frontend

* Server Side Rendering con Jinja2
* HTMX per interazioni dinamiche
* TailwindCSS (CDN o build minimo)
* Zero framework JS pesanti (no React, no Vue)
* Mobile first sempre

### Database

* PostgreSQL (compatibile Supabase)

### Email

* Resend API per email transazionali

### Deploy target

* Render o Railway
* Docker opzionale ma consigliato
* Variabili ambiente via `.env`

## Struttura cartelle obbligatoria

```
app/
  routers/
  services/
  models/
  repositories/
  templates/
    auth/
    booking/
    admin/
  static/
  utils/
alembic/
tests/
.env.example
requirements.txt
Dockerfile
README.md
```

## Autenticazione utente (NUOVO SISTEMA)

### Prima schermata

La prima pagina che vede l'utente NON autenticato è sempre `/login`.
Nessuna pagina della piattaforma è accessibile senza autenticazione.
Redirect automatico a `/login` per utenti non autenticati.

### Registrazione

Percorso: `/register`
Campi obbligatori:

* Nome
* Cognome
* Email
* Password (min 8 caratteri, almeno 1 numero)
* Conferma password

Campi opzionali:

* Nome del cane (solo a scopo identificativo del profilo)

Flusso:

1. Utente compila il form di registrazione
2. Sistema invia email di verifica con link firmato (token itsdangerous, scadenza 24h)
3. Utente clicca il link → account attivato → redirect a `/login`
4. Fino alla verifica email, il login è bloccato con messaggio chiaro

### Login

Percorso: `/login`
Due modalità:

1. **Email + Password** — form classico
2. **Accedi con Google** — OAuth2 Google

Flusso email/password:

1. Utente inserisce email e password
2. Verifica che l'account sia email\_verified = true
3. Se non verificato → messaggio "Controlla la tua email per attivare l'account"
4. Se credenziali errate → messaggio "Email o password non corretti"
5. Login corretto → sessione attiva → redirect a `/`

Flusso Google OAuth:

1. Click "Accedi con Google" → redirect Google consent screen
2. Callback su `/auth/google/callback`
3. Se email già registrata → collega account Google
4. Se email nuova → crea account automaticamente (email\_verified = true)
5. Sessione attiva → redirect a `/`

### Sessioni

* Usare sessioni server-side con cookie firmato (itsdangerous o starlette SessionMiddleware)
* Cookie httponly, secure in produzione, samesite=lax
* Scadenza sessione: 7 giorni con rinnovo automatico

### Logout

* Percorso: `/logout`
* Invalida sessione server-side
* Redirect a `/login`

## Database — Schema aggiornato

### Tabella users (sostituisce customers)

* id
* first\_name
* last\_name
* email (unique)
* dog\_name (nullable)
* password\_hash (nullable — null se registrato via Google)
* google\_id (nullable)
* email\_verified (boolean, default false)
* verification\_token (nullable)
* is\_active (boolean, default true)
* created\_at

### Tabella disciplines

* id
* name

### Tabella appointments

* id
* discipline\_id (FK disciplines)
* user\_id (FK users) ← era customer\_id
* appointment\_date
* start\_time
* end\_time
* status (enum: pending, confirmed, cancelled, completed, no\_show)
* created\_at

Vincolo UNIQUE: (discipline\_id, appointment\_date, start\_time)

### Tabella availability\_rules

* id
* discipline\_id
* weekday
* start\_time
* end\_time

### Tabella blocked\_dates

* id
* discipline\_id
* blocked\_date
* reason

### Tabella admin\_users

* id
* username
* password\_hash

NON esiste più la tabella otp\_codes.

## Regole di sviluppo

### Generali

* Architettura monolitica semplice — nessun microservizio
* Nessun WebSocket
* Codice pulito, commentato in italiano dove utile
* Ogni file deve avere uno scopo chiaro e unico
* Nessuna dipendenza non necessaria

### Backend

* Ogni router in file separato
* Usare repository pattern per accesso DB
* Transazioni DB per operazioni critiche (prenotazioni)
* Gestire race conditions con lock appropriati
* Rate limiting su: login (max 10/ora per IP), registrazione (max 5/ora per IP), prenotazioni (max 10/ora per utente)
* CSRF protection attiva su tutti i form
* Input sempre validato con Pydantic
* Password hashata con bcrypt
* Logging strutturato su: registrazioni, login, prenotazioni, cancellazioni, errori email, login admin

### Middleware obbligatori

* SessionMiddleware (starlette)
* CSRF middleware
* Rate limiting middleware
* Auth middleware (verifica sessione su ogni route protetta)

### Frontend

* Mobile first — bottoni grandi, touch friendly
* Nessun popup invasivo
* Feedback errori in linguaggio umano
* MAI messaggi tecnici visibili all'utente (no 422, no stack trace)
* HTMX per aggiornamenti parziali pagina
* Jinja2 per rendering server side
* TailwindCSS utility classes
* Accessibilità: contrasto alto, label form corretti

## Discipline disponibili

* Agility
* Dog Training 1
* Dog Training 2
* Dog Training 3

## Logica prenotazioni

* Solo utenti autenticati possono prenotare
* Slot fissi da 30 minuti
* Orari disponibili: 09:00 → 21:00 (ogni 30 min)
* Nessun buffer tra slot
* 1 prenotazione per slot per disciplina
* Categorie diverse possono condividere lo stesso orario
* Prenotabile massimo entro 30 giorni dalla data odierna
* Blocco giorno successivo: prenotabile solo fino alle 23:59 del giorno precedente
* Cancellazione consentita solo entro 24h dall'appuntamento

## Admin

* Login classico con username + password hashata (separato dal sistema utenti)
* Percorso: `/admin/login`
* Funzioni: gestione disponibilità ricorrenti, blocco date, gestione prenotazioni (view, cancel, completed, no\_show)

## Email

* Verifica account (link con token)
* Conferma prenotazione
* Cancellazione prenotazione
* Template puliti e leggibili

## Privacy

* Checkbox privacy policy obbligatoria nella registrazione
* Pagina /privacy
* Solo cookie essenziali + cookie di sessione

## Qualità codice

* Nessun TODO lasciato nel codice finale
* Nessuna print() di debug in produzione
* Usare logger Python standard
* Gestire sempre le eccezioni con messaggi utente friendly
* Ogni endpoint API deve avere validazione input e gestione errore

## Variabili ambiente richieste (.env.example)

```
DATABASE\\\_URL=
SECRET\\\_KEY=
RESEND\\\_API\\\_KEY=
GOOGLE\\\_CLIENT\\\_ID=
GOOGLE\\\_CLIENT\\\_SECRET=
GOOGLE\\\_REDIRECT\\\_URI=
BASE\\\_URL=
ENVIRONMENT=development
```

## Deploy

* Dockerfile funzionante
* Istruzioni per Render e Railway nel README
* README professionale in italiano con sezione setup Google OAuth



