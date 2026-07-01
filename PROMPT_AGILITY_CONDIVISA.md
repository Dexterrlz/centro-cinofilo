# PROMPT — Agility condivisa: pacchetto unico, assegnazione automatica istruttore

## PROCEDURA DI SICUREZZA OBBLIGATORIA

```bash
git status
git add .
git commit -m "chore: work in progress before agility-shared refactor"
git push origin HEAD
git checkout -b feature/agility-shared
git branch
```

Fermati e mostrami l'output di `git branch` prima di procedere.

---

## CONTESTO

Angelo insegna "Agility Campo 1" e Conny insegna "Agility Campo 2".
Sono due discipline separate nel DB ma rappresentano lo stesso servizio
agli occhi dell'utente.

**Obiettivo:** l'utente vede e prenota una sola "Agility", il sistema
assegna automaticamente il primo istruttore con slot libero.
Un solo pacchetto per utente (non due separati per campo).
Admin e agenda restano invariati — Angelo vede le sue, Conny le sue.

---

## PARTE 1 — MIGRAZIONE DATABASE

### Nuova tabella `discipline_groups`

```python
# app/models/discipline_group.py
class DisciplineGroup(Base):
    __tablename__ = "discipline_groups"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    # Nome mostrato all'utente (es. "Agility")
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    disciplines = relationship("Discipline", back_populates="group")
    packages = relationship("Package", back_populates="group")
```

### Modifica tabella `disciplines`

Aggiungi campo nullable:
```python
group_id = Column(Integer, ForeignKey("discipline_groups.id"),
                  nullable=True)
group = relationship("DisciplineGroup", back_populates="disciplines")
```

### Modifica tabella `packages`

```python
# Rendi instructor_id nullable (per pacchetti di gruppo)
instructor_id = Column(Integer, ForeignKey("instructors.id"),
                       nullable=True)

# Aggiungi group_id (nullable — solo per discipline condivise)
group_id = Column(Integer, ForeignKey("discipline_groups.id"),
                  nullable=True)
group = relationship("DisciplineGroup", back_populates="packages")

# Il vincolo UNIQUE esistente va aggiornato:
# Prima era: (user_id, discipline_id, instructor_id)
# Diventa due vincoli separati:
# - Per discipline normali: (user_id, discipline_id, instructor_id)
# - Per discipline di gruppo: (user_id, group_id)
# Implementa con un CheckConstraint o due UniqueConstraint condizionali
```

### Migrazione Alembic

```bash
alembic revision --autogenerate -m "discipline_groups_shared_agility"
alembic upgrade head
```

### Seed dati iniziali — aggiorna app/utils/seed.py

Aggiungi dopo la creazione delle discipline:

```python
# Crea il gruppo Agility e associa le discipline
agility_group = DisciplineGroup(
    name="agility",
    display_name="Agility"
)
db.add(agility_group)
db.flush()

# Associa Agility Campo 1 e Agility Campo 2 al gruppo
agility_disciplines = db.query(Discipline)\
    .filter(Discipline.name.in_(["Agility Campo 1", "Agility Campo 2"]))\
    .all()
for disc in agility_disciplines:
    disc.group_id = agility_group.id

# Azzera tutti i pacchetti esistenti (siamo in sviluppo)
db.query(Package).delete()
db.commit()
```

**IMPORTANTE:** esegui il seed anche sul DB esistente con uno script
one-shot separato `setup_agility_group.py`:

```python
"""
Script da eseguire UNA SOLA VOLTA per inizializzare il gruppo Agility
sul database esistente (locale e Render).
"""
from app.database import SessionLocal
from app.models.discipline import Discipline
from app.models.discipline_group import DisciplineGroup
from app.models.package import Package

db = SessionLocal()
try:
    # Crea gruppo se non esiste
    group = db.query(DisciplineGroup)\
               .filter_by(name="agility").first()
    if not group:
        group = DisciplineGroup(name="agility", display_name="Agility")
        db.add(group)
        db.flush()
        print(f"Gruppo Agility creato (id={group.id})")

    # Associa discipline
    updated = db.query(Discipline)\
        .filter(Discipline.name.in_(["Agility Campo 1", "Agility Campo 2"]))\
        .update({"group_id": group.id}, synchronize_session=False)
    print(f"Discipline aggiornate: {updated}")

    # Azzera pacchetti (solo in sviluppo!)
    deleted = db.query(Package).delete()
    print(f"Pacchetti eliminati: {deleted}")

    db.commit()
    print("Done.")
finally:
    db.close()
```

