# PROMPT REDESIGN — ASD Diamoci la Zampa (Booking App)

## Obiettivo
Questo prompt gestisce un refactor architetturale completo della piattaforma.
Procedi SEMPRE in questo ordine esatto, completando e verificando ogni fase prima di passare alla successiva.
NON saltare fasi. NON modificare file non menzionati esplicitamente.

## PROCEDURA DI SICUREZZA OBBLIGATORIA (eseguire PRIMA di tutto)
```bash
git status                    # verifica che non ci siano modifiche non committate
git checkout -b redesign/v2   # crea branch dedicato, MAI lavorare su main
git branch                    # conferma di essere sul branch corretto
```
Inventaria i file esistenti prima di modificarli:
```bash
find app/ -name "*.py" | sort
find app/templates/ -name "*.html" | sort
```
Per ogni file che modifichi: leggi prima, modifica dopo. Preserva TUTTI i tag Jinja2, attributi HTMX, campi form. Lavora un file alla volta. Esegui `git diff --stat` prima di ogni commit parziale. Se qualcosa è ambiguo, fermati e chiedi.

---

## FASE 1 — MIGRAZIONE DATABASE

### Nuovi modelli da creare

**Istruttori** (`app/models/instructor.py`):
```python
class Instructor(Base):
    __tablename__ = "instructors"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)          # es. "Angelo"
    username = Column(String, unique=True)         # per login admin
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Discipline aggiornate** (`app/models/discipline.py`):
Aggiungi campi:
```python
instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=False)
slot_duration_minutes = Column(Integer, nullable=False)  # 30, 40 o 60 — NON modificabile da admin
is_active = Column(Boolean, default=True)                # apertura/chiusura stagionale
active_from = Column(Date, nullable=True)                # es. 1 Giugno (stagionale)
active_until = Column(Date, nullable=True)               # es. 30 Settembre (stagionale)
```

**Pacchetti** (`app/models/package.py`):
```python
class Package(Base):
    __tablename__ = "packages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False)
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=False)
    total_lessons = Column(Integer, nullable=False, default=8)
    lessons_completed = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)     # False = bloccato, aspetta rinnovo
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # UNIQUE: un solo pacchetto attivo per utente+disciplina+istruttore
    __table_args__ = (
        UniqueConstraint('user_id', 'discipline_id', 'instructor_id',
                        name='uq_active_package'),
    )
```

**Appointments aggiornato** (`app/models/appointment.py`):
- Rinomina `customer_id` → `user_id` (se non già fatto)
- Aggiungi `instructor_id = Column(Integer, ForeignKey("instructors.id"))`
- Aggiungi `package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)`
- Mantieni tutti i campi esistenti

**Availability rules aggiornato** (`app/models/availability_rule.py`):
- Aggiungi `instructor_id = Column(Integer, ForeignKey("instructors.id"))`
- Mantieni tutti i campi esistenti

**Blocked dates aggiornato** (`app/models/blocked_date.py`):
- Aggiungi campo `is_global = Column(Boolean, default=False)` per blocchi ferie di tutto il centro
- Mantieni tutti i campi esistenti

### Migrazione Alembic
```bash
alembic revision --autogenerate -m "v2_instructor_packages_system"
alembic upgrade head
```

### Seed dati iniziali
Crea `app/utils/seed.py` con funzione `seed_initial_data()`:
```python
# Istruttori
instructors = [
    {"name": "Angelo", "username": "angelo"},
    {"name": "Connie", "username": "connie"},
    {"name": "Santa", "username": "santa"},
    {"name": "Simona", "username": "simona"},
]

