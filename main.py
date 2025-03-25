from fastapi import FastAPI
from config.database import engine, Base
from config.middleware import add_cors_middleware
import contacts.router, node_templates.router, scheduled_events.router, whatsapp_tenant.router
import product.router, dynamic_models.router
import conversations.router, emails, notifications.router
import flowsAPI.router 
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
import logging
import os

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

@app.on_event("startup")
async def startup_event():
    """Initialize Azure Redis Cache on startup"""
    try:
        # Get Redis password from environment variable
        redis_password = os.environ.get("REDIS_PASSWORD")
        if not redis_password:
            logging.warning("REDIS_PASSWORD environment variable not set")
            return

        # Connect to Azure Redis Cache
        redis = aioredis.from_url(
            f"redis://whatsappnuren.redis.cache.windows.net:6379",
            password=redis_password,
            encoding="utf8",
            decode_responses=True,
            ssl=True  # Azure Redis requires SSL
        )
        
        # Initialize FastAPI Cache with Redis backend
        FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
        logging.info("Azure Redis Cache initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize Redis cache: {str(e)}")
        # Continue without cache if Redis is not available
        logging.warning("Application will run without Redis caching")

@app.get("/")
def read_root():
    return {"message": "FastAPI server is running"}