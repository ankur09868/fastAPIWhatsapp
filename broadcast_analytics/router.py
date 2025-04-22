# routers/broadcast_analytics.py
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import requests
from datetime import datetime, timedelta

from config.database import get_db
from broadcast_analytics.models import BroadcastAnalytics
from models import Tenant
from whatsapp_tenant.models import WhatsappTenantData
from .schema import TemplateAnalyticsRequest, AnalyticsResponse

router = APIRouter(
    prefix="/broadcast-analytics",
    tags=["broadcast-analytics"]
)


#  url = https://graph.facebook.com/v20.0/${accountId}/message_templates;
#       const response = await axios.get(url, {
#         headers: {
#           'Authorization': Bearer ${accessToken}
#         },
#         params: {
#           fields: 'name,status,components,language,category'
#         }
#       });


def get_start_date(days_ago: int):
    """Calculate the start date timestamp in seconds from epoch."""
    start_date = datetime.now() - timedelta(days=days_ago)
    return int(start_date.timestamp())

@router.post("/fetch-and-save", response_model=AnalyticsResponse)
async def fetch_and_save_analytics(
    request: TemplateAnalyticsRequest,
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db)
):
    try:
        request_date = datetime.strptime(request.date, "%d-%m-%Y").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD-MM-YYYY.")

    # Step 1: Check if data already exists
    existing_analytics = db.query(BroadcastAnalytics).filter(
        BroadcastAnalytics.tenant_id == x_tenant_id,
        BroadcastAnalytics.date == request_date
    ).first()

    if existing_analytics:
        return {
            "total_sent": existing_analytics.total_sent,
            "total_delivered": existing_analytics.total_delivered,
            "total_read": existing_analytics.total_read,
            "total_cost": existing_analytics.total_cost,
            "tenant_id": existing_analytics.tenant_id,
            "date": existing_analytics.date
        }

    # Step 2: Proceed to fetch if no data exists
    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    whatsapp_data = db.query(WhatsappTenantData).filter(
        WhatsappTenantData.tenant_id == x_tenant_id
    ).first()
    if not whatsapp_data:
        raise HTTPException(status_code=404, detail="WhatsApp data not found for this tenant")

    start_date = get_start_date(request.days)
    end_date = int(time.time())

    total_sent = 0
    total_delivered = 0
    total_read = 0
    total_cost = 0

    for i in range(0, len(request.template_ids), 10):
        batch_template_ids = ','.join(request.template_ids[i:i+10])
        try:
            response = requests.get(
                f"https://graph.facebook.com/v22.0/{whatsapp_data.business_account_id}/template_analytics",
                headers={'Authorization': f'Bearer {whatsapp_data.access_token}'},
                params={
                    'access_token': whatsapp_data.access_token,
                    'start': start_date,
                    'end': end_date,
                    'granularity': 'daily',
                    'metric_types': 'cost,delivered,read,sent',
                    'template_ids': batch_template_ids,
                }
            )
            response.raise_for_status()
            data = response.json()
            for template in data.get('data', []):
                for dp in template.get('data_points', []):
                    total_sent += dp.get('sent', 0)
                    total_delivered += dp.get('delivered', 0)
                    total_read += dp.get('read', 0)
                    for cost in dp.get('cost', []):
                        if cost.get('type') == 'amount_spent':
                            total_cost += cost.get('value', 0)
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    # Step 3: Save new record
    try:
        new_analytics = BroadcastAnalytics(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_read=total_read,
            total_cost=total_cost,
            tenant_id=x_tenant_id,
            date=request_date
        )
        db.add(new_analytics)
        db.commit()
        return {
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_read": total_read,
            "total_cost": total_cost,
            "tenant_id": x_tenant_id,
            "date": request_date
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/", response_model=AnalyticsResponse)
async def get_analytics(
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Retrieve broadcast analytics for a specific tenant.
    """
    # Validate tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get analytics
    analytics = db.query(BroadcastAnalytics).filter(
        BroadcastAnalytics.tenant_id == x_tenant_id
    ).first()
    
    if not analytics:
        # Return zeros if no analytics found
        return {
            "total_sent": 0,
            "total_delivered": 0,
            "total_read": 0,
            "total_cost": 0.0,
            "tenant_id": x_tenant_id
        }
    
    return analytics