---

## PARTE 2 — REPOSITORY

### Nuovo: app/repositories/discipline_group_repository.py

```python
def get_by_name(db, name: str) -> DisciplineGroup | None:
    return db.query(DisciplineGroup).filter_by(name=name).first()

def get_all(db) -> list[DisciplineGroup]:
    return db.query(DisciplineGroup)\
             .options(joinedload(DisciplineGroup.disciplines)
                      .joinedload(Discipline.instructor))\
             .all()
```

### Aggiorna: app/repositories/package_repository.py

```python
def get_active_for_user_and_group(db, user_id, group_id):
    """Pacchetto attivo per utente + gruppo disciplina (es. Agility)"""
    return db.query(Package).filter(
        Package.user_id == user_id,
        Package.group_id == group_id,
        Package.is_active == True
    ).first()

def get_active_for_user_and_discipline(db, user_id, discipline_id,
                                        instructor_id):
    """Pacchetto attivo per utente + disciplina singola (non di gruppo)"""
    return db.query(Package).filter(
        Package.user_id == user_id,
        Package.discipline_id == discipline_id,
        Package.instructor_id == instructor_id,
        Package.is_active == True
    ).first()

def create_for_group(db, user_id, group_id, total_lessons=8):
    """Crea pacchetto per disciplina condivisa (senza instructor_id fisso)"""
    from datetime import datetime
    pkg = Package(
        user_id=user_id,
        group_id=group_id,
        discipline_id=None,
        instructor_id=None,
        total_lessons=total_lessons,
        lessons_completed=0,
        is_active=True,
        activated_at=datetime.utcnow()
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg
```

### Aggiorna: app/repositories/availability_rule_repository.py

```python
def get_by_group_and_date(db, group_id, date):
    """
    Ritorna tutte le availability_rules per tutte le discipline
    di un gruppo in una data specifica (per giorno della settimana).
    """
    weekday = date.weekday()
    group = db.query(DisciplineGroup).filter_by(id=group_id)\
              .options(joinedload(DisciplineGroup.disciplines))\
              .first()
    if not group:
        return []

    discipline_ids = [d.id for d in group.disciplines]
    return db.query(AvailabilityRule)\
        .filter(
            AvailabilityRule.discipline_id.in_(discipline_ids),
            AvailabilityRule.weekday == weekday
        )\
        .options(
            joinedload(AvailabilityRule.discipline)
            .joinedload(Discipline.instructor)
        )\
        .all()
```

---

## PARTE 3 — BOOKING SERVICE

### Aggiorna: app/services/booking_service.py

Aggiungi la funzione di assegnazione automatica istruttore
per discipline condivise:

```python
def find_available_instructor_for_group(
    db, group_id, date, start_time, end_time
):
    """
    Per una disciplina condivisa (es. Agility), trova il primo
    istruttore con lo slot libero nella data e orario richiesti.

    Logica:
    1. Recupera tutte le discipline del gruppo
    2. Per ognuna, verifica:
       a. La disciplina è attiva per quella data
       b. Lo slot rientra nelle availability_rules della disciplina
       c. Lo slot non è già prenotato (appointments)
       d. L'istruttore non ha sovrapposizioni su altre sue discipline
    3. Ritorna la prima disciplina disponibile trovata,
       o None se nessuna è libera
    """
    from app.repositories import discipline_group_repository as group_repo

    group = group_repo.get_by_id(db, group_id)
    if not group:
        return None

    for discipline in group.disciplines:
        if not discipline.is_active:
            continue
        if not discipline_is_active_on_date(discipline, date):
            continue

        # Verifica che lo slot esista nelle regole di disponibilità
        slot_in_rules = slot_exists_in_rules(
            db, discipline.id, date, start_time
        )
        if not slot_in_rules:
            continue

        # Verifica che lo slot non sia già prenotato
        existing = appointment_repo.get_by_slot(
            db=db,
            discipline_id=discipline.id,
            instructor_id=discipline.instructor_id,
            date=date,
            start_time=start_time
        )
        if existing:
            continue

        # Verifica che l'istruttore non sia occupato su altre discipline
        instructor_free = instructor_is_available(
            db=db,
            instructor_id=discipline.instructor_id,
            date=date,
            start_time=start_time,
            end_time=end_time
        )
        if not instructor_free:
            continue

        # Trovato! Ritorna questa disciplina (con istruttore assegnato)
        return discipline

    return None  # nessun istruttore disponibile


def create_booking_for_group(
    db, user_id, group_id, date, start_time, end_time
):
    """
    Crea una prenotazione per una disciplina condivisa.
    Assegna automaticamente l'istruttore disponibile.
    Gestisce il pacchetto di gruppo.
    """
    # Trova istruttore disponibile
    discipline = find_available_instructor_for_group(
        db, group_id, date, start_time, end_time
    )
    if not discipline:
        raise ValueError(
            "Questo orario non è più disponibile"
        )

    # Recupera o crea pacchetto di gruppo
    package = package_repo.get_active_for_user_and_group(
        db, user_id, group_id
    )
    if not package:
        package = package_repo.create_for_group(
            db, user_id, group_id, total_lessons=8
        )
    elif package.lessons_completed >= package.total_lessons:
        raise ValueError(
            "Hai esaurito le lezioni del tuo pacchetto Agility. "
            "Contatta il centro per rinnovarlo."
        )

    # Controlla max 2 prenotazioni per settimana sul gruppo
    # (somma di Campo 1 + Campo 2 nella stessa settimana)
    weekly_count = appointment_repo.count_weekly_for_user_group(
        db, user_id, group_id, date
    )
    if weekly_count >= 2:
        raise ValueError(
            "Hai già raggiunto il limite di 2 prenotazioni "
            "Agility per questa settimana."
        )

    # Crea l'appuntamento
    appointment = Appointment(
        user_id=user_id,
        discipline_id=discipline.id,
        instructor_id=discipline.instructor_id,
        package_id=package.id,
        appointment_date=date,
        start_time=start_time,
        end_time=end_time,
        status="confirmed"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment
```

