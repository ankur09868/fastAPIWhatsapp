from pydantic import BaseModel
from datetime import date as dt_date, time as dt_time
from typing import Optional, Dict, Any

class ScheduledEventBase(BaseModel):
    type: str
    date: Optional[dt_date] = None
    time: Optional[dt_time] = None
    value: Dict[str, Any]

class ScheduledEventCreate(ScheduledEventBase):
    pass

class ScheduledEventResponse(ScheduledEventBase):
    id: int

    class Config:
        orm_mode = True
