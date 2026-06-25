from sqlalchemy import Column, Integer, Date, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class BlockedDate(Base):
    __tablename__ = "blocked_dates"

    id = Column(Integer, primary_key=True, index=True)
    # NULL = tutte le discipline
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=True)
    blocked_date = Column(Date, nullable=False, index=True)
    reason = Column(String(200), nullable=True)
    # Se True ignora discipline_id e blocca tutto
    all_disciplines = Column(Boolean, default=False, nullable=False)
    # True = blocco ferie di tutto il centro (tutte le discipline)
    is_global = Column(Boolean, default=False, nullable=False)

    discipline = relationship("Discipline")