Aggiungi in `appointment_repository.py`:

```python
def count_weekly_for_user_group(db, user_id, group_id, date):
    """
    Conta le prenotazioni attive dell'utente per un gruppo disciplina
    nella settimana del calendario contenente 'date'.
    """
    from datetime import timedelta
    week_start = date - timedelta(days=date.weekday())
    week_end = week_start + timedelta(days=6)

    # Recupera tutti i discipline_id del gruppo
    group = db.query(DisciplineGroup).filter_by(id=group_id).first()
    disc_ids = [d.id for d in group.disciplines] if group else []

    return db.query(Appointment).filter(
        Appointment.user_id == user_id,
        Appointment.discipline_id.in_(disc_ids),
        Appointment.appointment_date >= week_start,
        Appointment.appointment_date <= week_end,
        Appointment.status.in_(["pending", "confirmed"])
    ).count()
```

---

## PARTE 4 — AVAILABILITY SERVICE

### Aggiorna: app/services/availability_service.py

Aggiungi funzione per generare slot unificati di un gruppo:

```python
def get_available_slots_for_group(db, group_id, date_from, date_to,
                                   user_id=None):
    """
    Genera tutti gli slot disponibili per un gruppo di discipline
    in un range di date.

    Per ogni slot temporale disponibile in QUALSIASI disciplina
    del gruppo, lo include UNA SOLA VOLTA se almeno un istruttore
    ha quel slot libero.

    Ritorna lista di dict:
    {
        'date': date,
        'start': time,
        'end': time,
        'available_count': int,  # quanti istruttori hanno quel slot libero
        'total_capacity': int,   # quanti istruttori hanno quel slot aperto
        'is_suggested': bool,    # slot adiacente a prenotazione esistente
    }
    """
    from collections import defaultdict

    group = db.query(DisciplineGroup)\
              .filter_by(id=group_id)\
              .options(joinedload(DisciplineGroup.disciplines)
                       .joinedload(Discipline.instructor))\
              .first()
    if not group:
        return []

    results = []
    current = date_from
    while current <= date_to:
        # Per ogni giorno, raccoglie tutti gli slot possibili
        # da tutte le discipline del gruppo
        slot_map = defaultdict(lambda: {
            'available': 0, 'total': 0, 'suggested': False
        })

        for discipline in group.disciplines:
            if not discipline.is_active:
                continue
            if not discipline_is_active_on_date(discipline, current):
                continue

            weekday = current.weekday()
            rules = availability_rule_repo\
                .get_by_discipline_and_weekday(
                    db, discipline.id, weekday
                )

            for rule in rules:
                slots = generate_slots_for_rule(rule, discipline, current)
                for slot in slots:
                    key = (slot['start'], slot['end'])
                    slot_map[key]['total'] += 1

                    # Verifica se questo slot è libero
                    existing = appointment_repo.get_by_slot(
                        db=db,
                        discipline_id=discipline.id,
                        instructor_id=discipline.instructor_id,
                        date=current,
                        start_time=slot['start']
                    )
                    instr_free = instructor_is_available(
                        db=db,
                        instructor_id=discipline.instructor_id,
                        date=current,
                        start_time=slot['start'],
                        end_time=slot['end']
                    )
                    if not existing and instr_free:
                        slot_map[key]['available'] += 1

        # Calcola slot suggeriti (adiacenti a prenotazioni esistenti)
        existing_bookings = appointment_repo\
            .get_by_instructor_and_date_for_group(
                db, group_id, current
            )
        suggested_starts = set()
        for appt in existing_bookings:
            suggested_starts.add(appt.end_time)

        # Costruisce risultati per questo giorno
        # Rispetta regola 12h di preavviso
        from datetime import datetime
        now = datetime.now()
        for (start, end), info in sorted(slot_map.items()):
            if info['available'] == 0:
                continue
            # Check preavviso 12h
            slot_dt = datetime.combine(current, start)
            if (slot_dt - now).total_seconds() < 43200:
                continue

            results.append({
                'date': current,
                'start': start,
                'end': end,
                'available_count': info['available'],
                'total_capacity': info['total'],
                'is_suggested': start in suggested_starts,
            })

        current += timedelta(days=1)

    return results
```

