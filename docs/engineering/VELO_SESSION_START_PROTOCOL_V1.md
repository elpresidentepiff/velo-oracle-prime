# VÉLØ SESSION START PROTOCOL (V1)
**Author:** Manus AI | **Status:** RATIFIED | **Date:** May 28, 2026 | **Version:** 1.0.0

---

## 1. Objective
To prevent cognitive drift, factual erosion, and unauthorized system modifications during long, multi-turn AI agent execution sessions. Every development, audit, or operational session must start with the execution of this protocol. No commands may be run and no files may be modified until this protocol has been completed and verified.

---

## 2. Mandatory Session-Start Checklist

The agent must execute the following 10 steps at the beginning of the session, outputting the results as a structured markdown table.

### Checklist Steps:
1. **Branch/Head:** Verify the current active git branch and HEAD commit SHA.
2. **Current Date:** Establish the current operational date.
3. **Live Formula:** Identify the active scoring formula version (e.g., VÉLØ Prime v1).
4. **Active Gates:** List all currently active execution gates.
5. **Degraded Dates:** Identify any dates marked as degraded or incomplete.
6. **Learning Blocks:** Identify any dates where learning is strictly blocked.
7. **Open Council Items:** List any pending or un-ratified Council items.
8. **Next Safe Command:** Define the exact next safe terminal command to execute.
9. **No-Go Rules:** Re-state active operational restrictions.
10. **Worktree Status:** Check for uncommitted or dirty files in the worktree.

---

## 3. Session Start Template

The agent must populate and output this exact table format before taking any other action:

| Metric / Check | Value / Status | Verification Command / Source |
|---|---|---|
| **1. Branch / HEAD** | `main` (`a33c5bd`) | `git rev-parse --abbrev-ref HEAD && git rev-parse --short HEAD` |
| **2. Operational Date**| `2026-05-28` | System clock check |
| **3. Live Formula** | `VÉLØ Prime v1` | `run_prime_today.py` import inspection |
| **4. Active Gates** | `Gate 2 (Flatline), Gate 5 (RPDC), Gate 6 (Learning)` | `src/velo/feature_audit.py` inspection |
| **5. Degraded Dates** | `2026-05-20` (RP_MERGED fallback used) | `data/velo_daily_run_truth_*.md` inspection |
| **6. Learning Blocks** | `2026-05-20` (degraded features) | `data/nightly_eod_learning_status_*.json` |
| **7. Open Council Items**| None | `docs/council/` inspection |
| **8. Next Safe Command**| `python scripts/ops/run_prime_today.py --dry-run` | Operator instruction |
| **9. No-Go Rules** | `No live scoring/weight/model/staking changes` | `CLAUDE.md` / Doctrine |
| **10. Worktree Status**| `Clean` | `git status --porcelain` |

---

## 4. Session Handoff & Compaction Protocol

When the token context window approaches limit, or when handing off execution to a new agent session, the current agent must output a **Handoff Packet** using the following schema:

```json
{
  "session_id": "velo_session_20260528_1779",
  "last_commit_sha": "a33c5bd99153c4e6abc8cd31283aa5d46bcbaa22",
  "dirty_files": [],
  "current_phase": "Harness Specification Complete",
  "active_degradation_warnings": [
    "RP_FEATURE_FLATLINE on Ayr 2.42"
  ],
  "learning_eligibility": {
    "blocked_dates": ["2026-05-20"],
    "reason": "Feature degradation on RP_MERGED source"
  },
  "next_safe_step": "Implement automated recovery loop tests"
}
```

This handoff packet must be appended to `data/velo_session_handoff_history.jsonl` and output in the final message of the session.
