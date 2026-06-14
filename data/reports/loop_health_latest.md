# Loop Health — latest

Generated 2026-06-10T22:14:34.025950+00:00 · date context 2026-06-10 · READ-ONLY

| Loop | Status | Detail / next fix |
|---|---|---|
| L1 Source Truth Loop | LOOP_PARTIAL | Pre-scoring PDF-intel coverage check (stage 6b) + write data/current/source_truth_latest.json |
| L2 Feature Health Loop | LOOP_PARTIAL | Standalone feature_health_latest.json packet with improvement_score variance check |
| L3 RPDC Integrity Loop | LOOP_FAILING | rpdc integrity status=RPDC_PERSIST_GAP |
| L4 Persistence Proof Loop | LOOP_FAILING | persistence proof status=FAIL |
| L5 Mission Control Truth Loop | LOOP_OK | mc source_truth=RP_MERGED_DEGRADED |
| L6 Race Day Execution Loop | LOOP_NOT_IMPLEMENTED | Build dry-run-only skeleton (live mode raises RuntimeError) after operator approval |
| L7 Sigma Loop | LOOP_PARTIAL | Four-status day classifier (CLOSED_CLEAN/CLOSED_DEGRADED/INCOMPLETE/BLOCKED) + sigma_status_latest.json |
| L8 Learning Admission Loop | LOOP_PARTIAL | Read-only checker script + learning runner refuses to start without PASS artifacts |
| L9 Testing and CI Loop | LOOP_PARTIAL | daily-chain-contract.yml CI workflow (MC tests, RPDC boundary tests, proof offline mode, Racing-API-not-live check) |
| L10 Docs Truth Loop | LOOP_PARTIAL | Operator-approved archive sweep per DOCS_CONSOLIDATION_MAP.md |
| L11 Telegram / Media Gate Loop | LOOP_BLOCKED_OPERATOR | Stays TELEGRAM_DISABLED until gate conditions PASS and operator approves |
| L12 Performance / Money Truth Loop | LOOP_PARTIAL | Repair paper-ledger ID chain (results cannot close); clean-day-only sigma series; named public benchmark via build_industry_comparison.py |

**Blocking learning:** L1, L2, L3, L4, L7, L8
**Blocking Telegram:** L1, L2, L4, L6, L11
**Blocking clean public claims:** L1, L2, L3, L4, L7, L12