Aggiungi in `appointment_repository.py`:

```python
def get_by_instructor_and_date_for_group(db, group_id, date):
    """Prenotazioni esistenti nel giorno per tutte le discipline del gruppo"""
    group = db.query(DisciplineGroup).filter_by(id=group_id).first()
    disc_ids = [d.id for d in group.disciplines] if group else []
    return db.query(Appointment).filter(
        Appointment.discipline_id.in_(disc_ids),
        Appointment.appointment_date == date,
        Appointment.status.in_(["pending", "confirmed"])
    ).all()
```

---

## PARTE 5 — ROUTER PUBBLICO

### Aggiorna app/routers/public.py

```python
@router.get("/")
async def homepage(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Gruppo Agility (mostrato come tile unica)
    agility_group = discipline_group_repo.get_by_name(db, "agility")

    # Discipline dirette senza gruppo (Swim Dog Sport)
    direct_disciplines = discipline_repo.get_direct_without_group(db)
    # Esclude Angelo e Conny come istruttori visibili

    # Istruttori visibili (Santa, Simona)
    hidden = ["Angelo", "Conny"]
    visible_instructors = instructor_repo.get_all_active_excluding(
        db, hidden
    )

    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": user,
        "agility_group": agility_group,
        "direct_disciplines": direct_disciplines,
        "visible_instructors": visible_instructors,
    })


@router.get("/agility")
async def agility_slot_selection(
    request: Request,
    date_from: str = None,
    date_to: str = None,
    db: Session = Depends(get_db)
):
    """Pagina selezione slot per il gruppo Agility"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    agility_group = discipline_group_repo.get_by_name(db, "agility")
    if not agility_group:
        raise HTTPException(404)

    # Finestra prenotazione (stessa logica esistente)
    window_start, window_end = get_booking_window()

    # Pacchetto utente per Agility
    package = package_repo.get_active_for_user_and_group(
        db, user.id, agility_group.id
    )

    # Slot disponibili unificati
    if date_from and date_to:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d").date()
            dt = datetime.strptime(date_to, "%Y-%m-%d").date()
            df = max(df, window_start)
            dt = min(dt, window_end)
        except ValueError:
            df, dt = window_start, window_end
    else:
        df, dt = window_start, window_end

    slots = availability_service.get_available_slots_for_group(
        db=db,
        group_id=agility_group.id,
        date_from=df,
        date_to=dt,
        user_id=user.id
    )

    return templates.TemplateResponse("booking/agility_slots.html", {
        "request": request,
        "current_user": user,
        "group": agility_group,
        "slots": slots,
        "package": package,
        "window_start": window_start,
        "window_end": window_end,
        "date_from": df,
        "date_to": dt,
        "prev_dates": ...,
        "next_dates": ...,
    })


@router.post("/agility/prenota")
async def agility_book(request: Request, db: Session = Depends(get_db)):
    """Crea prenotazione Agility con assegnazione automatica istruttore"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    date_str = form.get("date")
    start_time_str = form.get("start_time")
    end_time_str = form.get("end_time")
    group_id = int(form.get("group_id"))

    try:
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start = datetime.strptime(start_time_str, "%H:%M").time()
        end = datetime.strptime(end_time_str, "%H:%M").time()

        appointment = booking_service.create_booking_for_group(
            db=db,
            user_id=user.id,
            group_id=group_id,
            date=appt_date,
            start_time=start,
            end_time=end
        )
        return RedirectResponse(
            f"/prenotazione/confermata/{appointment.id}",
            status_code=302
        )
    except ValueError as e:
        return templates.TemplateResponse("booking/agility_slots.html", {
            "request": request,
            "current_user": user,
            "error": str(e),
            ...
        })
```

