"""
VÉLØ Oracle - Async Scheduler
Parallel execution of intelligence chains
"""
import asyncio
from typing import Dict, Any, List, Callable
import logging

logger = logging.getLogger(__name__)


async def run_chains_parallel(
    race: Dict[str, Any],
    runners: List[Dict[str, Any]],
    odds_movements: List[Dict] = None
) -> Dict[str, Any]:
    """
    Run multiple intelligence chains in parallel
    
    Args:
        race: Race data
        runners: List of runners
        odds_movements: Optional odds movements
        
    Returns:
        Combined results from all chains
    """
    from app.intelligence.chains import (
        run_narrative_chain,
        run_market_chain,
        run_pace_chain
    )
    from app.services.risk_layer import batch_risk_evaluation
    
    logger.info("Running chains in parallel...")
    
    # Run chains concurrently
    results = await asyncio.gather(
        run_narrative_chain(race, odds_movements),
        run_market_chain(race, odds_movements or []),
        run_pace_chain(runners, race),
        return_exceptions=True
    )
    
    # Unpack results
    narrative_result = results[0] if not isinstance(results[0], Exception) else {"status": "error", "error": str(results[0])}
    market_result = results[1] if not isinstance(results[1], Exception) else {"status": "error", "error": str(results[1])}
    pace_result = results[2] if not isinstance(results[2], Exception) else {"status": "error", "error": str(results[2])}
    
    # Calculate total execution time
    total_time = (
        narrative_result.get("execution_duration_ms", 0) +
        market_result.get("execution_duration_ms", 0) +
        pace_result.get("execution_duration_ms", 0)
    )
    
    # Note: Parallel execution means actual wall time is max, not sum
    actual_time = max(
        narrative_result.get("execution_duration_ms", 0),
        market_result.get("execution_duration_ms", 0),
        pace_result.get("execution_duration_ms", 0)
    )
    
    logger.info(f"✅ Parallel chains complete: {actual_time:.2f}ms (vs {total_time:.2f}ms sequential)")
    
    return {
        "narrative": narrative_result,
        "market": market_result,
        "pace": pace_result,
        "parallel_execution_ms": actual_time,
        "sequential_equivalent_ms": total_time,
        "speedup": total_time / actual_time if actual_time > 0 else 1.0
    }


async def run_tasks_parallel(tasks: List[Callable]) -> List[Any]:
    """
    Run arbitrary async tasks in parallel
    
    Args:
        tasks: List of async callables
        
    Returns:
        List of results
    """
    logger.info(f"Running {len(tasks)} tasks in parallel...")
    
    results = await asyncio.gather(*[task() for task in tasks], return_exceptions=True)
    
    # Count successes and failures
    successes = sum(1 for r in results if not isinstance(r, Exception))
    failures = len(results) - successes
    
    logger.info(f"✅ Parallel tasks complete: {successes} succeeded, {failures} failed")
    
    return results


async def run_with_timeout(coro, timeout: float):
    """
    Run coroutine with timeout
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        
    Returns:
        Result or raises TimeoutError
    """
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        logger.error(f"❌ Operation timed out after {timeout}s")
        raise


async def run_with_retry(
    coro_func: Callable,
    max_retries: int = 3,
    delay: float = 1.0
) -> Any:
    """
    Run coroutine with retry logic
    
    Args:
        coro_func: Async function to call
        max_retries: Maximum number of retries
        delay: Delay between retries (seconds)
        
    Returns:
        Result from successful execution
    """
    for attempt in range(max_retries):
        try:
            result = await coro_func()
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}, retrying...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ All {max_retries} attempts failed")
                raise


def run_async(coro):
    """
    Helper to run async coroutine from sync context
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result from coroutine
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)
