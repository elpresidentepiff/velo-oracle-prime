# NEXUS Query 2: Macro Context Live Consumers

**Files examined:**
- `src/intelligence/velo_prime_ensemble.py`
- `app/services/velo_prime_service.py`

---

## Summary

| Location | File | Lines | Guarded? | Changes `velo_prime_prob`? | Material? |
|---|---|---|---|---|---|
| `VeloPrimePrediction.compute()` | ensemble | 83–104 | ✅ `if self.macro_context is not None:` | **YES** | **YES** |
| `VeloPrimePrediction.to_dict()` | ensemble | 108–109 | ✅ `if self.macro_context:` | No | Cosmetic |
| `score_race_velo_prime()` macro fetch | service | 219–224 | N/A (sets to `None` on failure) | N/A | — |
| `score_race_velo_prime()` output enrichment | service | 257–258 | ✅ ternary `macro_ctx if macro_ctx else ...` | No | Cosmetic |

**Only one material consumer:** `VeloPrimePrediction.compute()` (ensemble, lines 83–104). All other reads are cosmetic output enrichment.

---

## Detail by Location

### 1. `VeloPrimePrediction.compute()` — MATERIAL
**File:** `src/intelligence/velo_prime_ensemble.py`
**Lines:** 83–104

```python
if self.macro_context is not None:          # line 83 — GUARDED ✅
    ctx = self.macro_context

    # Chaos mode: dampen confidence
    if ctx.chaos_mode:                       # line 86 — reads chaos_mode
        prob = _MACRO_CHAOS_CONFIDENCE_DAMPER * prob + ...
        self.verdict_flags.append("macro:chaos_regime_dampened")
        self.regime_override = "chaos"

    # Favourite trap: apply penalty
    if ctx.favourite_trap_risk == "high" and self.is_fav:  # line 92
        prob = max(0.01, prob - _MACRO_COMPRESSION_FAV_PENALTY)
        self.verdict_flags.append("macro:fav_trap_penalty_applied")

    # Thin market: increase uncertainty
    if ctx.field_size_regime == "tight":     # line 97
        prob = (1 - _MACRO_THIN_MARKET_UNCERTAINTY) * prob + ...
        self.verdict_flags.append("macro:thin_market_uncertainty")
```

- **Guard:** ✅ Yes — `if self.macro_context is not None:`
- **Probability impact:** YES — all three branches modify `prob`, which is then assigned to `self.velo_prime_prob`. Missing macro context means these adjustments are silently skipped.
- **Material:** YES — `chaos_mode` blends prob toward uniform (can substantially change rankings in small fields); `favourite_trap_risk` subtracts 5pp from the favourite; `field_size_regime == "tight"` spreads probability toward uniform.
- **Verdict flags / regime_override:** These are only set when macro context is present, so absent context also removes annotations from the output.

---

### 2. `VeloPrimePrediction.to_dict()` — COSMETIC
**File:** `src/intelligence/velo_prime_ensemble.py`
**Lines:** 108–109

```python
"macro_regime": self.macro_context.regime_label if self.macro_context else None,
"macro_favourite_trap": self.macro_context.favourite_trap_risk if self.macro_context else None,
```

- **Guard:** ✅ Yes — ternary `if self.macro_context else None`
- **Probability impact:** No — these are read after `velo_prime_prob` is already computed.
- **Material:** Cosmetic — only affects output fields `macro_regime_label` and `favourite_trap_risk` in the API response / DB row. Scoring and ranking are unchanged.

---

### 3. Macro context fetch in `score_race_velo_prime()` — NO GUARD NEEDED (fail-safe)
**File:** `app/services/velo_prime_service.py`
**Lines:** 219–224

```python
try:
    macro_ctx = get_macro_context_for_race(race_date, code)
except Exception as e:
    log.warning("Macro context unavailable: %s", e)
    macro_ctx = None          # gracefully falls back to None
```

- **Guard:** N/A — `None` is the intentional fallback when the fetch fails. No `if macro_ctx:` check needed here.
- **Probability impact:** Indirect — `macro_ctx` is passed to `ensemble.predict_race()`, which propagates it to `VeloPrimePrediction.compute()`. If `None`, the material adjustments in `compute()` are skipped.

---

### 4. Output enrichment in `score_race_velo_prime()` — COSMETIC
**File:** `app/services/velo_prime_service.py`
**Lines:** 257–258

```python
row["macro_regime_label"]  = row.pop("macro_regime", None)
row["macro_chaos_mode"]    = (macro_ctx.chaos_mode if macro_ctx else False)
row["favourite_trap_risk"] = (macro_ctx.favourite_trap_risk if macro_ctx else "normal")
```

- **Guard:** ✅ Yes — ternary `macro_ctx if macro_ctx else ...`
- **Probability impact:** No — these are just surface reads into the already-computed prediction.
- **Material:** Cosmetic — only affects output fields. Values default to `False` / `"normal"` when `macro_ctx` is `None`.

---

## Behaviour When `macro_ctx` is `None`

| Scenario | `velo_prime_prob` change? | `verdict_flags` | `regime_override` | `macro_regime_label` | `macro_chaos_mode` | `favourite_trap_risk` |
|---|---|---|---|---|---|---|
| `compute()` with None | No (skipped) | No chaos/thin/fav flags added | Not set | N/A | N/A | N/A |
| `to_dict()` with None | N/A | unchanged | unchanged | `None` | N/A | `None` |
| Service output with None | N/A | unchanged | unchanged | `None` (from to_dict) | `False` | `"normal"` |

**Conclusion:** When macro context is unavailable, `velo_prime_prob` is computed from the weighted specialist scores only — none of the macro regime adjustments (`chaos_mode`, `favourite_trap_risk`, `field_size_regime`) are applied. The probability is not artificially inflated or defaulted; it simply lacks the regime-sensitive damping/compression. The output annotations (`verdict_flags`, `regime_override`) are the primary casualty of missing macro context, not the scores themselves (beyond the absent regime adjustments).

---

*Generated by NEXUS (nexus-q2 session) — 2026-03-23*
