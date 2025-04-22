from sqlalchemy import Column, Integer, String, ForeignKey, Float,Date
from sqlalchemy.orm import relationship
from config.database import Base

class BroadcastAnalytics(Base):
    __tablename__ = "broadcast_analytics"

    id = Column(Integer, primary_key=True, index=True)
    total_sent = Column(Integer, default=0) 
    total_delivered = Column(Integer, default=0)
    total_read = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    date = Column(Date)
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"))

    # Relationship with Tenant
    tenant = relationship("Tenant", back_populates="broadcast_analytics")