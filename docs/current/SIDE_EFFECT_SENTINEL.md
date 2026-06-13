# VÉLØ Side-Effect Sentinel

**Date:** 2026-06-11
**Status:** ACTIVE
**Classification:** RUNTIME_SAFETY

## 1. Purpose

The Side-Effect Sentinel is a runtime safety gate that audits and blocks commands likely to cause external side effects (Supabase writes, Telegram messages, model promotions, or live scoring mutations). It ensures that exploratory, audit, or research tasks never accidentally touch production systems.

## 2. Enforced Boundaries

The Sentinel monitors and blocks the following:

- **Supabase Writes:** Blocks commands containing `supabase insert`, `supabase upsert`, `rpc write`, etc.
- **Telegram Messaging:** Blocks commands containing `telegram send`, `bot.send_message`, etc.
- **Model Promotion:** Blocks commands containing `promote_model`, `registry promote`, etc.
- **Live Scoring:** Blocks commands containing `live_scoring`, `run_engine_full`, `score_race`, etc.
- **Dangerous Environment Flags:** Blocks execution if `VELO_ALLOW_SUPABASE_WRITES=true` (or similar) is present in the environment without explicit authorization.

## 3. Explicit Safety States

The runner reports one of the following states:

- `SIDE_EFFECT_SAFE`: Audit passed; command has no detected production risks.
- `SIDE_EFFECT_FORBIDDEN_COMMAND`: Command contains a blocked high-risk pattern.
- `SIDE_EFFECT_FORBIDDEN_ENV`: Environment contains dangerous "allow" flags.
- `SIDE_EFFECT_SUPABASE_WRITE_RISK`: Specific risk of unauthorized database mutation.
- `SIDE_EFFECT_TELEGRAM_SEND_RISK`: Specific risk of unauthorized message transmission.
- `SIDE_EFFECT_MODEL_PROMOTION_RISK`: Specific risk of unauthorized model registry changes.
- `SIDE_EFFECT_LIVE_SCORING_RISK`: Specific risk of unauthorized live scoring execution.
- `SIDE_EFFECT_COMMAND_BLOCKED`: Safety check failed; command was not executed.
- `SIDE_EFFECT_COMMAND_OK`: Safety check passed and command returned exit code 0.
- `SIDE_EFFECT_COMMAND_FAILED`: Safety check passed but command returned non-zero.

## 4. Usage

### Audit Mode
Verify if a command is safe to run:
```bash
python scripts/ops/side_effect_sentinel.py --mode audit -- pytest tests/test_task_contract_runner.py
```

### Run Mode (Safe-only)
Run a command only if the Sentinel determines it is safe:
```bash
python scripts/ops/side_effect_sentinel.py --mode run -- pytest tests/test_capture_proof.py
```

## 5. Artifacts

The Sentinel always writes its final state to:
`data/current/side_effect_sentinel_latest.json`

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*
