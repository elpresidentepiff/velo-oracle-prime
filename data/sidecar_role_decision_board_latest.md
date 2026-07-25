# Sidecar Role Decision Board

- Generated: `2026-06-22T20:05:14.832600Z`
- Ablation source: `live_sidecar_ablation_audit_latest.json` (loaded: True)
- SQPE source: `sqpe_alone_control_audit_latest.json` (loaded: True)
- SQPE-only ROI: `0.0726` | SR: `0.1922`

## Decision Board

| Sidecar | Live Weight | Ablation | Ablation ROI | SQPE Cls | Recommended Role |
|---|---:|---|---:|---|---|
| improvement_score | 0.12 | OVERBET_RISK | -0.1757 | SIDECAR_BADGE_ONLY | **BADGE_ONLY_CANDIDATE** |
| release_day_prob | 0.00 | HOLD | -0.0711 | NO_DATA | **SHADOW_ONLY** |
| market_deception_score | 0.10 | OVERBET_RISK | -0.1001 | SIDECAR_HELPS_FRAME | **LIVE_WEIGHT_REDUCE_CANDIDATE** |
| place_prob | 0.08 | OVERBET_RISK | -0.0606 | SIDECAR_HELPS_FRAME | **BADGE_ONLY_CANDIDATE** |
| comment_intel_score | 0.00 | HOLD | -0.0711 | NO_DATA | **SHADOW_ONLY** |
| longshot_score | 0.07 | OVERBET_RISK | -0.1514 | SIDECAR_FREEZE_CANDIDATE | **BADGE_ONLY_CANDIDATE** |
| Racing_API_enrichment | 0.00 | NO_DATA | — | NO_DATA | **SHADOW_ONLY** |
| CASHRUN | 0.00 | NO_DATA | — | NO_DATA | **SHADOW_ONLY** |

### improvement_score

- **Recommended role:** `BADGE_ONLY_CANDIDATE`
- **Current live weight:** `0.12`
- **Evidence status:** `MULTI_SIGNAL`
- **Ablation classification:** `OVERBET_RISK`
- **Ablation n (matched high):** `274`
- **Ablation SR/Frame/ROI:** `0.3285 / 0.6496 / -0.1757`
- **SQPE control classification:** `SIDECAR_BADGE_ONLY`
- **Reason:** SR improves at high values (ablation: OVERBET_RISK, ROI negative). Ablation 2026-04-04 shows it hurts top-1. Weight=0.12 declared but disabled in ensemble. Evidence: improvement_score>0.40 SR=43.5% — may work as operator badge, not probability weight.
- **Next gate:** Maintain at DISABLED in _DISABLED_COMPONENTS. Re-enable only if retrained model shows positive ROI
- *Notes:* Disabled from ensemble by _DISABLED_COMPONENTS but weight declared as 0.12

### release_day_prob

- **Recommended role:** `SHADOW_ONLY`
- **Current live weight:** `0.00`
- **Evidence status:** `ABLATION_ONLY`
- **Ablation classification:** `HOLD`
- **Ablation n (matched high):** `1087`
- **Ablation SR/Frame/ROI:** `0.23 / 0.5299 / -0.0711`
- **SQPE control classification:** `NO_DATA`
- **Reason:** Weight=0.00 confirmed. Disabled from live ensemble. Required features not wired.
- **Next gate:** Wire required features, then run ablation audit with n>=50 before reconsideration
- *Notes:* Weight=0.00 confirmed, disabled from live ensemble

### market_deception_score

- **Recommended role:** `LIVE_WEIGHT_REDUCE_CANDIDATE`
- **Current live weight:** `0.10`
- **Evidence status:** `MULTI_SIGNAL`
- **Ablation classification:** `OVERBET_RISK`
- **Ablation n (matched high):** `284`
- **Ablation SR/Frame/ROI:** `0.412 / 0.7606 / -0.1001`
- **SQPE control classification:** `SIDECAR_HELPS_FRAME`
- **Reason:** Live weight=0.10. Ablation=OVERBET_RISK (SR=0.412, ROI=-0.1001). CRITICAL: MDS>0.5 is highest-lift signal SR=54.8%. Risk is in ensemble weight not signal itself. Recommended: keep in ensemble at reduced weight, maintain as operator badge at MDS>0.5.
- **Next gate:** Build n>=50 prospective results at MDS>0.5 threshold before weight change
- *Notes:* Live weighted. Highest-lift signal in system (SR=54.8% at MDS>0.5)

### place_prob

