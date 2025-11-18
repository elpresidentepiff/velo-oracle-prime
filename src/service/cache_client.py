# src/service/cache_client.py

import logging
import pickle
from typing import Any, Optional
import os

try:
    import redis
except ImportError:
    redis = None
    logging.warning("Redis not installed. Cache client will not be available. Install with: pip install redis")

logger = logging.getLogger(__name__)

class RedisCacheClient:
    """A client for storing and retrieving serialized Python objects in Redis."""
    def __init__(self, redis_url: str):
        if redis is None:
            raise ImportError("Redis client is required. Please run 'pip install redis'.")
        
        try:
            self.client = redis.from_url(redis_url, decode_responses=False) # Handle bytes for pickle
            self.client.ping()
            logger.info(f"Successfully connected to Redis at {redis_url}.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"FATAL: Could not connect to Redis at {redis_url}. {e}")
            raise

    def set_object(self, key: str, obj: Any, ttl_seconds: int = 3600):
        """Serializes a Python object with pickle and stores it in Redis."""
        try:
            serialized_obj = pickle.dumps(obj)
            self.client.set(key, serialized_obj, ex=ttl_seconds)
            logger.info(f"Cached object with key '{key}'. Size: {len(serialized_obj)} bytes.")
        except Exception as e:
            logger.error(f"Failed to set object for key '{key}': {e}")

    def get_object(self, key: str) -> Optional[Any]:
        """Retrieves and deserializes a Python object from Redis."""
        try:
            serialized_obj = self.client.get(key)
            if serialized_obj is None:
                logger.warning(f"Cache miss for key '{key}'.")
                return None
            
            logger.info(f"Cache hit for key '{key}'.")
            return pickle.loads(serialized_obj)
        except Exception as e:
            logger.error(f"Failed to get object for key '{key}': {e}")
            return None

    def invalidate(self, key: str):
        """Deletes a key from the cache."""
        self.client.delete(key)
        logger.info(f"Invalidated cache for key '{key}'.")

    def publish_invalidation(self, channel: str, key: str):
        """Publishes a message to a channel to notify subscribers to invalidate a key."""
        self.client.publish(channel, key)
        logger.info(f"Published invalidation message for key '{key}' on channel '{channel}'.")

# --- Default Instance ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Only create default instance if Redis is available
default_cache_client = None
if redis is not None:
    try:
        default_cache_client = RedisCacheClient(redis_url=REDIS_URL)
    except Exception as e:
        logger.warning(f"Could not initialize default Redis cache client: {e}")