Aggiungi in `discipline_repository.py`:

```python
def get_direct_without_group(db):
    """
    Discipline attive senza gruppo (es. Swim Dog Sport)
    escludendo quelle di Angelo e Conny (già nel gruppo)
    """
    hidden_instructors = ["Angelo", "Conny"]
    return db.query(Discipline)\
        .join(Instructor)\
        .filter(
            Discipline.is_active == True,
            Discipline.group_id == None,
            ~Instructor.name.in_(hidden_instructors)
        )\
        .options(joinedload(Discipline.instructor))\
        .all()
```

---

## PARTE 6 — TEMPLATE HOMEPAGE (index.html)

```html
<div class="instructor-grid">

  <!-- Tile Agility (gruppo condiviso) -->
  {% if agility_group %}
  <div class="instructor-card">
    <div class="instructor-card-icon">🏃</div>
    <h3>{{ agility_group.display_name }}</h3>
    {% set user_pkg = user_agility_package %}
    {% if user_pkg %}
    <div class="pkg-badge {% if user_pkg.lessons_completed >= user_pkg.total_lessons %}pkg-danger
                           {% elif (user_pkg.total_lessons - user_pkg.lessons_completed) <= 2 %}pkg-warn
                           {% else %}pkg-ok{% endif %}">
      {{ user_pkg.lessons_completed }}/{{ user_pkg.total_lessons }} lezioni
    </div>
    {% endif %}
    {% if user_pkg and user_pkg.lessons_completed >= user_pkg.total_lessons %}
    <p class="text-danger" style="font-size:13px">
      Pacchetto esaurito — contatta il centro per rinnovarlo
    </p>
    {% else %}
    <a href="/agility" class="btn btn-primary">Scegli</a>
    {% endif %}
  </div>
  {% endif %}

  <!-- Discipline dirette (Swim Dog Sport) -->
  {% for disc in direct_disciplines %}
  <div class="instructor-card">
    <div class="instructor-card-icon">
      {% if 'Swim' in disc.name %}🏊{% else %}🏃{% endif %}
    </div>
    <h3>{{ disc.name }}</h3>
    <p style="font-size:13px;color:var(--color-text-muted)">
      Slot da {{ disc.slot_duration_minutes }} minuti
    </p>
    <a href="/prenota/{{ disc.id }}" class="btn btn-primary">Scegli</a>
  </div>
  {% endfor %}

  <!-- Istruttori visibili (Santa, Simona) -->
  {% for instr in visible_instructors %}
  <div class="instructor-card">
    <div class="instructor-card-avatar">👤</div>
    <h3>{{ instr.name }}</h3>
    <ul class="instructor-card-disciplines">
      {% for disc in instr.disciplines if disc.is_active %}
      <li>{{ disc.name }}</li>
      {% endfor %}
    </ul>
    <a href="/istruttore/{{ instr.id }}" class="btn btn-primary">Scegli</a>
  </div>
  {% endfor %}

</div>
```

---

## PARTE 7 — TEMPLATE SLOT AGILITY

Crea `app/templates/booking/agility_slots.html`:
Usa lo stesso layout di `booking/select_slot.html` esistente
(range picker Da/Al + lista slot per giorno) con queste differenze:

- Titolo: "Agility" senza riferimento a istruttori
- Ogni slot mostra solo orario — NON mostra "con Angelo" o "con Conny"
- Se `slot.available_count >= 2`: normale
- Se `slot.available_count == 1`: mostra badge piccolo "Ultimo posto"
- Se `slot.is_suggested`: bordo verde + badge "✦ Consigliato"
- Form hidden fields: `group_id`, `date`, `start_time`, `end_time`
- Action: POST `/agility/prenota`

---

## PARTE 8 — PAGINA CONFERMA E PROFILO UTENTE

