# VELO Signal Rankings V1

**Evidence basis:** 49 race days | 1391 sigma rows | 1604 verdicts  
**Last updated:** 2026-04-29  
**Audit source:** `data/evidence_vault/velo_unified_evidence_audit_v1.json`

Signal ranks are derived from live closed-result data only.  
ETCSLV note: these ranks describe the live **Tool Registry** of trusted, risky, or still-unproven VELO behaviors.

---

## PROVEN_SIGNAL

### VP30_TIER_A

- **n:** 162
- **SR:** 40.1%
- **Frame:** 77.2%
- **Meaning:** first proven trust boundary
- **ETCSLV role:** candidate-lane seed and operator badge

### VP >= 0.40

- **n:** 100
- **SR:** 44.0%
- **Frame:** 85.0%
- **Meaning:** strongest VP band

### MDS_HIGH

- **n:** 31
- **SR:** 54.8%
- **Frame:** 96.8%
- **Meaning:** polarity-flip discovery
- **ETCSLV role:** highest-upside Tool Registry discovery

### IMPROVE_HIGH

- **n:** 62
- **SR:** 43.5%
- **Frame:** 82.3%
- **Meaning:** strong underused sidecar
- **ETCSLV role:** should remain visible in the operator interface

---

## PROMISING_SIGNAL

### VP >= 0.30

- **n:** 345
- **SR:** 32.2%
- **Frame:** 69.3%

### PLACE_PROB_HIGH

- **n:** 392
- **SR:** 31.6%
- **Frame:** 66.8%
- **Meaning:** large-sample positive sidecar

---

## WATCHLIST_SIGNAL

### Tier B VP >= 0.30

- **n:** 130
- **SR:** 30.0%
- **Frame:** 62.3%

### V1_BASE

- **n:** 27
- **SR:** 37.0%
- **Frame:** 85.2%
- **ROI:** +11.5%

### V2_CLASS4_ONLY

- **n:** 17
- **SR:** 41.2%
- **Frame:** 82.4%
- **ROI:** +30.2%

---

## SUPPRESS_SIGNAL

### B_LOW_VP_SUPPRESS

- **n:** 272
- **SR:** 16.9%
- **Frame:** 44.1%
- **Meaning:** confirmed drag
- **ETCSLV role:** live-warning badge, not a promotion candidate

---

## FORENSICS_ONLY

### MID_PRICE_ZONE_WATCH

- **Miss count:** 352
- **Share of misses:** 58%
- **Meaning:** main winner-conversion battlefield
- **ETCSLV role:** research and operator watch note, not predictive promotion

---

## INSUFFICIENT_SAMPLE

### V6_GOLD_SEAM

- **n:** 5
- **SR:** 60.0%
- **Frame:** 100.0%

### Playbook G V3 core

- **Status:** offline research candidate only

---

## ETCSLV Reading

- **Tool Registry:** VP30_TIER_A, MDS_HIGH, IMPROVE_HIGH, PLACE_PROB_HIGH, B_LOW_VP_SUPPRESS, MID_PRICE_ZONE_WATCH
- **Life Cycle Hooks:** candidate lanes, watchlists, suppressions, and freeze gates determine what can advance
- **Verification Interface:** Signal Stack and evidence reports expose the rankings to humans

---

*VELO Signal Rankings V1*

---

> Recovered from STASH-02 salvage review of stash@{6}; docs-only strategic/evidence material; no code change.
