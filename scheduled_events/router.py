from fastapi import APIRouter, Depends ,HTTPException, Header
from sqlalchemy import orm
from config.database import get_db, SessionLocal
from .models import ScheduledEvent
from typing import  List, Optional
from .schema import ScheduledEventCreate, ScheduledEventResponse , ScheduledEventBase
from datetime import datetime, timedelta
import schedule, time as datetime_time, requests, threading
from collections import deque
import json


router = APIRouter()

restart_event = threading.Event()

# ===================== DAILY TASK =====================
def daily_task():
    print("TASK BOOTS UP")
    now_utc = datetime.utcnow()

    # Add 5 hours and 30 minutes for IST    
    ist_offset = timedelta(hours=5, minutes=30)
    now_ist = now_utc + ist_offset
    today = now_ist.date()
    current_time = now_ist.time()
    db: orm.Session = SessionLocal()

    try:
        events_today = db.query(ScheduledEvent).filter(
            ScheduledEvent.date == today, ScheduledEvent.time > current_time
        ).order_by(ScheduledEvent.time).all()

        if events_today:
            events_queue = deque(events_today)
            print(f"{len(events_queue)} Events scheduled for today:")

            while events_queue:
                event = events_queue.popleft()
                print(f"Processing event '{event.type}' scheduled at {event.time}")
                now = datetime.now()
                event_time = datetime.combine(now_ist.date(), event.time)
                time_diff = event_time - now_ist
                print("Time diff:", time_diff)

                time_to_wait = time_diff.total_seconds()
                if time_to_wait < 0:
                    continue

                sleep_time = int(time_to_wait)
                interval = 5  # Check every 5 seconds

                for _ in range(0, sleep_time, interval):
                    if restart_event.is_set():
                        print("Restarting daily_task due to new event...")
                        restart_event.clear()
                        return daily_task()

                    # print("Waiting...")
                    datetime_time.sleep(interval)

                # Make the request
                try:
                    body = event.value
                    # headers = {'x-tenant-id': 'ai'}
                    response = requests.post(
                        'https://whatsappbotserver.azurewebsites.net/send-template',
                        json=body
                    )
                    if response.status_code == 200:
                        print(f"Event '{event.type}' processed successfully.")
                    else:
                        print(f"Failed to process event '{event.type}'. Status code: {response.status_code}")

                except requests.RequestException as e:
                    print(f"Request failed for event '{event.type}': {e}")
        else:
            print("No events scheduled for today.")

    finally:
        db.close()
        
@router.post("/events/group", response_model=dict)
def group_events_for_next_day(tenant_id: str = Header(...), db: orm.Session = Depends(get_db)):

    print(f"🔍 Grouping today's and tomorrow's events for tenant_id: {tenant_id}")

    # Get current IST date
    now_utc = datetime.utcnow()
    ist_offset = timedelta(hours=5, minutes=30)
    now_ist = now_utc + ist_offset
    today_date = now_ist.date()
    tomorrow_date = (now_ist + timedelta(days=1)).date()

    # Query events for today and tomorrow, only for this tenant
    events = db.query(ScheduledEvent).filter(
        ScheduledEvent.date.in_([today_date, tomorrow_date]),
        ScheduledEvent.tenant_id == tenant_id
    ).all()

    if not events:
        return {"message": "No events scheduled for today or tomorrow for this tenant."}

    grouped_events = {}

    for event in events:
        value_data = event.value
        if isinstance(value_data, str):
            value_data = json.loads(value_data)

        template_name = value_data.get("template", {}).get("name")

        if template_name:
            key = (template_name, event.date)
            if key not in grouped_events:
                grouped_events[key] = []
            grouped_events[key].append({
                "id": event.id,
                "time": event.time,
                "value": value_data,
                "date": event.date
            })

    result = []

    for (template_name, event_date), event_list in grouped_events.items():
        if len(event_list) <= 1:
            continue  # no need to merge if only 1

        latest_event = max(event_list, key=lambda x: x["time"])
        latest_time = latest_event["time"]
        template = latest_event["value"].get("template")
        business_id = latest_event["value"].get("business_phone_number_id")

        # Merge phone numbers from all events
        all_phone_numbers = set()
        for event in event_list:
            phone_numbers = event["value"].get("phoneNumbers", [])
            all_phone_numbers.update(phone_numbers)

        merged_value = {
            "bg_id": "null",
            "template": template,
            "business_phone_number_id": business_id,
            "phoneNumbers": list(all_phone_numbers)
        }

        # Create the merged event
        merged_event = ScheduledEvent(
            date=event_date,
            time=latest_time,
            type="Template",
            value=merged_value,
            tenant_id=tenant_id
        )

        db.add(merged_event)
        db.commit()
        db.refresh(merged_event)

        # Delete old events
        event_ids_to_delete = [e["id"] for e in event_list]
        db.query(ScheduledEvent).filter(ScheduledEvent.id.in_(event_ids_to_delete)).delete(synchronize_session=False)
        db.commit()

        result.append({
            "merged_event_id": merged_event.id,
            "template_name": template_name,
            "event_date": str(event_date),
            "deleted_event_ids": event_ids_to_delete
        })

    return {"message": "Events grouped and merged successfully.", "results": result}

