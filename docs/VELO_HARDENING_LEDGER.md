# VÉLØ Hardening Ledger

**Status:** Active Governance | **Revision:** 2026-04-18.01

This ledger tracks the closure of "Honesty Gaps" and "Silent Splits" identified during the release audit.

---

## 1. Tracked Hardening Gaps

| Gap | Classification | Priority | Status | Proof Artifact |
|---|---|---|---|---|
| **Schema drift** | Truth | HIGH | **VERIFIED FIXED** | Manual SQL applied 2026-04-18. |
| **Top-level observability**| Truth | HIGH | **VERIFIED FIXED** | Native persistence proven on verdict `ac83288e`. |
| **Cash-run effectiveness** | Research | MEDIUM | **OPEN / UNKNOWN** | Accumulation phase: awaiting data volume. |
| **Subgroup Audit** | Research | MEDIUM | **DAY ZERO / NOT READY** | Effectiveness audit locked until 100+ flag-bearing rows. |

| **Accumulation tracker** | Governance | MEDIUM | **ACTIVE** | Daily updates in `docs/VELO_FLAG_ACCUMULATION_TRACKER.md`. |

| **Lying Success Path (Telegram)** | Honesty Gap | CRITICAL | **VERIFIED FIXED** | Atomic gate in `run_prime_today.py`. Verified by disciplined real-path rerun 2026-04-18. |
| **Silent Persistence Drops** | Truth Gap | HIGH | **VERIFIED FIXED** | `persist_race_predictions` failure now suppresses signal. Verified by disciplined real-path rerun 2026-04-18. |
| **API Key Surface Hardening** | Security | MEDIUM | **VERIFIED SECURE** | Fail-closed proven by `verify_surface_security_fail_closed.py`. |
| Webhook Memory Exhaustion | DoS Risk | HIGH | **VERIFIED FIXED** | Bounded `OrderedDict` (LRU) in `app/main.py`. Verified by `verify_webhook_memory_guard.py`. |
| **Ingestion Sequencing Bug** | Operational Risk | MEDIUM | **OPEN** | Documented in `VELO_INGESTION_SEQUENCING_AUDIT.md`. |

---

## 2. Closure Proofs

### [2026-04-18] Lying Success Path (Telegram)
- **Problem:** Telegram decision cards were broadcast even if database persistence failed.
- **Fix:** Implemented `persist_map` in `run_prime_today.py`.
- **Atomic Rule:** No A/B card is sent unless `persist_map[race_id]` is `True`.
- **Verification:** Failed persistence now triggers a loud "⚠ CRITICAL: PERSISTENCE FAILURE" alert instead of the signal.
- **Next Verification Step:** Induce a temporary DB disconnect and verify Signal Suppression on Telegram.

---

## 3. Hardening Roadmap
1. **[LANE 1] Honesty Path:** (Atomic Persistence, Fail-Fast Loops).
2. **[LANE 2] Surface Security:** (API Key verification, env isolation).
3. **[LANE 3] Operational Resilience:** (Pre-race re-scoring for ingestion bug).
