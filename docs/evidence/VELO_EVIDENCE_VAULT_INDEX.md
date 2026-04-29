# VÉLØ Evidence Vault Index

**Vault initialized:** 2026-04-28
**Baseline commit:** 06ba74b (Router Evidence Engine)
**Evidence Audit commit:** 0cfbbed (Unified Evidence Audit V1)
**Vault commit:** see git log

This vault is the canonical, investor-grade, audit-grade evidence archive for VÉLØ Oracle Prime.
It is committed to Git and never overwritten — new versions are added alongside old ones.

---

## Vault Contents

### Master Audit Artifacts

| File | Description | Date |
|---|---|---|
| `data/evidence_vault/velo_unified_evidence_audit_v1.json` | Machine-readable master truth (49 days, all signals) | 2026-04-28 |
| `data/evidence_vault/velo_unified_evidence_audit_v1.md` | Human-readable audit report | 2026-04-28 |
| `data/evidence_vault/velo_unified_evidence_audit_v1_metrics.csv` | Signal rankings table | 2026-04-28 |

### Evidence Documents

| File | Description |
|---|---|
| `docs/evidence/VELO_EVIDENCE_VAULT_INDEX.md` | This file — vault index |
| `docs/evidence/VELO_SIGNAL_RANKINGS_V1.md` | Full signal ranking table with evidence basis |
| `docs/evidence/VELO_OPERATING_TRUTH_BOARD_V1.md` | What works, what doesn't, what to suppress |
| `docs/evidence/VELO_COMPANY_EVIDENCE_BRIEF_V1.md` | Investor/partner-facing evidence summary |
| `docs/evidence/VELO_EVIDENCE_ARCHIVE_PROTOCOL.md` | How evidence is archived and versioned |
| `docs/evidence/VELO_SPECIAL_DAY_REPORTS_INDEX.md` | Index of all special day reports |

### Special Day Reports

| Report | Date | SR | Frame | Key Finding |
|---|---|---|---|---|
| `special_days/VELO_SPECIAL_DAY_2026-04-28.md` | 2026-04-28 | 15.4% | 61.5% | VP≥0.30 frame strength vs mid-price winner weakness |

### Company Documents

| File | Description |
|---|---|
| `docs/company/VELO_COMPANY_MASTER_PLAN_V1.md` | Phased company roadmap |
| `docs/company/VELO_WEBSITE_APP_MVP_SPEC_V1.md` | Product MVP specification |
| `docs/company/VELO_WHITEPAPER_OUTLINE_V1.md` | Whitepaper structure |
| `docs/company/VELO_FUNDING_PACK_OUTLINE_V1.md` | Funding pack requirements |

---

## Core Evidence Numbers (49-day read, last updated 2026-04-28)

- **Global SR:** 20.6% (baseline 20%)
- **Global Frame:** 48.4% (target 70%+)
- **VP ≥ 0.30 + Tier A:** SR=40.1%, Frame=77.2%, n=162 — **PROVEN**
- **Market deception score >0.5:** SR=54.8%, Frame=96.8%, n=31 — **PROVEN**
- **Improvement score >0.40:** SR=43.5%, Frame=82.3%, n=62 — **PROVEN**
- **Primary miss class:** SP 3.0–8.5 zone = 58% of all misses

---

## Versioning Protocol

When a new Unified Evidence Audit runs:
1. Save as `velo_unified_evidence_audit_v2.json/md/csv` (increment version)
2. Add row to Special Day Reports Index
3. Update Operating Truth Board if rankings change
4. Do NOT overwrite v1 files

When a modification changes signal rankings:
1. Create new `VELO_SIGNAL_RANKINGS_V2.md`
2. Reference both from this index
3. Commit with descriptive message

---

*VÉLØ Oracle Prime — Evidence Vault V1*
*This vault is the foundation for the whitepaper, audit dossier, and funding pack.*
