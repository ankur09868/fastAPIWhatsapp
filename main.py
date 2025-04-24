from fastapi import FastAPI
from config.database import engine, Base
from config.middleware import add_cors_middleware
import contacts.router, node_templates.router, scheduled_events.router, whatsapp_tenant.router
import product.router, dynamic_models.router
import conversations.router, emails, notifications.router
import broadcast_analytics.router
import catalog.router
import flowsAPI.router 
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

newEvent = False
app = FastAPI()

add_cors_middleware(app)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include all routers
app.include_router(contacts.router.router)
app.include_router(node_templates.router.router)
app.include_router(whatsapp_tenant.router.router)
app.include_router(scheduled_events.router.router)
app.include_router(product.router.router)
app.include_router(dynamic_models.router.router)
app.include_router(conversations.router.router)
app.include_router(emails.router)
app.include_router(notifications.router.router)
app.include_router(flowsAPI.router.router)
app.include_router(catalog.router.router)
app.include_router(broadcast_analytics.router.router)


@app.get("/")
def read_root():
    return {"message": "FastAPI server is running"}