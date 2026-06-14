# VFU-01 Build Plan

**Status**: PHASE 1 ACTIVE
**Created**: 2026-06-14
**Owner**: VÉLØ Forensics Unit

---

## Current Phase: Phase 1 — Doctrine + Schema + Inventory

**Status**: COMPLETE (this document marks Phase 1 closure)

Deliverables:
- `docs/current/VELO_FORENSICS_UNIT_V1.md` ✓
- `docs/current/VFU_RACE_AUTOPSY_SCHEMA_V1.md` ✓
- `docs/current/HORSE_PASSPORT_FORENSIC_EXTENSION_V1.md` ✓
- `docs/current/PATTERN_PROSECUTOR_SCHEMA_V1.md` ✓
- `docs/current/VFU_FAILURE_TAXONOMY_V1.md` ✓
- `data/reports/vfu_01_build_plan.md` ✓
- `data/reports/vfu_01_build_plan.json` ✓

Guardrails confirmed:
- Horse Passport is canonical — no rival dossier system created ✓
- VFU is investigative feeder ✓
- No autopsy execution ✓
- No Supabase writes ✓
- No live scoring change ✓
- No model promotion ✓
- No Telegram send ✓
- No Racing API restoration ✓
- No Mar–Apr extraction ✓

---

## Phase 2 — Autopsy Generator Dry-Run

**Status**: LOCKED — awaits operator approval after Phase 1 acceptance

Scope:
- Select 20 current-era races from sigma results (May 08–Jun 13)
- Mix: 5 WIN, 5 PLACED, 10 MISS
- Mix: GREEN days, AMBER days, include Jun 09 FALSE_GREEN day
- Generate autopsy JSON for each under `data/reports/vfu_autopsies/`
- NO Supabase writes
- NO passport mutations
- Report: 20-race autopsy summary with failure class distribution

Unlock condition: Operator explicit approval after reviewing Phase 1 schemas.

---

## Phase 3 — Horse Passport Forensic Extension Dry-Run

**Status**: LOCKED — awaits Phase 2 completion

Scope:
- Identify horses appearing 2+ times in current-era sigma universe
- Generate forensic extension records for those horses
- Test merge logic between base Passport and forensic extension
- Write to `data/reports/vfu_passport_extensions/` only
- NO mutation of `data/new_build/passports/horse_passports_v1.jsonl`

Unlock condition: Phase 2 complete, autopsy quality reviewed, operator approval.

---

## Phase 4 — Full Current-Era Autopsy Pass

**Status**: LOCKED — awaits Phase 3 completion

Scope:
- Full 1,263-row current-era union autopsy (May 08–Jun 13)
- All race types, all courses, all VP bands
- Failure class distribution report
- Horses appearing 5+ times: full forensic passport extension
- Pattern Prosecutor candidates flagged

Unlock condition: Phase 3 complete, passport merge validated, operator approval.

---

## Phase 5 — Pattern Prosecutor Summary Report

**Status**: LOCKED — awaits Phase 4 completion

Scope:
- First prosecution run across Phase 4 autopsy output
- Minimum sample patterns (n>=20) tested
- Report: ACCUMULATING / CONFIRMED / REJECTED per pattern
- No doctrine changes without operator approval

Unlock condition: Phase 4 complete, operator approval.

---

## Phase 6 — Mar–Apr Pre-Surgery Study

**Status**: LOCKED — separate from VFU phases

Unlock condition:
- 14-day VP Gatekeeper dry-run validation complete (from 2026-06-14)
- Operator explicit approval
- NOT dependent on VFU phases

Reference: `data/reports/pre_surgery_sigma_study_plan.md`

---

## Hard Rules — Permanent

| Rule | Status |
|---|---|
| Horse Passport is canonical | PERMANENT |
| No duplicate dossier system | PERMANENT |
| No autopsy execution before Phase 2 unlock | ENFORCED |
| No Supabase writes before operator approval | ENFORCED |
| No live scoring changes | PERMANENT |
| No model promotion | PERMANENT |
| No Telegram send | PERMANENT |
| No Racing API restoration | PERMANENT |
| No Mar–Apr extraction before 14-day VP validation | ENFORCED |
