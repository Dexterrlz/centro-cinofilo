from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Discipline(Base):
    __tablename__ = "disciplines"
    __table_args__ = (
        UniqueConstraint("name", "instructor_id", name="uq_discipline_instructor"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#3B82F6")
    is_active = Column(Boolean, default=True, nullable=False)
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=True)
    slot_duration_minutes = Column(Integer, nullable=True)
    active_from = Column(Date, nullable=True)
    active_until = Column(Date, nullable=True)

    instructor = relationship("Instructor", back_populates="disciplines")
    appointments = relationship("Appointment", back_populates="discipline")
    availability_rules = relationship("AvailabilityRule", back_populates="discipline")
    packages = relationship("Package", back_populates="discipline")

    @property
    def display_name(self) -> str:
        """Nome disciplina con istruttore, per disambiguare combinazioni omonime (es. due 'Agility')."""
        if self.instructor:
            return f"{self.name} con {self.instructor.name}"
        return self.name
