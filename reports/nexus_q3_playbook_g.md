# NEXUS Q3 — Playbook G Live-Read Truth

**Task:** Find where `app/playbooks/playbook_g_sentient_loopback.py` (Playbook G / `SentientLoopbackEngine`) is imported and called in production.
**Date:** 2026-03-23

---

## FINDING 1 — Direct imports of `playbook_g_sentient_loopback` / `SentientLoopbackEngine`

| File | Line | Nature |
|------|------|--------|
| `scripts/close_sigma_loops.py` | **983** | Lazy import inside `_feed_playbook_g()` — PRODUCTION path |
| `scripts/run_prime_today.py` | **462** | Lazy import inside STEP 3 — AUDIT only, no scoring change |
| `app/main.py` | **31** | Import at FastAPI lifespan startup — AUDIT only |
| `scripts/proof_playbook_g_persistence.py` | **75** | Test/benchmark script |
| `scripts/proof_sentient_bridge.py` | **54** | Test/bridge proof script |
| `app/playbooks/playbook_orchestrator.py` | **48** | `from .playbook_g_sentient_loopback import create_sentient_loopback_engine` — production orchestrator |

**Exact import lines:**

```python
# scripts/close_sigma_loops.py:983
from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

# scripts/run_prime_today.py:462-463
from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
_g = SentientLoopbackEngine()

# app/main.py:31-32 (FastAPI lifespan)
from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
_g = SentientLoopbackEngine()

# app/playbooks/playbook_orchestrator.py:48
from .playbook_g_sentient_loopback import create_sentient_loopback_engine
```

---

## FINDING 2 — Is Playbook G called from `run_prime_today.py`, `score_race_velo_prime()`, or `close_sigma_loops.py`?

### `run_prime_today.py` — AUDIT ONLY, NO SCORING CHANGE
**Line 462–463** — Playbook G is instantiated but the result is **not used to alter scoring**:

```python
# scripts/run_prime_today.py:462-463
from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
_g = SentientLoopbackEngine()
```

The state is retrieved for logging/audit:
```python
# scripts/run_prime_today.py (same block)
_sentient_state = {**_raw_state, "_source": _source}
# logged but NOT passed to scoring pipeline
```
**Verdict:** G is loaded in STEP 3 of `run_prime_today.py` purely as a **read-only audit bridge**. It does not feed into `score_race_velo_prime` or any scoring model. No `SentientLoopbackEngine` method is called beyond constructor and `get_evolutionary_state()`.

### `score_race_velo_prime()` — **DOES NOT EXIST**
No function named `score_race_velo_prime` exists anywhere in the codebase.
There is no Playbook G call in any scoring function.

### `close_sigma_loops.py` — **YES, PRODUCTION CALL** ✅
**Line 941 (`_feed_playbook_g` function)** is the real production call site:

```python
# scripts/close_sigma_loops.py:941
def _feed_playbook_g(
    db: Client,
    run_reviews: List[Dict],
    verdicts_by_race: Dict[str, Dict],
    target_date: str,
) -> int:
```

Called at **line 1437** inside the sigma reconciliation loop:
```python
# scripts/close_sigma_loops.py:1437
fed_n = _feed_playbook_g(db, run_reviews, verdict_by_race, target_date)
```

Inside `_feed_playbook_g`, at **line 983-984**:
```python
from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
engine = SentientLoopbackEngine()
```

Then `engine.observe_race_outcome(...)` is called per race to feed outcomes back into G's evolution loop. This is the **daily auto-pipeline** (Step 9 of sigma reconciliation).

Also called from `scripts/feed_sigma_loop.py:157`:
```python
# scripts/feed_sigma_loop.py:157-158
from scripts.close_sigma_loops import _feed_playbook_g
fed_n = _feed_playbook_g(db, run_reviews, verdicts_by_race, target_date)
```
This delegates to the same `_feed_playbook_g` implementation in `close_sigma_loops.py`.

---

## FINDING 3 — `app/playbooks/playbook_orchestrator.py` — Imported Where?

