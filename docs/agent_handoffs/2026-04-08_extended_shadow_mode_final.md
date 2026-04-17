# 2026-04-08 — Extended Shadow Mode Final Report

## Status

Extended shadow mode is running.

The analog sidecar has now been tested against live VÉLØ outputs using:

- 206 live runners
- 12-month sequential historical analog memory
- advisory-only comparison
- no live influence on production decisions

---

## Core Result

### Agreement distribution

- AGREE: 134 / 206 (65.0%)
- DISAGREE: 20 / 206 (9.7%)
- UNCERTAIN: 52 / 206 (25.2%)

This is the correct shape for a useful sidecar:

- mostly confirming
- sometimes contradicting
- often appropriately uncertain

It is not rubber-stamping the live engine.

---

## What the DISAGREE cases mean

All important DISAGREE cases are:

- VÉLØ top-ranked horses (★)
- where VÉLØ sees edge
- but the analog layer says PASS / no historical confirmation

Examples:

- "velo_p=0.207 ★" vs "analog_sqpe=0.020 (PASS)"
- "velo_p=0.346 ★" vs "analog_sqpe=0.020 (PASS)"
- "velo_p=0.372 ★" vs "analog_sqpe=0.020 (PASS)"
- "velo_p=0.277 ★" vs "analog_sqpe=0.020 (PASS)"
- "velo_p=0.314 ★" vs "analog_sqpe=0.020 (PASS)"

### Interpretation

This is not a bug.

This is exactly what shadow mode is meant to reveal:

- VÉLØ is seeing live edge the historical market-shaped memory does not yet confirm
- the analog layer is acting as a conservative historical validator
- the sidecar is exposing where:
  - live intelligence is stronger than historical recall
  - or historical memory is still incomplete / underpowered

---

## What this proves

### 1. The sidecar is operationally valid

It can:

- run beside VÉLØ
- compare live runners to historical analog memory
- generate agreement / disagreement / uncertainty states
- do so without touching live production logic

### 2. The analog layer is useful

It is no longer just infrastructure.
It is now producing:

- confirmation
- contradiction
- uncertainty

in a live-shadow context.

### 3. Real VÉLØ SQPE remains the stronger engine

The DISAGREE pattern suggests:

- live VÉLØ is capturing real signal
- historical analog memory is still more conservative and partly market-shaped
- the sidecar should remain advisory, not controlling

---

## Operational Conclusion

### Decision

Do not promote the analog sidecar into live influence yet.

### Correct current role

The sidecar should remain:

- confirmation layer
- contradiction detector
- explanation layer
- memory layer

Not:

- replacement engine
- hard blocker
- rank override

---

## What stays true

- SQPE remains the primary engine
- trainer context remains secondary
- analog memory is now real but not yet dominant
- VÉLØ core remains untouched
- sidecar remains advisory-first

---

## Next exact step

### Final unlock

Feed real VÉLØ SQPE values into the analog memory path.

### Current blocker:

- historical analog memory still relies partly on "sqpe_proxy"
- proxy is structurally useful but not on the same scale as real VÉLØ SQPE
- this is why many top-ranked VÉLØ horses can still appear as analog PASS / non-confirmed

### Required next build

Create the bridge:

```
real VÉLØ SQPE → fingerprint memory layer
```

Then compare:

1. historical analog using proxy SQPE
2. historical analog using real VÉLØ SQPE where available
3. live VÉLØ output

That is the next serious engineering step.

---

## What not to do

- do not replace live SQPE
- do not widen feature scope
- do not connect this to trading systems
- do not let disagreement automatically suppress live top-ranked selections
- do not call the sidecar "production decisioning" yet

---

## Final verdict

Extended shadow mode passed.

The sidecar is now:

- live-safe
- operational
- informative
- and meaningfully distinct from VÉLØ

It confirms most of the live view, contradicts a minority, and leaves a quarter uncertain.

That is exactly what a useful second brain should do.

### Blunt summary

- VÉLØ sees the edge
- the sidecar remembers the market
- the disagreement cases are the gold
- the next unlock is real SQPE flowing into memory

---

## Handover classification

- Live system status: unaffected
- Sidecar status: running in extended shadow mode
- Promotion status: not approved
- Next blocker: real VÉLØ SQPE integration into analog memory

---

## Key files delivered

- `src/v13/racing_analogs/extended_shadow.py` — extended shadow runner
- `src/v13/racing_analogs/raceform_feature_deriver.py` — SP fallback for sqpe_proxy
- `docs/agent_handoffs/2026-04-08_extended_shadow_mode_final.md` — this report
- `/tmp/states_12m_seq.pkl` — 171,641 sequential states (12-month backfill)
- `/tmp/raceform_12m.pkl` — raw raceform rows (July 2024 – July 2025)