- **Recommended role:** `BADGE_ONLY_CANDIDATE`
- **Current live weight:** `0.08`
- **Evidence status:** `MULTI_SIGNAL`
- **Ablation classification:** `OVERBET_RISK`
- **Ablation n (matched high):** `286`
- **Ablation SR/Frame/ROI:** `0.3706 / 0.7587 / -0.0606`
- **SQPE control classification:** `SIDECAR_HELPS_FRAME`
- **Reason:** Live weight=0.08. Ablation=OVERBET_RISK (SR=0.3706, ROI=-0.0606). Frame improves but ROI is negative. place_prob>0.80 SR=31.6% in unified audit. Best used as operator coverage badge, not ensemble weight.
- **Next gate:** Monitor at n>=100. If ROI remains negative, reclassify to FRAME_SUPPORT_BADGE
- *Notes:* Live weighted. place_prob>0.80 SR=31.6% (SQPE evidence)

### comment_intel_score

- **Recommended role:** `SHADOW_ONLY`
- **Current live weight:** `0.00`
- **Evidence status:** `ABLATION_ONLY`
- **Ablation classification:** `HOLD`
- **Ablation n (matched high):** `1087`
- **Ablation SR/Frame/ROI:** `0.23 / 0.5299 / -0.0711`
- **SQPE control classification:** `NO_DATA`
- **Reason:** Weight=0.00 confirmed. Disabled from live ensemble. Required features not wired.
- **Next gate:** Wire required features, then run ablation audit with n>=50 before reconsideration
- *Notes:* Weight=0.00 confirmed, disabled from live ensemble

### longshot_score

- **Recommended role:** `BADGE_ONLY_CANDIDATE`
- **Current live weight:** `0.07`
- **Evidence status:** `MULTI_SIGNAL`
- **Ablation classification:** `OVERBET_RISK`
- **Ablation n (matched high):** `278`
- **Ablation SR/Frame/ROI:** `0.3237 / 0.6547 / -0.1514`
- **SQPE control classification:** `SIDECAR_FREEZE_CANDIDATE`
- **Reason:** Live weight=0.07. Ablation=OVERBET_RISK (SR=0.3237, ROI=-0.1514). Only fires at SP>=10 — small n. Frame may improve but ROI negative.
- **Next gate:** Isolate to SP>=10 candidates only. Monitor at n>=30 in that band.
- *Notes:* Live weighted. Only fires at SP>=10.

### Racing_API_enrichment

- **Recommended role:** `SHADOW_ONLY`
- **Current live weight:** `0.00`
- **Evidence status:** `NO_EVIDENCE`
- **Ablation classification:** `NO_DATA`
- **Ablation n (matched high):** `0`
- **Ablation SR/Frame/ROI:** `None / None / None`
- **SQPE control classification:** `NO_DATA`
- **Reason:** No live weight. Operator/shadow visibility only. No evidence gate cleared.
- **Next gate:** Build prospective sample before any promotion discussion
- *Notes:* Shadow/operator only. No live weight. Connection/course/distance scores.

### CASHRUN

- **Recommended role:** `SHADOW_ONLY`
- **Current live weight:** `0.00`
- **Evidence status:** `NO_EVIDENCE`
- **Ablation classification:** `NO_DATA`
- **Ablation n (matched high):** `0`
- **Ablation SR/Frame/ROI:** `None / None / None`
- **SQPE control classification:** `NO_DATA`
- **Reason:** No live weight. Operator/shadow visibility only. No evidence gate cleared.
- **Next gate:** Build prospective sample before any promotion discussion
- *Notes:* Pending. Not yet wired. RPDC cash_run_flag — insufficient sample.

## Role Summary

| Role | Count |
|---|---|
| BADGE_ONLY_CANDIDATE | 3 |
| LIVE_WEIGHT_REDUCE_CANDIDATE | 1 |
| SHADOW_ONLY | 4 |

## Role Definitions

- **LIVE_WEIGHT_KEEP** — Live-weighted, value positive — keep as-is
- **LIVE_WEIGHT_REDUCE_CANDIDATE** — Live but shrink weight — pending audit gate
- **BADGE_ONLY_CANDIDATE** — Remove from probability weighting; keep as operator flag
- **FRAME_SUPPORT_BADGE** — Helps frame/coverage but not value — badge only
- **SUPPRESS_BADGE** — Negative signal for suppressing short-priced horses
- **SHADOW_ONLY** — Not ready for live use — shadow / operator visibility only
- **FREEZE_CANDIDATE** — Actively hurts — freeze weight at 0

---
*Audit only. No weight changes applied. All recommendations require operator review and evidence gate passage.*
