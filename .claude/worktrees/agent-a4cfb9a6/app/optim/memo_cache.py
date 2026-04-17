"""
VÉLØ Oracle - Memo Cache
LRU caching for expensive operations
"""
from functools import lru_cache
from typing import Dict, Any, Callable
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# Global cache store
CACHE_STORE: Dict[str, Any] = {}


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = {
        "args": args,
        "kwargs": kwargs
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


def memo_cache(maxsize: int = 128):
    """
    Decorator for memoization with LRU cache
    
    Usage:
        @memo_cache(maxsize=256)
        def expensive_function(x):
            ...
    """
    def decorator(func: Callable):
        # Use functools.lru_cache
        cached_func = lru_cache(maxsize=maxsize)(func)
        return cached_func
    return decorator


def cache_narrative(race_id: str, narrative: Dict[str, Any]) -> None:
    """Cache narrative analysis"""
    key = f"narrative:{race_id}"
    CACHE_STORE[key] = narrative
    logger.debug(f"Cached narrative for {race_id}")


def get_cached_narrative(race_id: str) -> Dict[str, Any]:
    """Get cached narrative"""
    key = f"narrative:{race_id}"
    return CACHE_STORE.get(key)


def cache_pace_map(race_id: str, pace_map: Dict[str, Any]) -> None:
    """Cache pace map"""
    key = f"pace:{race_id}"
    CACHE_STORE[key] = pace_map
    logger.debug(f"Cached pace map for {race_id}")


def get_cached_pace_map(race_id: str) -> Dict[str, Any]:
    """Get cached pace map"""
    key = f"pace:{race_id}"
    return CACHE_STORE.get(key)


def cache_risk_classification(runner_id: str, risk: Dict[str, Any]) -> None:
    """Cache risk classification"""
    key = f"risk:{runner_id}"
    CACHE_STORE[key] = risk
    logger.debug(f"Cached risk for {runner_id}")


def get_cached_risk(runner_id: str) -> Dict[str, Any]:
    """Get cached risk classification"""
    key = f"risk:{runner_id}"
    return CACHE_STORE.get(key)


def cache_overlay_detection(runner_id: str, overlay: Dict[str, Any]) -> None:
    """Cache overlay detection"""
    key = f"overlay:{runner_id}"
    CACHE_STORE[key] = overlay
    logger.debug(f"Cached overlay for {runner_id}")


def get_cached_overlay(runner_id: str) -> Dict[str, Any]:
    """Get cached overlay"""
    key = f"overlay:{runner_id}"
    return CACHE_STORE.get(key)


def clear_cache(pattern: str = None) -> int:
    """
    Clear cache entries
    
    Args:
        pattern: Optional pattern to match (e.g., "narrative:")
        
    Returns:
        Number of entries cleared
    """
    global CACHE_STORE
    
    if pattern:
        keys_to_delete = [k for k in CACHE_STORE if k.startswith(pattern)]
        for key in keys_to_delete:
            del CACHE_STORE[key]
        count = len(keys_to_delete)
    else:
        count = len(CACHE_STORE)
        CACHE_STORE = {}
    
    logger.info(f"✅ Cleared {count} cache entries")
    return count


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    
    # Count by type
    type_counts = {}
    for key in CACHE_STORE:
        cache_type = key.split(":")[0]
        type_counts[cache_type] = type_counts.get(cache_type, 0) + 1
    
    return {
        "total_entries": len(CACHE_STORE),
        "by_type": type_counts
    }
