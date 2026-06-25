import logging
import secrets
import string
from datetime import date

import bcrypt

from app.database import SessionLocal
from app.models.discipline import Discipline
from app.models.instructor import Instructor

logger = logging.getLogger(__name__)

INSTRUCTORS_DATA = [
    {"name": "Angelo", "username": "angelo"},
    {"name": "Connie", "username": "connie"},
    {"name": "Santa", "username": "santa"},
    {"name": "Simona", "username": "simona"},
]

DISCIPLINES_DATA = [
    {"name": "Agility", "instructor": "Angelo", "slot_duration": 30},
    {"name": "Swim Dog Sport", "instructor": "Angelo", "slot_duration": 40,
     "active_from": (6, 1), "active_until": (9, 30)},
    {"name": "Agility", "instructor": "Connie", "slot_duration": 30},
    {"name": "Educazione di Base", "instructor": "Santa", "slot_duration": 60},
    {"name": "Hoopers", "instructor": "Santa", "slot_duration": 30},
    {"name": "Rally Obedience", "instructor": "Santa", "slot_duration": 30},
    {"name": "Educazione di Base", "instructor": "Simona", "slot_duration": 60},
    {"name": "Nosework", "instructor": "Simona", "slot_duration": 30},
]


def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_initial_data() -> None:
    """Crea istruttori e discipline iniziali se non esistono già.

    Le password in chiaro vengono generate al volo e stampate a video
    una sola volta: non vengono salvate nel codice né nei log persistenti.
    """
    db = SessionLocal()
    try:
        if db.query(Instructor).count() > 0:
            logger.info("Istruttori già presenti, seed saltato.")
            return

        instructors_by_name = {}
        print("\n" + "=" * 60)
        print("PASSWORD INIZIALI ISTRUTTORI — salvale ora, non saranno più mostrate")
        print("=" * 60)
        for data in INSTRUCTORS_DATA:
            plain_password = _generate_password()
            instructor = Instructor(
                name=data["name"],
                username=data["username"],
                password_hash=_hash_password(plain_password),
                is_active=True,
            )
            db.add(instructor)
            db.flush()
            instructors_by_name[data["name"]] = instructor
            print(f"  {data['name']:<10} username: {data['username']:<10} password: {plain_password}")
        print("=" * 60 + "\n")

        current_year = date.today().year
        for data in DISCIPLINES_DATA:
            instructor = instructors_by_name[data["instructor"]]
            active_from = active_until = None
            if "active_from" in data:
                month, day = data["active_from"]
                active_from = date(current_year, month, day)
            if "active_until" in data:
                month, day = data["active_until"]
                active_until = date(current_year, month, day)

            db.add(Discipline(
                name=data["name"],
                instructor_id=instructor.id,
                slot_duration_minutes=data["slot_duration"],
                is_active=True,
                active_from=active_from,
                active_until=active_until,
            ))

        db.commit()
        logger.info(
            "Seed completato: %d istruttori, %d discipline.",
            len(INSTRUCTORS_DATA), len(DISCIPLINES_DATA),
        )
    finally:
        db.close()
