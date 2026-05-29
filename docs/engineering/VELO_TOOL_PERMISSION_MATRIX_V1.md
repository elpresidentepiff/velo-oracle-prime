# VÉLØ TOOL PERMISSION MATRIX (V1)
**Author:** Manus AI | **Status:** RATIFIED | **Date:** May 28, 2026 | **Version:** 1.0.0

---

## 1. Introduction
To prevent autonomous AI agents from making unapproved modifications to live scoring algorithms, production databases, or execution pipelines, this matrix defines strict permission levels and boundaries for all tool uses. 

---

## 2. Permission Levels

We define 7 strict permission levels:

1. **READ_ONLY:** Allowed to read files, view directory structures, and inspect logs. No write or execute capabilities.
2. **DOCS_ONLY:** Allowed to write and modify Markdown files under `docs/` and `reports/`. No code changes.
3. **AUDIT_ONLY:** Allowed to run read-only scripts (e.g., preflight, feature audits, database checks). No state mutation.
4. **LOCAL_ARTIFACT_ONLY:** Allowed to write local JSON/CSV logs or snapshots. No remote writes or database inserts.
5. **SUPABASE_WRITE_APPROVAL_REQUIRED:** Allowed to write to Supabase tables *only* after explicit operator confirmation.
6. **LIVE_STATE_BLOCKED:** Strictly forbidden from mutating active trading states, balances, or live API configurations.
7. **MODEL_PROMOTION_BLOCKED:** Strictly forbidden from changing active model weights, scoring formulas, or staging branches.

---

## 3. Tool Mapping Matrix

The following matrix maps specific agent actions and tools to their required permission levels and restrictions.

| Tool / Action | Permission Level | Allowed Operations | Forbidden Operations |
|---|---|---|---|
| **Reading Files** | `READ_ONLY` | Inspecting `.py`, `.md`, `.json`, `.csv` files. | Accessing unencrypted private keys or env files. |
| **Writing Docs** | `DOCS_ONLY` | Creating/editing `.md` files in `docs/` or `reports/`. | Editing Python code files or configurations. |
| **Running Audits**| `AUDIT_ONLY` | Running `preflight.py`, `feature_audit.py`, `pytest`. | Mutating state, modifying databases, or running tests with side effects. |
| **Local Artifacts**| `LOCAL_ARTIFACT_ONLY` | Writing local `.json`, `.csv` logs in `data/` or `predictions/`. | Writing to shared system volumes or modifying Git configurations. |
| **Telegram Alerts**| `LOCAL_ARTIFACT_ONLY` | Sending pre-formatted alert messages to Telegram. | Triggering arbitrary alerts, spamming, or changing chat IDs. |
| **Supabase Writes**| `SUPABASE_WRITE_APPROVAL` | Inserting/updating rows with verified `git_commit_sha`. | Deleting tables, altering schemas, disabling RLS, or updating live states. |
| **Scoring Changes**| `MODEL_PROMOTION_BLOCKED`| Reading weights, comparing formulas. | Modifying `score_race_velo_prime()`, changing live coefficients. |
| **Staking / Router**| `LIVE_STATE_BLOCKED` | Inspecting decision-tier rules. | Modifying `product_router.py`, changing stake limits. |
| **Learning Engine**| `MODEL_PROMOTION_BLOCKED`| Auditing backtests, inspecting retraining logs. | Running automatic model retraining or promoting new model weights. |
| **Live State** | `LIVE_STATE_BLOCKED` | Viewing dashboard, checking health. | Changing live system variables, credentials, or stopping servers. |

---

## 4. Enforcement and Guardrails

1. **Preflight Enforcement:** The `preflight.py` module must automatically verify that the execution environment complies with these boundaries before permitting pipeline execution [1].
2. **Commit Gate:** Any modification to code files (`.py`) during a `DOCS_ONLY` or `READ_ONLY` session must trigger an immediate commit block and hard-fail the session.
3. **Database Guardrails:** Database connections used during audits must utilize a restricted-privilege role rather than the `service_role` key to programmatically prevent write operations.

---

## References
* [1] `src/preflight.py` - VÉLØ Preflight Gate check constraints and env verification.
