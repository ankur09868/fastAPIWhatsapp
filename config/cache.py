import time
import threading

# Global cache store
custom_cache = {}
CACHE_TTL = 300  # seconds
cache_lock = threading.Lock()

def get_cache(key: str):
    with cache_lock:
        item = custom_cache.get(key)
        if item:
            value, timestamp = item
            if time.time() - timestamp < CACHE_TTL:
                return value
            else:
                del custom_cache[key]
    return None

def set_cache(key: str, value):
    with cache_lock:
        custom_cache[key] = (value, time.time())