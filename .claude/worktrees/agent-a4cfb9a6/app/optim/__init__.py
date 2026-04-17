"""
VÉLØ Oracle - Optimization Layer
Performance optimization utilities
"""
from .latency_profiler import (
    profile_latency,
    measure_operation,
    get_latency_stats,
    clear_latency_store
)

from .memo_cache import (
    memo_cache,
    cache_narrative,
    get_cached_narrative,
    cache_pace_map,
    get_cached_pace_map,
    clear_cache,
    get_cache_stats
)

from .async_scheduler import (
    run_chains_parallel,
    run_tasks_parallel,
    run_with_timeout,
    run_with_retry,
    run_async
)

__all__ = [
    # Latency profiler
    "profile_latency",
    "measure_operation",
    "get_latency_stats",
    "clear_latency_store",
    
    # Memo cache
    "memo_cache",
    "cache_narrative",
    "get_cached_narrative",
    "cache_pace_map",
    "get_cached_pace_map",
    "clear_cache",
    "get_cache_stats",
    
    # Async scheduler
    "run_chains_parallel",
    "run_tasks_parallel",
    "run_with_timeout",
    "run_with_retry",
    "run_async"
]