# Discipline con istruttore e durata slot
disciplines = [
    {"name": "Agility",           "instructor": "Angelo",  "slot_duration": 30},
    {"name": "Swim Dog Sport",    "instructor": "Angelo",  "slot_duration": 40,
     "active_from": "06-01", "active_until": "09-30"},  # stagionale
    {"name": "Agility",           "instructor": "Connie",  "slot_duration": 30},
    {"name": "Educazione di Base","instructor": "Santa",   "slot_duration": 60},
    {"name": "Hoopers",           "instructor": "Santa",   "slot_duration": 30},
    {"name": "Rally Obedience",   "instructor": "Santa",   "slot_duration": 30},
    {"name": "Educazione di Base","instructor": "Simona",  "slot_duration": 60},
    {"name": "Nosework",          "instructor": "Simona",  "slot_duration": 30},
]
# Tutte le discipline hanno pacchetti da 8 lezioni
```
Le password iniziali degli istruttori vengono generate hashate con bcrypt.
Stampa le password in chiaro a video UNA sola volta durante il seed — non salvarle nel codice.

---

## FASE 2 — BOOKING ENGINE

### Regole temporali (sostituiscono quelle esistenti)
```python
# In app/services/booking_service.py

MIN_ADVANCE_HOURS = 12      # deve mancare almeno 12h alla lezione
CANCEL_ADVANCE_HOURS = 24   # cancellabile fino a 24h prima
MAX_LESSONS_PER_WEEK = 2    # per combinazione utente+disciplina+istruttore
```

### Finestra prenotazione — settimane sincronizzate per tutti
La finestra mostra SEMPRE le prossime 2 settimane di calendario (Lun-Dom).
Ogni Sabato alle 00:00 si apre automaticamente una nuova settimana.

```python
def get_booking_window():
    """
    Ritorna (start_date, end_date) della finestra prenotabile.
    Mostra sempre le prossime 2 settimane complete (Lun-Dom).
    Ogni Sabato a mezzanotte si apre la settimana successiva.
    """
    today = date.today()
    # Trova il lunedì della settimana corrente
    current_monday = today - timedelta(days=today.weekday())
    # La finestra inizia sempre dal lunedì della settimana corrente
    start = current_monday
    # Mostra sempre 2 settimane complete = 14 giorni
    end = start + timedelta(days=13)  # fino alla domenica della settimana successiva
    return start, end
```

### Logica slot consigliati (anti-buco)
```python
def get_suggested_slots(available_slots, existing_bookings_that_day):
    """
    Marca come 'suggested' i 2 slot immediatamente successivi
    a ogni prenotazione già esistente nel giorno.
    """
    suggested = set()
    for booking in existing_bookings_that_day:
        booking_end = booking.end_time
        # Trova i 2 slot che iniziano subito dopo la fine della prenotazione
        for i, slot in enumerate(available_slots):
            if slot.start_time == booking_end:
                suggested.add(slot.start_time)
                if i + 1 < len(available_slots):
                    suggested.add(available_slots[i + 1].start_time)
    return suggested
```

### Controllo pacchetto attivo
Prima di ogni prenotazione verificare:
1. Esiste un pacchetto attivo per utente+disciplina+istruttore?
2. `package.is_active == True`?
3. `package.lessons_completed < package.total_lessons`?
4. L'utente non ha già 2 prenotazioni in quella settimana per quella combinazione?

Se una di queste condizioni fallisce → blocca la prenotazione con messaggio specifico in italiano.

### Aggiornamento contatore pacchetto
Quando admin segna una lezione come `completed`:
```python
def complete_lesson(appointment_id, db):
    appointment = get_appointment(appointment_id, db)
    appointment.status = "completed"
    
    # Scala il contatore del pacchetto
    package = get_active_package(
        appointment.user_id,
        appointment.discipline_id,
        appointment.instructor_id,
        db
    )
    if package:
        package.lessons_completed += 1
        # Se ha raggiunto il totale, blocca automaticamente
        if package.lessons_completed >= package.total_lessons:
            package.is_active = False
            # Invia email all'utente: "Hai completato il tuo pacchetto, contatta il centro per rinnovare"
