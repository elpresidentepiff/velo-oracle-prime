# NEXUS Q1 — BHA Macro Parquet Failure Path

**File:** `/home/purorpurorestrepo1981/.openclaw/workspace/repos/velo-oracle-prime/src/intelligence/macro_regime/bha_macro_context.py`

---

## 1. Exact Function That Raises FileNotFoundError

**`_load_macro_df()`** at lines 117–122:

```python
if not _DATA_PATH.exists():
    raise FileNotFoundError(
        f"BHA macro features not found at {_DATA_PATH}. "
        "Run: python scripts/cache_bha_macro_features.py"
    )
```

- **Data path:** `data/bha_macro_features.parquet` (relative to repo root)
- The `@lru_cache(maxsize=1)` decorator means this is only evaluated **once per process**, then cached.

---

## 2. Every Caller of That Function

```
_load_macro_df()
  └── get_macro_context()          [bha_macro_context.py:142]
        ├── get_macro_context_for_race() [bha_macro_context.py:183]
        │     └── (used in production path — see §5)
        └── __main__ self-test       [bha_macro_context.py:199–241]
              (NOT production)
```

**No other module calls `_load_macro_df()` directly.** It is private (`_`-prefixed).

---

## 3. Is the Exception Caught?

**No.** The `FileNotFoundError` raised in `_load_macro_df()` is **not caught anywhere** inside `bha_macro_context.py`.

It **propagates uncaught** to the caller of `get_macro_context()` / `get_macro_context_for_race()`.

---

## 4. Fallback Behavior When Parquet Is Absent

In the **production path** (`score_race_velo_prime`, velo_prime_service.py:208–214):

```python
try:
    macro_ctx = get_macro_context_for_race(race_date, code)
except Exception as e:
    log.warning("Macro context unavailable: %s", e)
    macro_ctx = None          # ← fallback: None
```

When parquet is absent:
- `FileNotFoundError` bubbles up → caught by `except Exception` → `macro_ctx = None`
- `VeloPrimeEnsemble.predict_race(..., macro_context=None)` is called
- Inside `predict_race()`, `macro_context` is typed `MacroContext | None`, but the code at line ~172 references it as `MacroContext` — **no null guard is shown in the grep'd excerpt**; this is a potential `AttributeError` if `macro_ctx` is `None` and accessed
- No null/0/skip is applied to individual macro features — the whole context is None

**Fallback result:** macro features are entirely absent from ensemble scoring. `macro_ctx.chaos_mode`, `macro_ctx.regime_label`, etc. are never consulted.

---

## 5. Is This on the Production Scoring Path?

**YES.** The call chain is:

```
scripts/run_prime_today.py  (line 490)
  └── score_race_velo_prime()           [app/services/velo_prime_service.py:172]
        ├── VeloPrimeEnsemble()          [line 191]
        ├── get_macro_context_for_race() [line 212]
        │     └── get_macro_context()    [bha_macro_context.py:183 → 142]
        │           └── _load_macro_df() [bha_macro_context.py:117]
        │                 └── FileNotFoundError ← possible here
        └── ensemble.predict_race()     [line 250]
```

This is the **live scoring path** (run_prime_today → score_race_velo_prime → ensemble), not the self-test block.

---

## Summary Table

| Item | Value |
|---|---|
| Exception-raising function | `_load_macro_df()` @ line ~119 |
| FileNotFoundError raised? | YES — when `data/bha_macro_features.parquet` is absent |
| Caught internally? | NO — propagates to callers |
| Production caller | `score_race_velo_prime()` @ velo_prime_service.py:212 |
| Caught in production? | YES — generic `except Exception` → `macro_ctx = None` |
| Fallback behavior | `macro_ctx = None`; ensemble proceeds without macro features |
| On live scoring path? | **YES** — run_prime_today.py → score_race_velo_prime → ensemble |

---

## Risk Assessment

- **If parquet is absent and `macro_ctx` is accessed without a null check in `predict_race()`** → `AttributeError` crash at scoring time.
- **Recommended fix:** Add null guard in `VeloPrimeEnsemble.predict_race()`:
  ```python
  if macro_context is None:
      macro_context = MacroContext(year=2024, race_code="flat").classify()
  ```
  Or ensure `data/bha_macro_features.parquet` is always pre-cached.
