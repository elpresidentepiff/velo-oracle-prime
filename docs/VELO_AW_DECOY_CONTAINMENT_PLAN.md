# VÉLØ AW Decoy Containment Plan
**Generated:** 2026-04-19 | **Source:** 167 decoy misses, MDS analysis  
**Status:** Defined. Not yet implemented.

---

## The Decoy Problem — Restated Precisely

The 167 market_decoy_followed misses at avg SP 4.80 are not all the same failure type.

**Critical finding from this audit:** MDS > 0.3 toward rank-1 produces 72.9% win rate. MDS < 0.10 produces 15.4%.

This means the organism already DETECTS the difference between:
- **Real steam (toward our pick):** market is backing our horse quietly → amplify
- **Fake steam (away from our pick):** market is being positioned elsewhere → suppress or review

The current pipeline does not separate these two directions. That is the fix.

---

## Two Types of Decoy Misses

### Type A: Our horse got decoyed away from
The market moved steam toward a DIFFERENT horse. We followed the steam (or got displaced by it). Our original pick (or rank-2) was the actual winner.

**Signature:** market_deception_score is high, but it's NOT toward our pick — it's toward a competing horse.
**Fix:** When MDS is high AND it's directional toward a horse other than rank-1 → flag as potential decoy → surface rank-2 for review → do not auto-select rank-1.

### Type B: Our horse had genuine intent steam
The market backed our horse quietly (steam toward our pick). We correctly identified the horse. The market was right to back it.

**Signature:** MDS > 0.3 AND direction toward rank-1.
**Fix:** AMPLIFY. This is the 72.9% win rate finding. Do not suppress.

---

## Current MDS Usage — The Error

The model computes `market_deception_score` at the race level, not directionally per horse. This means:
- A race with genuine steam toward our pick scores the same as a race with fake steam
- Both currently trigger the same underpowered caution response
- The 72.9% signal is being diluted by the lower-strike races

---

## Containment Policy

### Step 1: Directional MDS Split (implement in scoring pipeline)

Add a field `mds_direction` to the verdict output:
- `toward_rank1` — the deception signal aligns with our pick
- `away_from_rank1` — the deception signal is toward a different horse
- `ambiguous` — cannot determine direction

**Source of direction:** Look at `market_deception_score` values per horse in `full_analysis`. If the rank-1 horse has the highest individual market_deception_score → `toward_rank1`. If a different horse has it → `away_from_rank1`.

---

### Step 2: MDS Gate at Selection

| MDS condition | Action |
|--------------|--------|
| MDS > 0.3, direction `toward_rank1` | **PRIORITY SELECT** — 72.9% win rate |
| MDS > 0.3, direction `away_from_rank1` | **FLAG DECOY** — review rank-2, consider pass |
| MDS > 0.3, direction `ambiguous` | **REVIEW** — surface rank-2 for operator review |
| MDS 0.1–0.3, any direction | Standard selection gate |
| MDS < 0.10 | No MDS signal — use other gates |

---

### Step 3: AW-Specific Threshold

AW tracks have structurally higher decoy rates (Wolverhampton 16.2%, Lingfield: high, Newcastle: high). On AW surfaces, apply a lower MDS threshold for review:

| Track type | MDS review threshold |
|-----------|---------------------|
| AW (Wolverhampton, Lingfield, Newcastle, Kempton, Dundalk) | > 0.2 triggers review |
| Turf (GB) | > 0.3 triggers review |
| NH (jumps) | > 0.25 triggers review (NH less common but not immune) |

---

### Step 4: Day-Level Decoy Flag

From the forensic data, decoy misses cluster on specific dates:
- 2026-03-26: 24 decoy misses
- 2026-03-27: 22 decoy misses

**Episodic decoy activity is a real pattern.** When ≥ 4 decoy signals fire on the same racing card, apply blanket decoy elevation: treat all selections on that card as review-required regardless of MDS value.

---

## AW Track Policy

| Track | Decoy rate | Policy |
|-------|-----------|--------|
| Wolverhampton (AW) | 16.2% | Select with MDS directional check mandatory |
| Lingfield (AW) | High (no exact %) | MDS directional check mandatory |
| Newcastle (AW) | High | MDS directional check mandatory |
| Kempton (AW) | 8.6% | Standard AW policy |
| Southwell | 15.4% | Apply AW threshold |
| Dundalk (IRE, AW) | Unknown | Apply AW threshold |

**Key:** AW does NOT mean avoid. AW win rate is 22.2% — above organism average. AW means apply the directional MDS check before selecting.

---

## What the Fix Is NOT

- Not "avoid all AW races" — that would remove 22.2% win rate racing
- Not "always back rank-2 on AW" — rank-2 simulation showed -45.4% ROI on AW decoy
- Not "suppress all high-MDS races" — MDS toward rank-1 at >0.3 is the strongest win signal

The fix is precision: separate direction, apply threshold, make the decision on each race individually.

---

## Expected Impact

If directional MDS is implemented:

| Change | Expected effect |
|--------|----------------|
| MDS toward rank-1 promoted | Captures 72.9% win rate lane |
| MDS toward other horse flagged | Prevents 30%+ of decoy misses |
| AW threshold applied | Reduces decoy rate from 19.3% to estimated <10% |
| Day-level flag applied | Catches episodic cluster days |
| Net: decoy miss count | Estimated reduction from 167 to 80–100 |

This does not guarantee positive ROI — it removes contamination so the real signal can work.
