from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, JSON, Date, Time
from sqlalchemy.orm import relationship
from config.database import Base
from datetime import datetime

class NodeTemplate(Base):
    __tablename__ = "node_temps_nodetemplate"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    date_created = Column(DateTime, default=datetime.utcnow)
    category = Column(String(100), nullable=False)
    createdBy_id = Column(Integer, nullable=True)
    node_data = Column(JSON, nullable=False)
    fallback_msg = Column(Text, nullable=True)
    fallback_count = Column(Integer, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenant_tenant.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="node_templates")
    trigger = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<NodeTemplate(name={self.name})>"