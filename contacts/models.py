from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, JSON, Date, Time
from sqlalchemy.orm import relationship
from config.database import Base
from datetime import datetime


class Contact(Base):
    __tablename__ = "contacts_contact"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    createdOn = Column(DateTime, default=datetime.utcnow, nullable=True)
    isActive = Column(Boolean, default=False, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenant_tenant.id"), nullable=True)
    tenant = relationship("Tenant", back_populates="contacts")  # Corrected back_populates
    template_key = Column(String(50), nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=True)
    last_delivered = Column(DateTime, default=datetime.utcnow, nullable=True)
    last_replied = Column(DateTime, default=datetime.utcnow, nullable=True)
    customField = Column(JSON, nullable=True)

    notifications = relationship("Notifications", back_populates="contact")


    def __repr__(self):
        return f"<Contact(name={self.name})>"
    