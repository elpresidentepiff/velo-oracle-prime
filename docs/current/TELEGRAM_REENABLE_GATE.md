# TELEGRAM RE-ENABLE GATE — LOOP 11

**Effective:** 2026-06-10 · Current status: **`TELEGRAM_DISABLED`** · No Telegram picks are sent. Period.

## Statuses
`TELEGRAM_DISABLED` → `TELEGRAM_READY_PENDING_OPERATOR` → (operator approves) → enabled → `TELEGRAM_SENT_VERIFIED` per send.
Blocking states: `TELEGRAM_BLOCKED_DEGRADED`, `TELEGRAM_BLOCKED_SOURCE_UNKNOWN`.

## Re-enable conditions — ALL must be true, on the same day
1. ONE_TRUTH law active (it is, `fa97c2a`).
2. Mission Control truth fix live (it is, `bc28e2f`).
3. **RPDC integrity = `RPDC_OK` on a new clean day** (checker: `check_rpdc_integrity.py`; June 10 = PERSIST_GAP, June 9 = UNKNOWN/attach failure — neither qualifies).
4. **Supabase persistence proof = PASS** for that day (`prove_supabase_persistence.py` exit 0).
5. Feature-health packet exists and reads CLEAN (observability `source_truth: RP_MERGED_CLEAN`, no flatline).
6. `source_truth` known — never UNKNOWN.
7. No degraded day labelled clean anywhere in the previous 7 days (Mission Control history check).
8. No learning contamination flags for the day.
9. **Operator approves, explicitly, in writing.**

## Mechanics on re-enable
- Remove `--no-notify` only for the approved scope (sigma report first; scoring alerts as a second, separate approval).
- The Sigma Telegram format is LOCKED — re-enabling must not alter it.
- Every send must land in `data/telegram_delivery_truth_{date}.json` with sent/failed counts; suppressed sends must be recorded as SUPPRESSED, never silently skipped.
- One failed-delivery day (events > 0, sent = 0, notify enabled) re-triggers `TELEGRAM_DISABLED` pending investigation.

## Why it is disabled today
The truth boundary was unreliable: Mission Control could call degraded clean (fixed), RPDC persistence was corrupted for 7 weeks (fixed forward, history unrepaired), and June 9/10 both fail the integrity conditions. Publishing picks from a chain that cannot prove itself is how trust dies. The chain proves itself first; then it speaks.
