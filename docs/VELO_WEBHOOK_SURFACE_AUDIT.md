# VÉLØ Webhook Surface Audit

**Revision:** 2026-04-18.01 | **Status:** VERIFIED FIXED

---

## 1. Audit Objective
To prove that the `/telegram/webhook` endpoint is exposed safely and handles malformed payloads without unintended internal behavior.

---

## 2. Findings: Webhook Resilience

| Test Case | Payload | Behavior | Result |
|---|---|---|---|
| **Malformed JSON** | `Invalid {` | Returns HTTP 200 (Silent Ignore) | **✓ PASS** |
| **Missing Message**| `{}` | Returns HTTP 200 (No side effect) | **✓ PASS** |
| **Missing User/Text**| `{"message": {}}` | Bails early, returns HTTP 200 | **✓ PASS** |
| **Command Logic** | `/start` | Triggers agent init + response | **✓ PASS** |

---

## 3. Implementation: Webhook Memory Guard
The previously identified "Unbounded Agent Memory" vulnerability has been addressed:
- **Bounded Store:** `_vox_agents` replaced with a bounded `OrderedDict` (LRU cache).
- **Eviction Policy:** Oldest inactive agent instances are evicted when the `MAX_VOX_AGENTS` limit (default 50) is reached.
- **Identity Gate:** Optional `WHITELISTED_TELEGRAM_USERS` env var added to restrict agent creation to authorized users only.

---

## 4. Verification Proof
End-to-end negative path testing performed on 2026-04-18 via `scripts/verify_webhook_memory_guard.py`.
- **Size Limit (Max 3):** ✓ PASS (Oldest evicted).
- **LRU Retention:** ✓ PASS (Recently used kept).
- **Identity Whitelist:** ✓ PASS (Unauthorized blocked).
