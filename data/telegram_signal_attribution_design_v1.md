# VÉLØ Telegram Signal Attribution Panel Design V1

**Created:** 2026-04-29 00:43 UTC
**Status:** DESIGN ONLY — not yet in production

---

## The Operator Visibility Problem

Current Telegram output shows: horse name, VP score, tier, and a narrative summary. It does NOT surface candidate lane badges, sidecar signal values, or suppress warnings. The operator cannot distinguish a VP=0.38/Tier A/MDS=0.71 pick from a VP=0.38/Tier A/MDS=0.10 pick.

**Gap severity:** HIGH

> On 2026-04-28, MARKET_DECEPTION_HIGH would have fired on a subset of picks. The operator received the standard Telegram output with no indication of MDS elevation. A 54.8% SR signal was invisible at the operator layer.

**Fix required:** Add the VÉLØ SIGNAL STACK panel near the top of each race report. This does not change predictions. It surfaces what the engine already knows.

---

## Panel Design: VÉLØ SIGNAL STACK

**Panel name:** VÉLØ SIGNAL STACK
**Position:** top of each race prediction block in Telegram
**Display logic:** Always show VP, Tier, Router status, and operator note. Show lane badges, sidecar values, and warnings only when relevant.

---

## Panel Fields

| Field | Label | Source | Required |
|---|---|---|---|
| `pick` | Pick | velo_verdicts.top.horse | ✅ |
| `velo_prime_prob` | VP | velo_verdicts.velo_prime_prob | ✅ |
| `decision_tier` | Tier | velo_verdicts.decision_tier | ✅ |
| `lane_badges` | Candidate Lanes | computed from candidate lane conditions | — |
| `sidecar_values` | Sidecar | velo_verdicts.market_deception_score, improvement_score, place_prob | — |
| `suppress_warnings` | Suppress Warnings | decision_tier + velo_prime_prob | — |
| `forensics_warnings` | Risk Flags | computed from SP zone and tier | — |
| `router_status` | Router | router_shadow_audit_latest.csv | ✅ |
| `operator_note` | Status | hardcoded constant | ✅ |

---

## Badge Logic

| # | Badge | Condition | Evidence | Priority |
|---|---|---|---|---|
| 1 | 🔥 MDS_HIGH | `market_deception_score > 0.50` | n=31 | SR 54.8% | Frame 96.8% | 1 |
| 2 | ✅ VP30_TIER_A | `velo_prime_prob >= 0.30 AND decision_tier == 'A'` | n=162 | SR 40.1% | Frame 77.2% | 2 |
| 3 | 📈 IMPROVE_HIGH | `improvement_score > 0.40` | n=62 | SR 43.5% | Frame 82.3% | 3 |
| 4 | 🟡 PLACE_HIGH | `place_prob > 0.80` | n=392 | SR 31.6% | Frame 66.8% | 4 |
| 5 | ⚠️ B_LOW_VP | `decision_tier == 'B' AND velo_prime_prob < 0.30` | n=272 | SR 16.9% | Frame 44.1% — below baseline | 5 |
| 6 | 🔬 MID_PRICE_RISK | `opponent_sp_range_3_to_8.5_possible` | 352 misses = 58% of all misses in SP 3.0–8.5 zone | 6 |

---

## Sidecar Display Thresholds

| Signal | Show if | Elite/Strong if | Format |
|---|---|---|---|
| market_deception_score | > 0.4 | > 0.5 | `MDS={value:.2f}` |
| improvement_score | > 0.3 | > 0.4 | `Improve={value:.2f}` |
| place_prob | > 0.7 | > 0.8 | `PlaceProb={value:.2f}` |
| rpdc_release_score | > 0.5 | > — | `RPDC={value:.2f}` |

---

## Example Panels

### Elite multi-signal race — MDS + VP30_TIER_A + IMPROVE

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.42 | Tier: A

Candidate Lanes:
🔥 MDS_HIGH — elite shadow signal
   n=31 | SR 54.8% | Frame 96.8%
✅ VP30_TIER_A — proven shadow signal
   n=162 | SR 40.1% | Frame 77.2%
📈 IMPROVE_HIGH — proven shadow signal
   n=62 | SR 43.5% | Frame 82.3%

Sidecar: MDS=0.63 ⚡ ELITE | Improve=0.47 ↑ STRONG | PlaceProb=0.84 📍 HIGH

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Single proven signal — VP30_TIER_A only

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.33 | Tier: A

Candidate Lanes:
✅ VP30_TIER_A — proven shadow signal
   n=162 | SR 40.1% | Frame 77.2%

Sidecar: MDS=0.31 | Improve=0.28 | PlaceProb=0.76

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Suppress warning — Tier B VP<0.30 drag zone

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.24 | Tier: B

Candidate Lanes:
⚠️ B_LOW_VP — suppress candidate
   n=272 | SR 16.9% | Frame 44.1% — DRAG ZONE

Sidecar: MDS=0.18 | Improve=0.15 | PlaceProb=0.61

⚠️ RISK: Tier B + VP<0.30 — confirmed drag zone
   Suppress candidate. Historical SR well below baseline.

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### MDS elite signal — maximum interest

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.38 | Tier: A

Candidate Lanes:
🔥 MDS_HIGH — ELITE SHADOW SIGNAL
   n=31 | SR 54.8% | Frame 96.8%
   ⚡ Highest-lift signal in system. n=31 — discipline required.
✅ VP30_TIER_A — proven shadow signal
   n=162 | SR 40.1% | Frame 77.2%

Sidecar: MDS=0.71 ⚡ ELITE | Improve=0.22 | PlaceProb=0.81 📍 HIGH

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

*MDS > 0.70 should include the n=31 caution note explicitly.*

---

## Production Integration Path

**File to modify:** `scripts/run_prime_today.py (Telegram output section)`
**Function:** `format_telegram_message() or equivalent`
**Requires operator approval:** True
**Status:** DESIGN_ONLY — production integration NOT yet approved
**Next step:** Operator reviews this design doc, approves panel format, then integration is built

---

## Hard Rules

- The panel is informational only. It does not change the prediction or decision.
- The SHADOW EVIDENCE ONLY note must always appear — never remove it.
- No badge implies staking approval. Badges are shadow evidence signals only.
- MDS_HIGH badge must always include the n=31 caution note when n is still below 75.
- B_LOW_VP warning must always include the SR=16.9% figure.
- Panel content must be derived from velo_verdicts and candidate lane design — no recalculation.

---
*VÉLØ Telegram Signal Attribution Panel Design V1 | 2026-04-29 00:43 UTC*