"""
VÉLØ Oracle - Optimization Layer
Performance optimization utilities
"""

from .async_scheduler import run_async, run_chains_parallel, run_tasks_parallel, run_with_retry, run_with_timeout
from .latency_profiler import clear_latency_store, get_latency_stats, measure_operation, profile_latency
from .memo_cache import (
    cache_narrative,
    cache_pace_map,
    clear_cache,
    get_cache_stats,
    get_cached_narrative,
    get_cached_pace_map,
    memo_cache,
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
    "run_async",
]
