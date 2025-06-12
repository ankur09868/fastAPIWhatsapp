import redis
import os

redis_password = os.environ.get("REDIS_PASSWORD")
if not redis_password:
    raise ValueError("Missing REDIS_PASSWORD environment variable")

redis_client = redis.Redis(
    host="whatsappnuren.redis.cache.windows.net",         # e.g., "yourredisname.redis.cache.windows.net"
    port=6380,                             # Azure Redis SSL port
    password=redis_password,          # Azure Redis Access Key
    ssl=True,
    decode_responses=True
)
