# 2026-04-08 — SQPE Bridge Update

## Status

Bridge built and tested. Extended shadow mode updated.

---

## What Was Done

### 1. SQPE Bridge Module
**File:** `src/v13/racing_analogs/sqpe_bridge.py` (NEW)

Contains:
- `SQPEBandSource` enum: `live_sqpe_v17_prob`, `live_velo_prime_prob`, `historical_proxy`, `unknown`
- `LiveSQPERecord`: extracts and derives live SQPE signals from velo_verdicts
- `LiveSQPEBridge`: batch extraction from verdict rows
- Signal quality assessment and disagreement detection

### 2. Extended Shadow Updated
**File:** `src/v13/racing_analogs/extended_shadow.py` (updated)

Changes:
- `_build_comparison()` now uses `velo_prime_prob` as the live SQPE signal
- `ShadowComparison` now includes `sqpe_source` field
- `to_dict()` includes `sqpe_source` tag in output
- `persist()` writes `sqpe_source` to Supabase

---

## Exact Field Used

**Field:** `velo_prime_prob` from `velo_verdicts.full_analysis[runner]`

**Source tag:** `sqpe_source = "live_ensemble_prob"`

**Why velo_prime_prob (not sqpe_v17_prob):**

| Field | Range | Band Distribution | Discrimination |
|---|---|---|---|
| sqpe_v17_prob | 0.005–0.065 | 100% very_low | NONE — isotonic calibration flattens to win probability |
| velo_prime_prob | 0.005–0.372 | 97.6% very_low, 2.4% low | YES — ensemble adds market + trainer signals |
| Historical proxy | 0.001–0.800 | 99.8% very_low | Partial |

**Conclusion:** `sqpe_v17_prob` is the isotonic-calibrated ML probability. It is compressed to near-zero values for ALL runners (3.29% calibrated win probability for a top horse). It cannot differentiate. `velo_prime_prob` is the full ensemble output and IS what VÉLØ actually ranks on — it has real discrimination.

---

## What sqpe_v17_prob Actually Is

The Phase 3.5 SQPE engine computes a raw A/E-like score internally:

```
raw_sqpe = trainer_ae × base_rate × form_modifier × days_modifier
```

This gets isotonic-calibrated to a well-calibrated win probability:

```
sqpe_v17_prob = isotonic_calibrated(raw_sqpe)  # → 0.03-0.06 range
```

The calibration step is what flattens the signal. This is intentional for the ensemble (calibrated probabilities are better for weighted combination), but it destroys the A/E-like discrimination that the analog layer needs.

The `velo_prime_prob` restores discrimination by adding back non-SQPE signals (market deception, place probability, improvement score) at ensemble weights of 0.45 + 0.10 + 0.08 + ...

---

## Bridge Test Result

**Test:** 10 live races, 110 runners, 171K historical states indexed

```
sqpe_source distribution: {'live_ensemble_prob': 110}  ← 100% tagged

Agreement distribution:
  AGREE:       77 (70.0%)   ← vs 65.0% previously
  DISAGREE:    10 (9.1%)    ← vs 9.7% previously
  UNCERTAIN:   23 (20.9%)   ← vs 25.2% previously
```

**Change from previous run:** Agreement increased from 65% → 70% because `velo_prime_prob` is a richer signal than the proxy. Disagreement rate stays similar (~9-10%).

**Sample tagged output:**
```
Nancee Spain | velo_p=0.2074 velo_sqpe=0.2074 | ana_sqpe=0.0202 | live_ensemble_prob | DISAGREE
Harry's Legacy | velo_p=0.1335 velo_sqpe=0.1335 | ana_sqpe=0.0202 | live_ensemble_prob | UNCERTAIN
```

**Key:** `velo_sqpe=0.2074` now shows the full ensemble probability, not the compressed sqpe_v17. This is honest — `sqpe_source=live_ensemble_prob` means "this is the ensemble probability, not raw SQPE."

---

## Live VÉLØ Status

**UNTOUCHED.** No modification to velo_prime_ensemble.py, no change to live verdict generation. The bridge reads from the existing velo_verdicts table only. No production writes.

---

## Persistence Extension — Mapped (Not Implemented)

**Minimal safe change to persist raw Phase 3.5 SQPE:**

1. **Where raw SQPE is computed:** `intelligence/sqpe.py` → `_MLCore.predict_proba()` → returns calibrated probability. The raw uncalibrated score is in `_model.predict_proba()` (pre-calibration). This is an internal numpy array, not persisted.

2. **Where verdict rows are assembled:** `velo_prime_ensemble.py` → `VeloPrimePrediction.to_dict()` (line ~207). This assembles the runner dict that gets appended to `full_analysis` and written to Supabase.

3. **Proposed additive field:** Add `sqpe_v17_raw_score` to the runner dict in `to_dict()`. Pass the pre-calibration raw model output at the point where `self.sqpe_v17_prob` is set (line ~141 in velo_prime_ensemble.py).

4. **Risk:** LOW. Additive field only. No existing field modified. Backward compatible — sidecar reads `sqpe_v17_raw_score` if present, falls back to `sqpe_v17_prob` if not.

5. **Files that would change:** `intelligence/velo_prime_ensemble.py` (additive only), `src/v13/racing_analogs/canonical_mapper.py` (read new field), `src/v13/racing_analogs/schema.py` (add field to CanonicalRaceState).

**This is a separate engineering task — not implemented yet.**

---

## Recommendation

### Current bridge: SUFFICIENT for extended shadow mode

The `velo_prime_prob` signal gives the sidecar real discrimination:
- VÉLØ top-ranked horses: velo_prime 0.20–0.37
- Other horses: velo_prime 0.03–0.12
- This is what produces the 70% AGREE / 9% DISAGREE / 21% UNCERTAIN split

The `sqpe_source=live_ensemble_prob` tag makes the signal origin explicit. The sidecar is no longer comparing proxy SQPE against a mystery signal — it's comparing historical market-shaped memory against the VÉLØ ensemble output.

### Raw SQPE persistence: WORTH DOING but not urgent

If the sidecar needs to distinguish "SQPE signal strength" from "ensemble signal strength," add `sqpe_v17_raw_score` as an additive field. But for the current purpose of extended shadow mode, `velo_prime_prob` with honest tagging is sufficient.

---

## Files Changed

| File | Change |
|---|---|
| `src/v13/racing_analogs/sqpe_bridge.py` | NEW — live SQPE bridge module |
| `src/v13/racing_analogs/extended_shadow.py` | UPDATED — uses velo_prime_prob as live SQPE signal, sqpe_source tag |
| `docs/agent_handoffs/2026-04-08_sqpe_bridge_update.md` | NEW — this file |

---

## Handover Classification

- Live system status: **UNTOUCHED**
- Sidecar status: **OPERATIONAL** with live_ensemble_prob bridge
- sqpe_source tags: **WORKING** — 100% of live runners tagged correctly
- Promotion status: **NOT APPROVED** — still advisory only
- Next blocker: **NONE** — bridge is complete and tested

---

## Exact Next Step

1. Schedule `extended_shadow.py` as a cron job (every 2h on race days)
2. Run extended shadow mode daily and accumulate agreement/disagreement statistics
3. After 2-4 weeks of shadow data: evaluate whether disagreement cases correlate with VÉLØ accuracy
4. Only then decide if raw SQPE persistence is needed

**No further architecture changes required for extended shadow mode to operate.**
