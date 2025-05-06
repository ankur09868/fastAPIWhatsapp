import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from config.database import get_db
from broadcast_analytics.models import BroadcastAnalytics
from models import Tenant
from whatsapp_tenant.models import WhatsappTenantData
from .schema import TemplateAnalyticsRequest, AnalyticsResponse
from sqlalchemy import func

router = APIRouter(
    prefix="/broadcast-analytics",
    tags=["broadcast-analytics"]
)

def get_start_date(days_ago: int):
    start_date = datetime.now() - timedelta(days=days_ago)
    return int(start_date.timestamp())

def fetch_analytics_for_template(template_id, access_token, business_account_id):
    durations = [1, 7, 30, 60, 90]  # in days
    last_successful_data = None

    for days in durations:
        start = get_start_date(days)
        end = int(time.time())

        print(f"Fetching analytics for template {template_id} for {days} days (start: {start}, end: {end})")
        
        try:
            response = requests.get(
                f"https://graph.facebook.com/v22.0/{business_account_id}/template_analytics",
                headers={'Authorization': f'Bearer {access_token.strip()}'},
                params={
                    'start': start,
                    'end': end,
                    'granularity': 'daily',
                    'metric_types': 'cost,delivered,read,sent',
                    'template_ids': template_id,
                }
            )

            if response.status_code == 200:
                print(f"Successfully fetched data for {template_id} (duration: {days} days)")
                last_successful_data = response.json()
            else:
                print(f"Error fetching data for {template_id} (status code: {response.status_code})")
                break  # Stop trying longer durations if we hit an error

        except Exception as e:
            print(f"Exception fetching data for {template_id} during {days} days: {e}")
            break  # Stop if an exception occurs

    if last_successful_data:
        print(f"Returning data for {template_id}")
        print(f"data>last_successful_data{last_successful_data}")
        return last_successful_data

    print(f"No data found for {template_id} after checking all durations.")
    return None

def process_template_analytics(whatsapp_data, template_ids):
    total_sent = 0
    total_delivered = 0
    total_read = 0
    total_cost = 0
    
    for template_id in template_ids:
        print(f"Processing analytics for template {template_id}...")
        data = fetch_analytics_for_template(template_id, whatsapp_data.access_token, whatsapp_data.business_account_id)
        if not data:
            print(f"No data found for template {template_id}. Skipping.")
            continue
        for template in data.get('data', []):
            for dp in template.get('data_points', []):
                total_sent += dp.get('sent', 0)
                total_delivered += dp.get('delivered', 0)
                total_read += dp.get('read', 0)
                for cost in dp.get('cost', []):
                    if cost.get('type') == 'amount_spent':
                        total_cost += cost.get('value', 0)

    print(f"Total data processed: Sent={total_sent}, Delivered={total_delivered}, Read={total_read}, Cost={total_cost}")
    return total_sent, total_delivered, total_read, total_cost

@router.post("/fetch-and-save", response_model=AnalyticsResponse)
async def fetch_and_save_analytics(
    request: TemplateAnalyticsRequest,
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db)
):
    print(f"Fetching and saving analytics for tenant {x_tenant_id} on date {request.date}")
    try:
        request_date = datetime.strptime(request.date, "%d-%m-%Y").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD-MM-YYYY.")

    existing = db.query(BroadcastAnalytics).filter_by(tenant_id=x_tenant_id, date=request_date).first()
    if existing:
        print(f"Analytics already exist for tenant {x_tenant_id} on date {request.date}. Returning existing data.")
        return existing

    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    whatsapp_data = db.query(WhatsappTenantData).filter_by(tenant_id=x_tenant_id).first()
    if not whatsapp_data:
        raise HTTPException(status_code=404, detail="WhatsApp data not found")

    total_sent, total_delivered, total_read, total_cost = process_template_analytics(whatsapp_data, request.template_ids)

    try:
        record = BroadcastAnalytics(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_read=total_read,
            total_cost=total_cost,
            tenant_id=x_tenant_id,
            date=request_date
        )
        db.add(record)
        db.commit()
        print(f"Successfully saved analytics for tenant {x_tenant_id} on date {request.date}")
        return record
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/", response_model=Optional[AnalyticsResponse])
async def get_analytics_all(
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db)
):
    print(f"Fetching all analytics for tenant {x_tenant_id}")
    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get today's date
    today = datetime.now().date()

     # Filter and get only analytics up to today's date
    analytics = (
        db.query(BroadcastAnalytics)
        .filter(
            BroadcastAnalytics.tenant_id == x_tenant_id,
            func.date(BroadcastAnalytics.date) <= today
        )
        .order_by(BroadcastAnalytics.date.desc())  # Optional: newest first
        .first()
    )
    return analytics

def run_scheduled_job():
    print("Running scheduled job...")
    db = next(get_db())
    tenants = db.query(Tenant).all()
    for tenant in tenants:
        print(f"Processing tenant {tenant.id}")
        whatsapp_data = db.query(WhatsappTenantData).filter_by(tenant_id=tenant.id).first()
        if not whatsapp_data:
            print(f"No WhatsApp data found for tenant {tenant.id}. Skipping.")
            continue

        template_response = requests.get(
            f"https://graph.facebook.com/v20.0/{whatsapp_data.business_account_id}/message_templates",
            headers={'Authorization': f'Bearer {whatsapp_data.access_token.strip()}'},
            params={
                'fields': 'name,status,components,language,category'
            }
        )
        if template_response.status_code != 200:
            print(f"Failed to fetch templates for tenant {tenant.id}. Status code: {template_response.status_code}")
            continue

        template_data = template_response.json().get('data', [])
        template_ids = [t['id'] for t in template_data]
        template_names = [t['name'] for t in template_data]

        print(f"Templates for tenant {tenant.id}:")
        for name, id_ in zip(template_names, template_ids):
            print(f"- {name} (ID: {id_})")

        total_sent, total_delivered, total_read, total_cost = process_template_analytics(whatsapp_data, template_ids)

        record = BroadcastAnalytics(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_read=total_read,
            total_cost=total_cost,
            tenant_id=tenant.id,
            date=datetime.now().date()
        )
        try:
            db.add(record)
            db.commit()
            print(f"Successfully saved analytics for tenant {tenant.id}.")
        except:
            db.rollback()
            print(f"Failed to save analytics for tenant {tenant.id}.")

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.add_job(run_scheduled_job, 'cron', hour=0, minute=0)
scheduler.start()
