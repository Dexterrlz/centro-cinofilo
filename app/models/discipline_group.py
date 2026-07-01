from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class DisciplineGroup(Base):
    __tablename__ = "discipline_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    disciplines = relationship("Discipline", back_populates="group")
    packages = relationship("Package", back_populates="group")