```

### Griglia slot variabile per disciplina
```python
def generate_slots(discipline, date, start_time, end_time):
    """
    Genera gli slot in base alla durata configurata nella disciplina.
    slot_duration_minutes: 30, 40 o 60
    """
    slots = []
    current = datetime.combine(date, start_time)
    end = datetime.combine(date, end_time)
    duration = timedelta(minutes=discipline.slot_duration_minutes)
    
    while current + duration <= end:
        slots.append({
            "start": current.time(),
            "end": (current + duration).time()
        })
        current += duration
    return slots
```

---

## FASE 3 — ADMIN MULTI-UTENTE

### Autenticazione admin
Sostituisci il singolo `admin_user` con il modello `Instructor` che ha già `username` e `password_hash`.
Tutti gli istruttori hanno accesso completo — stesse viste, stesse azioni, nessuna restrizione per ruolo.

Router `app/routers/admin.py`:
- Login usa le credenziali di `Instructor` (username + password)
- Sessione admin separata dalla sessione utente normale
- Più sessioni admin concorrenti sono permesse (no lock su logout)

### Funzioni admin aggiornate

**Gestione disponibilità:**
- Dropdown istruttore → dropdown disciplina → configura giorni e orari
- La durata slot è mostrata ma NON modificabile (read-only, grigio)

**Apertura/chiusura disciplina:**
```
[Disciplina: Swim Dog Sport — Angelo]
Stato: ● Attiva  ○ Chiusa temporaneamente
Periodo stagionale: Dal [01/06] Al [30/09]
[Chiudi temporaneamente]  [Salva periodo stagionale]
```

**Blocco ferie globale:**
```
Blocca TUTTE le discipline:
Dal: [22/12/2025]  Al: [03/01/2026]
Motivo: Ferie natalizie
[Applica blocco globale]
```

**Gestione pacchetti utente:**
Per ogni utente, l'admin vede:
```
Mario Rossi
├── Agility (Angelo): 6/8 lezioni completate ████████░░  [Blocca] [Rinnova]
└── Nosework (Simona): 8/8 ██████████ PACCHETTO ESAURITO [Rinnova]
```
Bottone "Rinnova": resetta `lessons_completed = 0`, `is_active = True`, crea nuovo record package.
Bottone "Blocca": imposta `is_active = False` manualmente.

**Cambio password istruttori:**
Ogni istruttore può cambiare la propria password dal pannello.
Aggiungi endpoint `GET/POST /admin/change-password`.
Aggiungi link "Password dimenticata" nel login admin → flusso email reset (usa lo stesso sistema itsdangerous già esistente per gli utenti normali).

---

## FASE 4 — FRONTEND UTENTE

### Flusso prenotazione aggiornato

**Step 1 — Scelta istruttore:**
Grid di card istruttori (solo quelli con discipline attive):
```
[Angelo]          [Connie]
Agility           Agility
Swim Dog Sport

[Santa]           [Simona]
Ed. Base          Ed. Base
Hoopers           Nosework
Rally Obedience
```

**Step 2 — Scelta disciplina:**
Dopo aver scelto l'istruttore, mostra le sue discipline attive come card.
Se l'utente ha già un pacchetto attivo per quella combinazione → mostra badge "Pacchetto attivo: X/8 lezioni".
Se pacchetto esaurito → mostra "Pacchetto esaurito — contatta il centro per rinnovare" (non cliccabile).

**Step 3 — Selettore date stile range picker:**

Sostituisci il vecchio calendario a griglia con un range picker moderno:

```html
<div class="date-range-picker">
  <div class="date-range-inputs">
    <div class="date-input">
      <label>Dal</label>
      <input type="date" id="date-from" min="{today}" max="{window_end}">
    </div>
    <span class="date-range-arrow">→</span>
    <div class="date-input">
      <label>Al</label>
      <input type="date" id="date-to" min="{today}" max="{window_end}">
    </div>
  </div>
  <div class="quick-select">
    <button onclick="selectWeek(1)">Questa settimana</button>
    <button onclick="selectWeek(2)">Prossima settimana</button>
    <button onclick="selectAll()">Entrambe le settimane</button>
  </div>
