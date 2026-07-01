"""
Script da eseguire UNA SOLA VOLTA per inizializzare il gruppo Agility
sul database esistente (locale e Render).

Esegue queste operazioni:
1. Rinomina "Agility" di Angelo → "Agility Campo 1"
2. Rinomina "Agility" di Conny → "Agility Campo 2"
3. Crea il gruppo DisciplineGroup(name="agility", display_name="Agility")
4. Associa entrambe le discipline al gruppo
5. Azzera tutti i pacchetti esistenti (siamo in sviluppo)

Esegui con:
    python setup_agility_group.py
"""
import sys
import os

# Aggiunge la root del progetto al path
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.discipline import Discipline
from app.models.discipline_group import DisciplineGroup
from app.models.instructor import Instructor
from app.models.package import Package


def main():
    db = SessionLocal()
    try:
        # 1. Rinomina discipline Agility
        angelo = db.query(Instructor).filter(Instructor.name == "Angelo").first()
        conny = db.query(Instructor).filter(Instructor.name == "Conny").first()

        if angelo:
            agility_angelo = db.query(Discipline).filter(
                Discipline.name == "Agility",
                Discipline.instructor_id == angelo.id,
            ).first()
            if agility_angelo:
                agility_angelo.name = "Agility Campo 1"
                print(f"Rinominata: Agility (Angelo) -> Agility Campo 1")
            else:
                agility_angelo = db.query(Discipline).filter(
                    Discipline.name == "Agility Campo 1",
                    Discipline.instructor_id == angelo.id,
                ).first()
                if agility_angelo:
                    print("Agility Campo 1 (Angelo) già presente, salto rinomina.")
                else:
                    print("ATTENZIONE: disciplina Agility di Angelo non trovata!")

        if conny:
            agility_conny = db.query(Discipline).filter(
                Discipline.name == "Agility",
                Discipline.instructor_id == conny.id,
            ).first()
            if agility_conny:
                agility_conny.name = "Agility Campo 2"
                print(f"Rinominata: Agility (Conny) -> Agility Campo 2")
            else:
                agility_conny = db.query(Discipline).filter(
                    Discipline.name == "Agility Campo 2",
                    Discipline.instructor_id == conny.id,
                ).first()
                if agility_conny:
                    print("Agility Campo 2 (Conny) già presente, salto rinomina.")
                else:
                    print("ATTENZIONE: disciplina Agility di Conny non trovata!")

        db.flush()

        # 2. Crea il gruppo se non esiste
        group = db.query(DisciplineGroup).filter(DisciplineGroup.name == "agility").first()
        if not group:
            group = DisciplineGroup(name="agility", display_name="Agility")
            db.add(group)
            db.flush()
            print(f"Gruppo Agility creato (id={group.id})")
        else:
            print(f"Gruppo Agility già esistente (id={group.id})")

        # 3. Associa le discipline al gruppo
        updated = db.query(Discipline).filter(
            Discipline.name.in_(["Agility Campo 1", "Agility Campo 2"])
        ).update({"group_id": group.id}, synchronize_session=False)
        print(f"Discipline associate al gruppo: {updated}")

        # 4. Azzera i pacchetti (solo in sviluppo)
        # Prima azzera i riferimenti nelle prenotazioni
        from app.models.appointment import Appointment
        db.query(Appointment).update({"package_id": None}, synchronize_session=False)
        deleted = db.query(Package).delete()
        print(f"Pacchetti eliminati: {deleted}")

        db.commit()
        print("\nDone. Esegui ora: alembic upgrade head")
    except Exception as e:
        db.rollback()
        print(f"ERRORE: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
