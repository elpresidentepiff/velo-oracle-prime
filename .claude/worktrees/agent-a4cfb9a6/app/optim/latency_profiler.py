"""
VÉLØ Oracle - Latency Profiler
Measure and profile execution latencies
"""
import time
from typing import Dict, Any, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Global latency store
LATENCY_STORE: Dict[str, list] = {}


def profile_latency(operation_name: str):
    """
    Decorator to profile function latency
    
    Usage:
        @profile_latency("model_load")
        def load_model():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Store latency
            if operation_name not in LATENCY_STORE:
                LATENCY_STORE[operation_name] = []
            
            LATENCY_STORE[operation_name].append(elapsed_ms)
            
            logger.debug(f"⏱️ {operation_name}: {elapsed_ms:.2f}ms")
            
            return result
        return wrapper
    return decorator


def measure_operation(operation_name: str, func: Callable, *args, **kwargs) -> tuple:
    """
    Measure operation latency
    
    Returns:
        (result, latency_ms)
    """
    start_time = time.time()
    result = func(*args, **kwargs)
    latency_ms = (time.time() - start_time) * 1000
    
    # Store latency
    if operation_name not in LATENCY_STORE:
        LATENCY_STORE[operation_name] = []
    
    LATENCY_STORE[operation_name].append(latency_ms)
    
    return result, latency_ms


def get_latency_stats(operation_name: str = None) -> Dict[str, Any]:
    """
    Get latency statistics
    
    Args:
        operation_name: Optional specific operation, or None for all
        
    Returns:
        Latency statistics
    """
    if operation_name:
        if operation_name not in LATENCY_STORE:
            return {"error": "Operation not found"}
        
        latencies = LATENCY_STORE[operation_name]
        
        if not latencies:
            return {"count": 0}
        
        return {
            "operation": operation_name,
            "count": len(latencies),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "avg_ms": sum(latencies) / len(latencies),
            "p50_ms": sorted(latencies)[len(latencies) // 2],
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
            "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0]
        }
    else:
        # All operations
        stats = {}
        for op_name in LATENCY_STORE:
            stats[op_name] = get_latency_stats(op_name)
        return stats


def clear_latency_store():
    """Clear all stored latencies"""
    global LATENCY_STORE
    LATENCY_STORE = {}
    logger.info("✅ Latency store cleared")


def get_operation_breakdown() -> Dict[str, float]:
    """
    Get breakdown of average latencies by operation
    
    Returns:
        Dictionary of operation -> avg latency (ms)
    """
    breakdown = {}
    
    for op_name, latencies in LATENCY_STORE.items():
        if latencies:
            breakdown[op_name] = sum(latencies) / len(latencies)
    
    return breakdown
