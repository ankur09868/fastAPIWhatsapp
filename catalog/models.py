# models/catalog.py
from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, JSON
from sqlalchemy.orm import relationship
from config.database import Base

class Catalog(Base):
    __tablename__ = "catalogs"
    
    id = Column(Integer, primary_key=True, index=True)
    catalog_id = Column(BigInteger, unique=True, index=True)
    spreadsheet_link = Column(String, nullable=False)
    razorpay_key = Column(JSON, nullable=True)
    
    business_owner_phone_number = Column(String(20), nullable=True)
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=True)
    tenant = relationship("Tenant", back_populates="catalogs")