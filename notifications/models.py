from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, JSON, Date, Time
from sqlalchemy.orm import relationship
from config.database import Base
from datetime import datetime


class Notifications(Base):
    
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text)
    created_on = Column(DateTime, default=datetime.now())
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts_contact.id"), nullable=True) 
     
    tenant = relationship("Tenant", back_populates="notifications")
    contact = relationship("Contact", back_populates="notifications")
