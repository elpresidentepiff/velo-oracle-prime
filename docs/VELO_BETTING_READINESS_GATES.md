# VÉLØ Betting Readiness Gates

**Status:** HARD LOCKED | **Last Updated:** 2026-04-19

No live capital is authorized until these gates are GREEN.

---

## 1. Governance Gates
- [x] **A-Tier Integrity:** Proven 60.3% win rate on sub-3.0 SP.
- [x] **Governance Schema Live:** `assigned_product`, `router_reasons`, `execution_allowed` columns applied to `velo_verdicts` (migration `20260419_001`). No more silent stripping.
- [x] **Pass Logic Defined:** Refined in `VELO_SELECTION_REFINEMENT_PLAN.md`.
- [ ] **Price Discovery (BSP):** CONDITIONAL lanes (FRAME_ONLY, EW_CANDIDATE) confirmed positive at BSP over 18–19 races each. Need 50+ BSP races per lane before live capital. BSP mandatory at routing time.
- [ ] **AW Decoy Policy:** Automated 0.85x penalty logic implemented and tested.
- [ ] **prob_gap Persistence:** `prob_gap` must be stored in verdict JSON and passed to router at live routing time.

## 2. Technical Gates
- [x] **Sigma Truth Spine:** 1,107 races reconciled and auditable.
- [x] **Doctrine Persistence:** Hardening confirmed for flag-bearing rows.
- [x] **ProductRouter Chain:** Scoring → routing → Supabase → Telegram chain complete and coherent.
- [ ] **BSP Feed Live:** Racing API BSP field populated at execution window (currently empty post-April 5).
- [ ] **Real-Time Handshake:** Verified WebSocket latency < 200ms for final 5m window.

## 3. Financial Gates
- [ ] **Lane Authorization:** FRAME_ONLY + EW_CANDIDATE reach 50+ BSP-confirmed races each.
- [ ] **WIN_ONLY (Odds-On):** Sub-2.0 SP sub-lane reaches 50+ BSP races with BE gap confirmed positive.
- [ ] **Staking Engine:** AAE Embodied Market (AEGIS) wiring complete.
- [ ] **Treasury Lock:** Zero-delta proof over 1,000 simulated trades.

---

## Lane Status Summary (2026-04-19)

| Lane | Status | Basis |
|---|---|---|
| WIN_ONLY (odds-on) | SHADOW_ONLY | 69% win, +0.02 above BE at SP. BSP subset biased. |
| WIN_ONLY (2.0–5.0) | BLOCKED | Structural loser at every SP band above 2.0. |
| FRAME_ONLY | CONDITIONAL | +11.2% ROI@BSP over 19 races. BSP required. |
| EW_CANDIDATE | CONDITIONAL | +23.2% ROI@BSP over 18 races. BSP required. |
| VISION_ONLY | BLOCKED | No edge. Monitor only. |
| PASS (C/D) | PERMANENTLY BLOCKED | — |

See `docs/VELO_BSP_COMMERCIAL_REPLAY.md` for full analysis.