# ===================== SCHEDULER =====================
schedule.every().day.at("00:00:00").do(daily_task)

def run_scheduler():
    print("[SCHEDULER] Started")
    while True:
        # print("running scheduler")
        schedule.run_pending()
        # print("Sleeping for 10 seconds")
        if restart_event.is_set():
            print("Restarting daily_task in run scheduler")
            restart_event.clear()
            daily_task()
        # print("sleeping..")
        datetime_time.sleep(5)

        # daily_task()

@router.on_event("startup")
def startup_event():
    print(schedule.get_jobs())
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    restart_event.set()

# ===================== ROUTES =====================
@router.get("/")
def read_root():
    return {"message": "FastAPI server with scheduled task is running"}


@router.post("/scheduled-events/", response_model=ScheduledEventResponse)
def create_scheduled_event(event: ScheduledEventCreate, x_tenant_id: Optional[str] = Header(None) ,db: orm.Session = Depends(get_db)):
    global newEvent
        
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required in the headers.")

    db_event = ScheduledEvent(**event.dict(), tenant_id = x_tenant_id)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    restart_event.set()

    return db_event

@router.get("/scheduled-events/{event_id}/", response_model=ScheduledEventResponse)
def get_scheduled_event(event_id: int, db: orm.Session = Depends(get_db)):
    db_event = db.query(ScheduledEvent).filter(ScheduledEvent.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Scheduled event not found")
    return db_event

@router.get("/scheduled-events/", response_model=List[ScheduledEventResponse])
def list_scheduled_events(x_tenant_id : Optional[str] = Header(None), db: orm.Session = Depends(get_db)):
    events = db.query(ScheduledEvent).filter(ScheduledEvent.tenant_id == x_tenant_id).all()
    return events

@router.delete("/scheduled-events/{event_id}/", status_code=204)
def delete_scheduled_event(event_id: int, db: orm.Session = Depends(get_db)):
    db_event = db.query(ScheduledEvent).filter(ScheduledEvent.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Scheduled event not found")
    db.delete(db_event)
    db.commit()

    restart_event.set()

@router.put("/scheduled-events-editing/{event_id}/", response_model=ScheduledEventResponse)
def update_scheduled_event(
    event_id: int,
    updated_event: ScheduledEventBase,
    x_tenant_id: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required in the headers.")

    db_event = db.query(ScheduledEvent).filter(
        ScheduledEvent.id == event_id,
        ScheduledEvent.tenant_id == x_tenant_id
    ).first()

    if not db_event:
        raise HTTPException(status_code=404, detail="Scheduled event not found or unauthorized")

    # Update fields
    db_event.type = updated_event.type
    db_event.date = updated_event.date
    db_event.time = updated_event.time
    db_event.value = updated_event.value

    db.commit()
    db.refresh(db_event)

    return db_event