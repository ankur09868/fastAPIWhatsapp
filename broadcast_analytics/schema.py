# schemas.py
from typing import List, Optional
from pydantic import BaseModel,validator
from datetime import date,datetime

class TemplateAnalyticsRequest(BaseModel):
    template_ids:List[str]
    date:str
    days: Optional[int] = 7


class AnalyticsResponse(BaseModel):
    total_sent: int
    total_delivered: int
    total_read: int
    total_cost: float
    tenant_id: str
    date: Optional[date] 

    class Config:
        orm_mode = True