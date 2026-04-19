# VÉLØ Persistence Honesty Audit

**Revision:** 2026-04-18.01 | **Classification:** LYING SUCCESS PATH

---

## 1. Audit Objective
To determine if the VÉLØ system can report success via Telegram while failing to persist operational truth to the database (Supabase).

---

## 2. Findings: The Deception Loop
The audit of `scripts/run_prime_today.py` reveals a sequential but non-atomic relationship between persistence and notification:

1.  **Non-Blocking Persistence:** `persist_race_predictions()` is called for each race. If it returns `False`, the script logs the failure but continues execution.
2.  **Premature Broadcast:** Telegram "Decision Cards" (A-STRIKE/B-PLAYABLE) are broadcast *after* the persistence loop but *before* the final status check.
3.  **Lying Logic:** A race that fails to write to `velo_verdicts` will still have its "A-STRIKE" card sent to the operator. The operator receives a signal that has no corresponding record in the system of record.
4.  **Late-Stage Honesty:** The final "Persistence Report" and "Final Report" correctly reflect the failure status, but they arrive *after* the actionable signals have already been issued.

---

## 3. Impact
- **Forensic Breakdown:** If an operator bets on a Telegram signal that wasn't persisted, the Sigma Loop (nightly reconciliation) will have no verdict to reconcile against. The "Truth" is lost.
- **Operator False Confidence:** The system appears operational even when the database layer is failing.

---

## 4. Required Fix: Atomic Persistence Guard
The following structural change is required to move from "Lying" to "Honest":
- **Mutation:** Modify Step 5 in `run_prime_today.py` to only broadcast Decision Cards for races that have a confirmed `persist_ok` status.
- **Fail-Fast:** If persistence fails for an A-STRIKE race, an immediate "CRITICAL: PERSISTENCE FAILURE" alert must be sent *instead* of the decision card.
