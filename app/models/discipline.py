from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Discipline(Base):
    __tablename__ = "disciplines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#3B82F6")
    is_active = Column(Boolean, default=True, nullable=False)

    appointments = relationship("Appointment", back_populates="discipline")
    availability_rules = relationship("AvailabilityRule", back_populates="discipline")