| File | Line | Import |
|------|------|--------|
| `scripts/activate_betfair_live.py` | **18** | `from app.playbooks.playbook_orchestrator import create_playbook_orchestrator` |
| `app/agents/betfair_execution_agent.py` | **13** | `from app.playbooks.playbook_orchestrator import create_playbook_orchestrator` |

The orchestrator (which holds a `SentientLoopbackEngine` instance as `self.sentient_loopback`) is used in the **Betfair execution agent** — a live trading context. However, the orchestrator's G instance is only ever queried via `get_evolutionary_state()` and `identify_kingmaker()` — it does not call `observe_race_outcome()` in the live scoring path.

---

## FINDING 4 — `app/playbooks/__init__.py` — What Does It Export?

```python
from .playbook_orchestrator import create_playbook_orchestrator, PlaybookOrchestrator

__all__ = ["create_playbook_orchestrator", "PlaybookOrchestrator"]
```

**Playbook G / `SentientLoopbackEngine` is NOT exported from `__init__.py`.** It must be imported directly via the full module path: `from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine`.

---

## FINDING 5 — `SENTIENT_STATE_BACKUP` Pattern in Live Scoring Path?

### Read path:
`app/playbooks/playbook_g_sentient_loopback.py:116` (in `_load_state()`):
> Priority order: (1) Local `sentient_state.json` → (2) Supabase `SENTIENT_STATE_BACKUP` row → (3) Fresh state

```python
# playbook_g_sentient_loopback.py:156
# Reads SENTIENT_STATE_BACKUP when local state file is absent/unreadable:
supabase.query(...).eq("pattern_name", "SENTIENT_STATE_BACKUP")
```

### Write path:
`playbook_g_sentient_loopback.py:218` — writes state to Supabase with:
```python
"pattern_name": "SENTIENT_STATE_BACKUP"
```
This is the **backup row** that survives Railway restarts/redeploys.

### In live scoring path (`run_prime_today.py` STEP 3):
`SENTIENT_STATE_BACKUP` is **NOT read** directly by the live scoring path. The `SentientLoopbackEngine()` is instantiated at line 462 purely to retrieve `get_evolutionary_state()` for audit logging — `_sentient_state` is stored and logged but **never passed into the scoring model**.

### In `close_sigma_loops.py` Step 9:
`SENTIENT_STATE_BACKUP` is **implicitly written** when `engine.observe_race_outcome()` is called — the backup upsert happens inside `SentientLoopbackEngine` automatically. The dedup marker used is `playbook_g_fed_{date}`, NOT `SENTIENT_STATE_BACKUP`.

### In `velo_morning_cockpit.py`:
```python
# Line 169 — queries SENTIENT_STATE_BACKUP
.eq("pattern_name", "SENTIENT_STATE_BACKUP")
```
This is a **read-only dashboard query**, not part of the live scoring pipeline.

---

## SUMMARY

| Question | Answer |
|----------|--------|
| Is Playbook G called in live scoring (`run_prime_today.py`)? | **No** — instantiated for audit logging only, not fed into scoring model |
| Is `score_race_velo_prime()` a real function? | **No such function exists** |
| Is Playbook G called in `close_sigma_loops.py`? | **Yes** — `_feed_playbook_g()` at line 941/1437, PRODUCTION auto-pipeline Step 9 |
| Is `playbook_orchestrator.py` imported in production? | **Yes** — in Betfair execution agent (`activate_betfair_live.py:18`, `betfair_execution_agent.py:13`) |
| Does `__init__.py` export Playbook G? | **No** — only the orchestrator is exported |
| Is `SENTIENT_STATE_BACKUP` read in live scoring? | **No** — read only in G's own `_load_state()` and in dashboard queries |
| Does G actually evolve during live scoring? | **No** — `observe_race_outcome()` is only called in the nightly `close_sigma_loops.py` pipeline |

**Playbook G's `SentientLoopbackEngine.observe_race_outcome()` — the only method that causes G to evolve — is exclusively called from `_feed_playbook_g()` in `close_sigma_loops.py` as part of the daily sigma reconciliation auto-pipeline. It is NOT in the live scoring path.**
