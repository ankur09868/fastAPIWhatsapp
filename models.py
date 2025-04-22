from sqlalchemy import Column, Integer, String, ForeignKey, LargeBinary, BigInteger, JSON
from sqlalchemy.orm import relationship
from config.database import Base

class Tenant(Base):
    __tablename__ = "tenant_tenant"

    id = Column(String(50), primary_key=True)
    organization = Column(String(100), nullable=False)
    db_user = Column(String(100), nullable=False)
    db_user_password = Column(String(100), nullable=False)
    spreadsheet_link = Column(String, nullable=True)
    catalog_id = Column(BigInteger, nullable=True)
    key = Column(LargeBinary, nullable=True)
    tier = Column(String(20))
    agents = Column(JSON, nullable=True)

    contacts = relationship("Contact", back_populates="tenant")
    whatsapp_chat_whatsapp_data = relationship("WhatsappTenantData", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    node_templates = relationship("NodeTemplate", back_populates="tenant")
    dynamic_models = relationship("DynamicModel", back_populates="tenant")
    message_status = relationship("MessageStatus", back_populates="tenant")
    broadcast_groups = relationship("BroadcastGroups", back_populates="tenant")
    scheduled_events = relationship("ScheduledEvent", back_populates="tenant")
    conversations = relationship("Conversation", back_populates="tenant")
    notifications = relationship("Notifications", back_populates="tenant")
    message_statistics = relationship("MessageStatistics", back_populates="tenant")
    # retailer = relationship("Retailer", back_populates="tenant")

    def __repr__(self):
        return f"<Tenant(id={self.id}, organization={self.organization})>"
    
from catalog.models import Catalog
from broadcast_analytics.models import BroadcastAnalytics

# Now add the relationship
Tenant.catalogs = relationship("Catalog", back_populates="tenant")
Tenant.broadcast_analytics = relationship("BroadcastAnalytics", back_populates="tenant")