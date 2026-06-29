from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.package import Package


class PackageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, package_id: int) -> Optional[Package]:
        return self.db.query(Package).filter(Package.id == package_id).first()

    def get_by_combo(self, user_id: int, discipline_id: int, instructor_id: int) -> Optional[Package]:
        return (
            self.db.query(Package)
            .filter(
                Package.user_id == user_id,
                Package.discipline_id == discipline_id,
                Package.instructor_id == instructor_id,
            )
            .first()
        )

    def create(self, user_id: int, discipline_id: int, instructor_id: int) -> Package:
        package = Package(
            user_id=user_id,
            discipline_id=discipline_id,
            instructor_id=instructor_id,
            total_lessons=8,
            lessons_completed=0,
            is_active=True,
            activated_at=datetime.utcnow(),
        )
        self.db.add(package)
        self.db.flush()
        return package

    def get_all_for_user(self, user_id: int) -> List[Package]:
        """Tutti i pacchetti di un utente, con disciplina e istruttore precaricati, per il profilo."""
        return (
            self.db.query(Package)
            .options(joinedload(Package.discipline), joinedload(Package.instructor))
            .filter(Package.user_id == user_id)
            .all()
        )

    def get_all_with_relations(self) -> List[Package]:
        """Tutti i pacchetti con utente, disciplina e istruttore precaricati, per la vista admin."""
        return (
            self.db.query(Package)
            .options(
                joinedload(Package.user),
                joinedload(Package.discipline),
                joinedload(Package.instructor),
            )
            .all()
        )

    def renew(self, package_id: int) -> Optional[Package]:
        """Rinnova il pacchetto: azzera il contatore e lo riattiva (stesso record, vincolo UNIQUE su combo)."""
        package = self.get_by_id(package_id)
        if package:
            package.lessons_completed = 0
            package.is_active = True
            package.activated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(package)
        return package

    def get_expiring_by_instructor(self, instructor_id: int, threshold: int = 2) -> List[Package]:
        """Pacchetti quasi esauriti per un istruttore (lezioni rimanenti <= threshold)."""
        return (
            self.db.query(Package)
            .options(joinedload(Package.user), joinedload(Package.discipline))
            .filter(
                Package.instructor_id == instructor_id,
                Package.is_active == True,
                (Package.total_lessons - Package.lessons_completed) <= threshold,
            )
            .all()
        )

    def set_active(self, package_id: int, is_active: bool) -> Optional[Package]:
        package = self.get_by_id(package_id)
        if package:
            package.is_active = is_active
            self.db.commit()
            self.db.refresh(package)
        return package

    def create_manual(
        self,
        user_id: int,
        discipline_id: int,
        instructor_id: int,
        lessons_completed: int = 0,
        total_lessons: int = 8,
    ) -> Package:
        existing = self.db.query(Package).filter(
            Package.user_id == user_id,
            Package.discipline_id == discipline_id,
            Package.instructor_id == instructor_id,
            Package.is_active == True,
        ).first()
        if existing:
            raise ValueError("Esiste già un pacchetto attivo per questa combinazione")
        pkg = Package(
            user_id=user_id,
            discipline_id=discipline_id,
            instructor_id=instructor_id,
            total_lessons=total_lessons,
            lessons_completed=lessons_completed,
            is_active=lessons_completed < total_lessons,
            activated_at=datetime.utcnow(),
        )
        self.db.add(pkg)
        self.db.commit()
        self.db.refresh(pkg)
        return pkg

    def update_lessons_completed(self, package_id: int, lessons_completed: int) -> Package:
        pkg = self.get_by_id(package_id)
        if not pkg:
            raise ValueError("Pacchetto non trovato")
        if lessons_completed < 0:
            raise ValueError("Il numero di lezioni non può essere negativo")
        if lessons_completed > pkg.total_lessons:
            raise ValueError(f"Non puoi inserire più di {pkg.total_lessons} lezioni")
        pkg.lessons_completed = lessons_completed
        pkg.is_active = lessons_completed < pkg.total_lessons
        self.db.commit()
        self.db.refresh(pkg)
        return pkg