### booking/confirm.html e booking/confirmed.html

Per prenotazioni Agility (riconoscibili perché `appointment.discipline.group_id is not None`):
- Mostra: "Agility" come disciplina
- NON mostrare il nome dell'istruttore assegnato
- Mostra: data, orario, durata

Per tutte le altre discipline: comportamento invariato.

### profile/bookings.html

Per prenotazioni Agility:
- Mostra "Agility" — non "Agility Campo 1 con Angelo"
- Badge pacchetto: legge da `package.group_id` → mostra
  `lessons_completed/total_lessons` del pacchetto di gruppo

### complete_lesson() — aggiorna in booking_service.py

```python
def complete_lesson(db, appointment_id):
    appointment = appointment_repo.get_by_id(db, appointment_id)
    appointment.status = "completed"

    # Determina quale pacchetto scalare
    package = None
    if appointment.package_id:
        package = package_repo.get_by_id(db, appointment.package_id)

    if package:
        # Ricalcola usando COUNT (idempotente)
        completed_count = db.query(Appointment).filter(
            Appointment.package_id == package.id,
            Appointment.status == "completed",
        ).count()
        package.lessons_completed = completed_count

        if package.lessons_completed >= package.total_lessons:
            package.is_active = False

    db.commit()
    return appointment
```

---

## PARTE 9 — AGENDA ADMIN (invariata)

L'agenda admin NON cambia — Angelo vede i suoi slot
(Agility Campo 1 + Swim Dog Sport), Conny vede i suoi
(Agility Campo 2). Il gruppo non è visibile nell'admin.

**Verifica che `build_daily_timeline()` in availability_service.py
usi ancora `discipline.instructor_id` direttamente — non passi
mai per `group_id`.**

---

## PARTE 10 — CHECKLIST FINALE

### Database
- [ ] Tabella `discipline_groups` creata
- [ ] `disciplines.group_id` aggiunto (nullable)
- [ ] `packages.group_id` aggiunto (nullable)
- [ ] `packages.instructor_id` reso nullable
- [ ] Migrazione Alembic eseguita senza errori
- [ ] Script `setup_agility_group.py` eseguito — gruppo creato,
      discipline associate, pacchetti azzerati
- [ ] Verificare con SELECT: Agility Campo 1 e 2 hanno group_id

### Backend
- [ ] `find_available_instructor_for_group()` funzionante
- [ ] `create_booking_for_group()` funzionante
- [ ] `get_available_slots_for_group()` funzionante
- [ ] `count_weekly_for_user_group()` funzionante
- [ ] `complete_lesson()` aggiornata (scala pacchetto di gruppo)
- [ ] `get_direct_without_group()` funzionante

### Frontend utente
- [ ] Homepage: 5 card (Agility, Swim Dog, Santa, Simona + eventuali)
- [ ] Tile Agility mostra badge pacchetto se utente ha pacchetto attivo
- [ ] /agility mostra slot unificati senza nomi istruttori
- [ ] Badge "Ultimo posto" quando available_count == 1
- [ ] Badge "✦ Consigliato" per slot suggeriti
- [ ] POST /agility/prenota assegna automaticamente istruttore
- [ ] Conferma prenotazione: "Agility" senza istruttore
- [ ] Profilo utente: "Agility" senza istruttore, pacchetto di gruppo

### Admin (invariato)
- [ ] Agenda Angelo: vede Agility Campo 1 + Swim Dog Sport
- [ ] Agenda Conny: vede Agility Campo 2
- [ ] Switcher istruttori: tutti e 4 visibili con nomi reali
- [ ] Tab Prenotazioni: istruttore assegnato visibile in admin
- [ ] Tab Pacchetti: pacchetti di gruppo mostrati correttamente
- [ ] complete_lesson() da admin scala correttamente il pacchetto

### Test end-to-end
- [ ] Utente A prenota Agility martedì 15:00 → assegnato a Conny
      (unica con slot aperto a quell'ora)
- [ ] Utente B prenota Agility martedì 16:00 → assegnato primo libero
- [ ] Utente C prenota Agility martedì 16:00 → assegnato al secondo
- [ ] Utente D prova Agility martedì 16:00 → "non disponibile"
      (entrambi i campi occupati)
- [ ] Utente A fa 8 lezioni → pacchetto bloccato, non può prenotare
- [ ] Admin segna lezione completata → pacchetto di gruppo scala
- [ ] Build_daily_timeline() agenda admin NON è influenzata dal gruppo