</div>
```

Regole del range picker:
- Minimo: oggi + 12h (rispetta la regola preavviso minimo)
- Massimo: fine della finestra delle 2 settimane
- Giorni non disponibili (festivi, discipline chiuse, ferie): grigi, non selezionabili
- Le date fuori dalla finestra delle 2 settimane: non selezionabili

**Step 4 — Lista slot disponibili nel range:**

Dopo la selezione del range, HTMX carica la lista degli slot disponibili:

```
Risultati: 14 Giugno — 21 Giugno
────────────────────────────────
Lunedì 14 Giugno
  🟢 15:30 — 16:00  "Slot consigliato"    [Prenota]
  🟢 16:00 — 16:30  "Slot consigliato"    [Prenota]
  ⚪ 17:00 — 17:30                         [Prenota]
  ⚪ 18:00 — 18:30                         [Prenota]

Martedì 15 Giugno
  ⚪ 15:00 — 15:30                         [Prenota]
  ⚪ 15:30 — 16:00                         [Prenota]
  ...
```

CSS per slot consigliato:
```css
.slot-suggested {
  background: #EDF7ED;
  border: 1.5px solid #4CAF50;
  border-radius: 10px;
  padding: 12px 16px;
}
.slot-suggested .slot-badge {
  color: #2E7D32;
  font-size: 12px;
  font-weight: 700;
}
.slot-normal {
  background: var(--color-white);
  border: 1px solid var(--color-cipria);
  border-radius: 10px;
  padding: 12px 16px;
}
```

**Profilo utente — sezione pacchetti:**

Nel profilo utente aggiungi sezione "I miei pacchetti":
```
I miei pacchetti
────────────────
🏃 Agility con Angelo
   ████████░░  6 di 8 lezioni completate
   2 lezioni rimanenti

🦴 Nosework con Simona
   ██████████  8 di 8 lezioni completate
   ⚠️ Pacchetto esaurito — contatta il centro per rinnovare
