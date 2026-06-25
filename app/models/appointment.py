import enum
from sqlalchemy import Column, Integer, String, Date, Time, Enum, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint(
            "discipline_id", "appointment_date", "start_time",
            name="uq_discipline_date_time"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(
        Enum(AppointmentStatus),
        default=AppointmentStatus.pending,
        nullable=False,
        index=True,
    )
    cancellation_token = Column(String(64), unique=True, nullable=True, index=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    discipline = relationship("Discipline", back_populates="appointments")
    user = relationship("User", back_populates="appointments")
    instructor = relationship("Instructor", back_populates="appointments")
    package = relationship("Package")
