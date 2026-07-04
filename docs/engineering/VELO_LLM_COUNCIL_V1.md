# VÉLØ LLM Council V1

> **The governance layer.** Reads the evidence, argues, verifies, and produces one controlled operator decision.
> **Rule One:** The council does not change live scoring directly. It recommends. The gates decide.

---

## 1. Overview

The VÉLØ LLM Council is a controlled multi-agent reasoning layer that sits above VÉLØ’s existing engine. It is not another sidecar; it is the boardroom that synthesizes all available evidence.

### Status: SHADOW / OPERATOR ONLY
- **NO** live scoring control.
- **NO** staking.
- **NO** live Betfair execution.
- **NO** automatic promotion.

---

## 2. Council Roles (v0.1)

### 1. PRIME CHAIR
- **Role:** Final synthesis, debate control, hallucination prevention, gate enforcement.
- **Input:** All council outputs, one truth file, current operating state.
- **Output:** Final operator read, decision classification, next action.

### 2. DATA AUDITOR
- **Role:** Data quality verification.
- **Checks:** Metadata completion, candidate gate, horse/trainer/jockey IDs, result availability, source conflicts.
- **Output:** PASS/FAIL, missing fields, do-not-trust warnings. **Veto power.**

### 3. RACING API CONNECTIONS ANALYST
- **Role:** analyzes trainer/jockey/course/distance strength using Racing API enrichment.
- **Output:** Connection strength, sample size warnings, shadow score.

### 4. CASHRUN ANALYST
- **Role:** Identifies trainer setup and handicap plots.
- **Input:** CASHRUN report (scripts/cashrun_detector.py output).
- **Output:** CASHRUN_READY, CASHRUN_WATCH, SUPPRESS.

### 5. MARKET ECONOMIST
- **Role:** Prevents backing overbet horses; identifies value.
- **Output:** Value classification (Value-positive, overbet-risk, suppress).

### 6. RED TEAM SKEPTIC
- **Role:** Attacks the recommendation, looks for overfitting and sample bias.
- **Output:** Objections, failure risk, do-not-trust reasons.

---

## 3. Evidence Packet

Every council run must be based on a single **Evidence Packet**. No packet, no council.

**Contains:**
- race metadata
- VP30 card
- SQPE / VP
- live sidecars (MDS, Improvement, etc.)
- Racing API enrichment
- CASHRUN report
- signal promotion board status
- router shadow audit
- execution bridge paper ledger
- result/audit history

---

## 4. Operational Commands

### Run Council
```bash
python scripts/run_velo_council.py --date YYYY-MM-DD
```

### Outputs
- `data/council_packets/council_packet_YYYY_MM_DD.json`
- `data/council_reports/velo_council_report_YYYY_MM_DD.md`
- `data/council_runs/velo_council_run_YYYY_MM_DD.json`

---

## 5. Safety Constraints

- No betting.
- No staking.
- No live Betfair.
- No changing VP weights.
- No changing router lanes.
- No automatic promotion.
- Council output is **SHADOW / OPERATOR ONLY**.

---

## 6. Daily Run Truth Duty

> Recovered from STASH-02 salvage review of stash@{4}; docs-only governance addition; no code change.

The council is not allowed to act as if "the system ran" unless the daily run-truth packet exists.

### Named ownership

#### DATA AUDITOR
- **Owns** the daily run-truth watchdog.
- Must run or review:
  - `python scripts/ops/velo_daily_run_truth_watchdog.py --date YYYY-MM-DD`
- Must classify the day as one of:
  - `AUTOMATED_RUN_OK`
  - `MANUAL_RECOVERY_ONLY`
  - `RUN_FAILED_NO_VERDICTS`
  - `FALSE_PASS_NO_VERDICTS`
  - `NO_SCORING_RUN`
  - `RUNNING_OR_STALLED`
  - `VERDICTS_WITHOUT_PIPELINE_TRUTH`
- Has veto power over operator trust if the truth packet is missing or degraded.

#### PRIME CHAIR
- **Owns escalation** when the watchdog is not `AUTOMATED_RUN_OK`.
- Must treat:
  - manual-only recovery,
  - missing local truth,
  - missing commit SHA,
  - and untracked Telegram delivery
as explicit governance defects, not background noise.

### Required packet

Every race day must have:
- `data/velo_daily_run_truth_YYYY_MM_DD.json`
- `data/velo_daily_run_truth_YYYY_MM_DD.md`

If those files do not exist, the council is not operating on proven truth.

### Five separate truths the council must keep distinct

- **Deploy truth**: what code was deployed
- **Cron truth**: whether the scheduled scorer actually fired
- **Supabase truth**: whether verdicts were written
- **Local truth**: whether the local verdict artifact hydrated
- **Telegram truth**: whether operator delivery was actually proven

These are separate facts. One does not imply the others.

### Hard rule

The council must not say "the day ran" unless at minimum:
- cron truth is proven or manual recovery is explicitly labeled
- Supabase verdict truth is present
- local truth is present or explicitly marked degraded

If Telegram delivery is not logged in the system of record, the council must mark it:
- `UNTRACKED_IN_SYSTEM_OF_RECORD`