```

---

## FASE 5 — REDESIGN FRONTEND (colori ufficiali brand)

### Design system ufficiale ASD Diamoci la Zampa
Sostituisci COMPLETAMENTE la palette terracotta/cream con i colori ufficiali del brand.

**CSS custom properties (sovrascrivere tutte le variabili esistenti in main.css/base.html):**
```css
:root {
  --color-primary:     #FC5E02;   /* arancio brand — bottoni, accent, link attivi */
  --color-primary-dark:#E04E00;   /* hover bottoni */
  --color-black:       #000000;   /* testi principali, titoli */
  --color-white:       #FFFFFF;   /* sfondi, card */
  --color-gray-light:  #F5F5F5;   /* sfondo pagina */
  --color-gray-mid:    #E0E0E0;   /* bordi, divisori */
  --color-gray-text:   #666666;   /* testi secondari, placeholder */
  --color-success:     #4CAF50;   /* slot consigliati, conferme */
  --color-error:       #D32F2F;   /* errori */
  --color-warning:     #F57C00;   /* avvisi pacchetto in scadenza */
}
```

**Font:**
```html
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
```
- Titoli, navbar logo, H1-H4: `font-family: 'Poppins', sans-serif`
- Tutto il resto (body, bottoni, label, input): `font-family: 'Inter', sans-serif`

**Texture splash (ink-splash):**
```css
body::before {
  content: '';
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background-image: url('/static/img/splash-texture.png');
  background-size: cover;
  opacity: 0.07;
  pointer-events: none;
  z-index: 0;
}
```
Se non esiste `splash-texture.png`, usa questo SVG inline come fallback:
```css
body::before {
  background-image: url("data:image/svg+xml,..."); /* pattern dots sottile */
  opacity: 0.04;
}
```

**Bottoni:**
```css
.btn-primary {
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 10px;   /* NON pill-shaped — 10px fissi */
  padding: 14px 28px;
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-primary:hover { background: var(--color-primary-dark); }
.btn-secondary {
  background: transparent;
  color: var(--color-primary);
  border: 2px solid var(--color-primary);
  border-radius: 10px;
}
```

**Navbar:**
```css
nav {
  background: var(--color-black);
  border-bottom: none;
  padding: 0 24px;
}
.nav-logo img { height: 48px; }
.nav-links a { color: var(--color-white); }
.nav-links a:hover { color: var(--color-primary); }
```

**Card:**
```css
.card {
  background: var(--color-white);
  border: 1px solid var(--color-gray-mid);
  border-radius: 12px;
  padding: 1.5rem;
}
```

**Form inputs:**
```css
.form-input {
  border: 1.5px solid var(--color-gray-mid);
  border-radius: 10px;
  padding: 13px 16px;
  font-family: 'Inter', sans-serif;
}
.form-input:focus { border-color: var(--color-primary); }
```

**Badge stato pacchetto:**
```css
.badge-active   { background: #E8F5E9; color: #2E7D32; border: 1px solid #A5D6A7; }
.badge-warning  { background: #FFF3E0; color: #E65100; border: 1px solid #FFCC02; }
.badge-blocked  { background: #FFEBEE; color: #C62828; border: 1px solid #EF9A9A; }
```

Applica il redesign a TUTTI i template in `app/templates/` — auth, booking, profile, admin.

---

## CHECKLIST FINALE (verificare prima del merge su main)

### Database
- [ ] Modello Instructor creato con username e password_hash
- [ ] Discipline aggiornate con instructor_id e slot_duration_minutes
- [ ] Modello Package creato con UniqueConstraint
- [ ] Appointments aggiornati con instructor_id e package_id
- [ ] Migrazione Alembic eseguita senza errori
- [ ] Seed dati: 4 istruttori + 8 combinazioni discipline create

### Booking Engine
- [ ] Regola 12h preavviso minimo funzionante
- [ ] Regola 24h cancellazione funzionante
- [ ] Max 2 prenotazioni per settimana per combinazione rispettato
- [ ] Finestra 2 settimane sincronizzata (Sabato 00:00 apre nuova settimana)
- [ ] Griglie slot variabili: 30/40/60 min per disciplina
- [ ] Blocco automatico quando pacchetto.lessons_completed >= total_lessons
- [ ] Contatore scala SOLO su status completed (non alla prenotazione)
- [ ] Slot consigliati (verde) = 2 slot successivi a prenotazione esistente

### Admin
- [ ] Login admin usa credenziali Instructor (non più admin_user singolo)
- [ ] Sessioni concorrenti multiple permesse
- [ ] Cambio password funzionante per ogni istruttore
- [ ] Reset password via email funzionante
- [ ] Apertura/chiusura temporanea disciplina funzionante
- [ ] Periodo stagionale configurabile per disciplina
- [ ] Blocco ferie globale funzionante
- [ ] Vista pacchetti utente con contatore e barra progresso
- [ ] Rinnovo pacchetto da admin funzionante
- [ ] slot_duration_minutes visibile ma NON modificabile dall'admin

### Frontend
- [ ] Flusso: istruttore → disciplina → range picker → lista slot
- [ ] Range picker con date minima/massima rispettate
- [ ] Giorni non disponibili non selezionabili
- [ ] Slot consigliati evidenziati in verde con badge "Slot consigliato"
- [ ] Profilo utente mostra tutti i pacchetti con barra progresso
- [ ] Pacchetto esaurito: messaggio chiaro, bottone prenota disabilitato

### Design
- [ ] Palette sostituita completamente: arancio #FC5E02 + nero + bianco
- [ ] Font Poppins (titoli) + Inter (body) caricati e applicati
- [ ] Bottoni con border-radius 10px (non pill)
- [ ] Navbar nera con logo e link bianchi
- [ ] Texture splash a 6-8% opacity sul body
- [ ] Nessun residuo della palette terracotta/cream precedente

### Git
- [ ] Tutto il lavoro su branch redesign/v2
- [ ] Nessuna modifica su main
- [ ] Commit parziali dopo ogni fase completata
- [ ] `git diff --stat` verificato prima del merge finale
