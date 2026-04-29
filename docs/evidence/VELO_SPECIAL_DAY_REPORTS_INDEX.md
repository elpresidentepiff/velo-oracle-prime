# VÉLØ Special Day Reports Index

Special Day Reports are generated for days that produce notable evidence —
strong performance, notable weakness, unusual signal behaviour, or days
that materially advance or retreat the router ledger.

---

## Reports

| Date | Title | SR | Frame | Key Finding | File |
|---|---|---|---|---|---|
| 2026-04-28 | High-Confidence Frame Strength, Mid-Price Winner Weakness | 15.4% | 61.5% | VP≥0.30 frame=81.8%; B-tier drag; mid-price winner class dominant | `special_days/VELO_SPECIAL_DAY_2026-04-28.md` |

---

## How To Generate A Special Day Report

```bash
source venv/bin/activate && PYTHONPATH=. python scripts/generate_special_day_report.py --date YYYY-MM-DD
```

Output paths:
- `docs/evidence/special_days/VELO_SPECIAL_DAY_YYYY-MM-DD.md`
- `data/evidence_vault/special_days/velo_special_day_YYYY-MM-DD.json`

Add the new report to this index after generation.

---

## When To Generate A Special Day Report

- Days where SR > 25% or SR < 10% (outlier performance)
- Days where VP≥0.30 frame rate > 85% or < 60%
- Days where a router lane gains 3+ qualifying results
- Days where a new sidecar signal fires strongly
- Days declared as noteworthy by the operator
