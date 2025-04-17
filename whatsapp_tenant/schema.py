from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class BroadcastGroupMember(BaseModel):
    name: Optional[str] = None
    phone: int  

class BroadcastGroupCreate(BaseModel):
    id: str
    name: str
    members: Optional[List[BroadcastGroupMember]] = []  

class BroadcastGroupResponse(BaseModel):
    id: str
    name: str
    members: Optional[List[dict]] = []

    class Config:
        orm_mode = True


class WhatsappTenantDataSchema(BaseModel):
    business_phone_number_id: Optional[int]
    flow_data: Optional[List[Dict[str, str]]]  # List of dictionaries where keys and values are strings
    adj_list: Optional[List[List[int]]]  # List of lists of integers
    access_token: str
    updated_at: Optional[datetime]
    business_account_id: int
    start: Optional[int]
    fallback_count: Optional[int]
    fallback_message: Optional[str]
    flow_name: Optional[str]
    tenant_id: str
    spreadsheet_link: Optional[str]
    id: int
    language: Optional[str]

    class Config:
        orm_mode = True
        from_attributes = True  # Allows from_orm to work correctly