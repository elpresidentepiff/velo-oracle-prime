# Telegram Signal Attribution Live Preview V1

Display-only preview. Not sent to Telegram.
Note: A/B governed card previews use illustrative second-rank gap placeholders because the local verdict backup only stores the top pick.

## Preview A-card sample

```text
🛡️ *EPSOM 2:05 | VISION_ONLY*
──────────────────────────────────
PRIMARY:     Runman
TIER:        A
CONFIDENCE:  LOW
PROB GAP:    0.0700
MDS (DECOY): 0.5755
EXECUTION:   NO
VÉLØ SIGNAL STACK
PICK:        Runman
VP:          0.616
TIER:        A
LANES:
✅ VP30_TIER_A — n=162 | SR=40.1% | Frame=77.2% | SHADOW_CANDIDATE
🔥 MDS_HIGH — n=31 | SR=54.8% | Frame=96.8% | SHADOW_CANDIDATE
📈 IMPROVE_HIGH — n=62 | SR=43.5% | Frame=82.3% | SHADOW_CANDIDATE
🟡 PLACE_PROB_HIGH — n=392 | SR=31.6% | Frame=66.8% | WATCHLIST
SIDECAR:
MDS:         0.576
IMPROVE:     0.483
PLACE:       0.983
RISK FLAGS:
— none
STATUS:      SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
REASONS:     preview proof only, display-only patch
SOURCE:      preview
DATE:        2026-04-28
──────────────────────────────────

```

## Preview B-card sample

```text
🛡️ *EPSOM 3:15 | VISION_ONLY*
──────────────────────────────────
PRIMARY:     Dangerman
TIER:        B
CONFIDENCE:  LOW
PROB GAP:    0.0700
MDS (DECOY): 0.0155
EXECUTION:   NO
VÉLØ SIGNAL STACK
PICK:        Dangerman
VP:          0.257
TIER:        B
LANES:
⚠️ B_LOW_VP_SUPPRESS — n=272 | SR=16.9% | Frame=44.1% | SUPPRESS_CANDIDATE
SIDECAR:
MDS:         0.015
IMPROVE:     0.028
PLACE:       0.727
RISK FLAGS:
⚠️ VP_020_030_DRAG — 18.0% SR | 47.8% frame
STATUS:      SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
REASONS:     preview proof only, display-only patch
SOURCE:      preview
DATE:        2026-04-28
──────────────────────────────────

```

## Preview C-WATCH sample

```text
SOUTHWELL (AW) 2:20  Brother Dave
  prob 0.241 | gap 0.070 | place 0.704
  SIGNAL STACK: VP 0.241 | Tier C
  badges none
  sidecar MDS 0.014 | IMP 0.078 | PLACE 0.704
  risk ⚠️ VP_020_030_DRAG — 18.0% SR | 47.8% frame
  SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
  preview proof only
```
