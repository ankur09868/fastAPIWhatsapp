from fastapi import APIRouter, Request, Depends, HTTPException, Header, encoders
from sqlalchemy import orm, func, and_
from config.database import get_db
from .models import Notifications
from typing import Optional
from datetime import datetime, timedelta
from contacts.models import Contact
router = APIRouter()


def convert_time(datetime_str):
    """
    Converts a date-time string from 'DD/MM/YYYY, HH:MM:SS.SSS'
    to PostgreSQL-compatible 'YYYY-MM-DD HH:MM:SS.SSS' format.
    
    Args:
        datetime_str (str): The date-time string to be converted.
    
    Returns:
        str: Converted date-time string in PostgreSQL format.
    """
    try:
        # Parse the input date-time string
        parsed_datetime = datetime.strptime(datetime_str, "%d/%m/%Y, %H:%M:%S.%f")
        # Convert it to the PostgreSQL-compatible format
        postgres_format = parsed_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")
        return postgres_format
    except ValueError as e:
        print(f"Error converting datetime: {e}")
        return None
    

@router.post("/notifications")
async def add_notifications(req: Request, db: orm.Session = Depends(get_db)):
    
    try:
        tenant_id = req.headers.get('X-Tenant-Id')
        body = await req.json()  # Use await to extract the JSON body asynchronously
        content = body.get('content')
        created_on = body.get('created_on')
        created_on_time = convert_time(created_on)

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID is required in the headers.")
        
        if not content:
            raise HTTPException(status_code=400, detail="Content is required in the request body.")

        notification = Notifications(
            content=content,
            tenant_id=tenant_id,
            created_on = created_on_time
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)  # Refresh to get the updated notification object with any DB-generated fields (like id)
    except Exception as e:
        print("Exceptions: ", e)
        db.rollback()  # Rollback in case of error
        raise HTTPException(status_code=500, detail="Failed to add notification.")
    
    return {"message": "Notification added successfully", "notification_id": notification.id}

@router.get("/notifications")
def get_notifications(
    day: Optional[int] = None, #no of days in past
    x_tenant_id: Optional[str] = Header(None), 
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required in the headers.")
    
    if day:
        today = datetime.now()
        that_day = today - timedelta(days=day)
        notifications = (
            db.query(Notifications)
            .filter(Notifications.tenant_id == x_tenant_id)
            .filter(Notifications.created_on == that_day)
            .order_by(Notifications.created_on.desc())
            .all()
        )
    else:
        notifications = (
            db.query(Notifications)
            .filter(Notifications.tenant_id == x_tenant_id)
            .order_by(Notifications.created_on.desc())
            .all()
        )    
        
    if not notifications:
        raise HTTPException(status_code=404, detail="No notifications found for the tenant.")

    return {"notifications": notifications}


@router.get("/notifications/{page_no}")
def get_limited_notifications(
    page_no: int,
    x_tenant_id: Optional[str] = Header(None),
    db: orm.Session = Depends(get_db),
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required in the headers.")
    
    limit = 10  # Number of contacts per page
    offset = limit * (page_no - 1)
    
    total = db.query(Notifications).filter(Notifications.tenant_id == x_tenant_id).count()

    total_pages = (total + limit - 1) // limit

    notifications_with_contacts = (
        db.query(Notifications, Contact)
        .outerjoin(
            Contact,
            and_(
                Contact.phone == func.substr(Notifications.content, 1, 12),
                Contact.tenant_id == Notifications.tenant_id
            )
        )
        .filter(Notifications.tenant_id == x_tenant_id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Process results
    enhanced_notifications = []
    for notification, contact in notifications_with_contacts:
        notif_data = encoders.jsonable_encoder(notification)
        if contact:
            notif_data["contact_id"] = contact.id
        enhanced_notifications.append(notif_data)


    return {
        "contacts": enhanced_notifications,
        "page_no": page_no or None,
        "page_size": limit or None,
        "total_contacts": len(enhanced_notifications),
        "total_pages": total_pages or None,
    }

@router.delete("/notifications/{notification_id}", status_code=204)
def delete_notification(
    notification_id: int,
    db: orm.Session = Depends(get_db)
):
    notification = db.query(Notifications).filter(Notifications.id == notification_id).first()

    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()

@router.delete("/notification/all", status_code=204)
def delete_all_notifications(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),  # Correct header alias
    db: orm.Session = Depends(get_db)
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required in the header")

    try:
        # Convert tenant_id to int if necessary (only if stored as int in DB)
        # tenant_id = int(x_tenant_id)  

        notifications = db.query(Notifications).filter(Notifications.tenant_id == x_tenant_id).all()
        print(f"Tenant ID: {x_tenant_id}, Notifications Found: {len(notifications)}")  # Debugging

        if not notifications:
            raise HTTPException(status_code=404, detail="No notifications found for this tenant")

        # Bulk delete for efficiency
        db.query(Notifications).filter(Notifications.tenant_id == x_tenant_id).delete(synchronize_session=False)
        db.commit()
        
        return {"message": "All notifications deleted successfully"}  # Only if status_code is 200

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting notifications: {str(e)}")
