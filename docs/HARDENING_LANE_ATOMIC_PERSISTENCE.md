# Hardening Lane: Atomic Persistence Guard

**Status:** High Priority Post-Release | **Owner:** VÉLØ Engineering

---

## 1. The Goal
Eliminate the "Lying Success Path" identified in the Persistence Honesty Audit. Ensure that every signal broadcast to Telegram is backed by a successful write to the System of Record (Supabase).

---

## 2. Mandatory Logic Rule
**Persist First, Then Broadcast.**

A Telegram Decision Card (A-STRIKE / B-PLAYABLE) must **never** be sent unless the `persist_race_predictions()` function for that specific race has returned a `True` (Success) response.

---

## 3. Implementation Plan
1.  **Modify `scripts/run_prime_today.py`:**
    *   Update the scoring/persistence loop to track the success of individual race writes in a temporary mapping (e.g., `race_id -> persist_status`).
2.  **Gate the Telegram Loop:**
    *   Before calling `tg(card)` for any race, verify its `persist_status` in the mapping.
3.  **Handle Failures:**
    *   If a race is A-STRIKE but `persist_status` is `False`, do NOT send the card.
    *   Instead, send a **CRITICAL SYSTEM ALERT**: "Persistence failed for [Course] [OffTime]. Signal suppressed to protect truth loop."
4.  **Verification:**
    *   Test by manually inducing a Supabase write failure (e.g., temporarily changing the table name) and confirming that Telegram correctly suppresses the signals and sends the alert instead.

---

## 4. Success Criteria
- [ ] No "A-STRIKE" cards are sent for races that fail to write to `velo_verdicts`.
- [ ] Every successful Telegram broadcast has a matching, queryable row in Supabase.
- [ ] System loudly announces persistence failures at the race level.
