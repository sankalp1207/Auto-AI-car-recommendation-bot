from sqlalchemy import Column, String, DateTime
from datetime import datetime
from app.database.database import Base

class ERPSession(Base):
    __tablename__ = "erp_sessions"

    student_id = Column(String, primary_key=True, index=True)
    encrypted_cookies = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
