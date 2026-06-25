from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Package(Base):
    __tablename__ = "packages"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "discipline_id", "instructor_id",
            name="uq_active_package"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False)
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=False)
    total_lessons = Column(Integer, nullable=False, default=8)
    lessons_completed = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    discipline = relationship("Discipline", back_populates="packages")
    instructor = relationship("Instructor", back_populates="packages")
