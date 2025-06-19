from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, JSON, Date, Time
from sqlalchemy.orm import relationship
from config.database import Base
from datetime import datetime

class WhatsappChatIndividualMessageStatistics(Base):
    __tablename__ = "whatsapp_chat_individualmessagestatistics"
    
    id = Column(Integer, primary_key=True)
    message_id = Column(String(255))
    status = Column(String(50))
    type = Column(String(50))
    type_identifier = Column(String(255))
    template_name = Column(String(255))
    userPhone = Column(String(50))
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=True)
    bpid = Column(String(255))
    timestamp = Column(DateTime)
    
    tenant = relationship("Tenant")  # No back

class WhatsappTenantData(Base):
    __tablename__ = "whatsapp_chat_whatsapptenantdata"

    business_phone_number_id = Column(BigInteger)
    flow_data = Column(JSON, nullable=True)
    adj_list = Column(JSON, nullable=True)
    access_token = Column(String(300), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    business_account_id = Column(BigInteger, nullable=False)
    start = Column(Integer, nullable=True)
    fallback_count = Column(Integer, nullable=True)
    fallback_message = Column(String(1000), nullable=True)
    flow_name = Column(String(200), nullable=True)
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=False)
    spreadsheet_link = Column(String, nullable=True)  # Use String for URL
    id = Column(Integer, primary_key=True)
    language = Column(String(50))
    introductory_msg = Column(JSON, nullable=True)
    multilingual =  Column(Boolean, default=False)
    prompt = Column(String(250),nullable=True)
    hop_nodes = Column(JSON, nullable=True)

    tenant = relationship("Tenant", back_populates="whatsapp_chat_whatsapp_data")

    def __repr__(self):
        return f"<WhatsappTenantData(business_phone_number_id={self.business_phone_number_id})>"

class MessageStatus(Base):
    __tablename__ = "whatsapp_message_id"

    business_phone_number_id = Column(BigInteger, nullable=False, index=True)  # Index added
    sent = Column(Boolean, default=False, nullable=False)                       # Default value set
    delivered = Column(Boolean, default=False, nullable=False)                  # Default value set
    read = Column(Boolean, default=False, nullable=False)                       # Default value set
    user_phone_number = Column(BigInteger, nullable=False, index=True)          # Index added
    message_id = Column(String(300), primary_key=True)                          # Primary key retained
    broadcast_group = Column(String(50), nullable=True)
    broadcast_group_name = Column(String(100), nullable=True)
    template_name = Column(String(50), nullable=True)
    replied = Column(Boolean, default=False, nullable=False)                    # Default value set
    failed = Column(Boolean, default=False, nullable=False)                     # Default value set
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=True)  # Adjusted ForeignKey reference

    tenant = relationship("Tenant", back_populates="message_status")

    def __repr__(self):
        return f"<MessageStatus(message_id={self.message_id}, user_phone_number={self.user_phone_number})>"

class BroadcastGroups(Base):
    __tablename__ = "broadcast_groups"

    name = Column(String(100), nullable=False)
    id = Column(String(50), primary_key=True)
    members = Column(JSON)
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=True)
    

    tenant = relationship("Tenant", back_populates="broadcast_groups")

class MessageStatistics(Base):
    __tablename__ = "message_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    record_key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    sent = Column(Integer, default=0)
    delivered = Column(Integer, default=0)
    read = Column(Integer, default=0)
    replied = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    template_name = Column(String, nullable=True)    
    tenant_id = Column(String(50), ForeignKey("tenant_tenant.id"), nullable=True)
    

    tenant = relationship("Tenant", back_populates="message_statistics")