# RAILWAY DECOMMISSION — APPROVAL PACKET

**Date:** 2026-06-10 · Nothing executed. Each row needs the operator's explicit dashboard action or written approval. Backups noted where state exists.

| # | Item | Type | Category | Reason / evidence | Risk if disabled | Rollback | Approve |
|---|---|---|---|---|---|---|---|
| 1 | `smoke-prod.yml` schedule | GH cron (every 30 min) | **A — safe to disable now** | 48 failures/day probing a 502 corpse | none — it only reports failure | re-enable schedule in file | ☐ |
| 2 | `score-daily.yml` schedule | GH cron (2×/day) | A — disable until Railway revived | fires triggers into 502; manual chain is the real path | none today (triggers already fail) | re-enable when endpoint lives | ☐ |
| 3 | `enchanting-exploration` | Railway service | A/B — disable, then delete after backup | documented duplicate of velo-oracle against same DB | none if truly duplicate — **confirm in dashboard it serves nothing** | Railway restore/redeploy | ☐ |
| 4 | `hermes-agent` | Railway service + volume | **E — manual review FIRST** | holds service-role Supabase key + Telegram token; purpose not in this repo (podcast/media agent?). Could be writing | unknown — could break media side | export volume before any change | ☐ |
| 5 | `velo-oracle` | Railway service | D — keep until replacement; **fix or park** | 502 dead; either redeploy healthy or park and adopt manual-first/GH-runner topology | losing the future API/dashboard host | redeploy from repo | ☐ |
| 6 | `velo-prime-scoring` | Railway service | D — tie to cron decision | the intended scoring cron host; dormant | none today (manual is the path) | redeploy | ☐ |
| 7 | `ingestion-spine` | Railway service | B — archive after backup | Racing-API-era PDF worker; CI's only test target | PDF parsing capability loss (PDFs now parsed locally) | redeploy from workers/ | ☐ |
| 8 | `RACING_API_*` env vars (all services) | env | A | dead source, law-forbidden live | none | re-add | ☐ |
| 9 | 25 empty Supabase tables (keep `market_snapshots`+`odds_snapshots` for BSP) | schema | B — archive list | never written; schema noise | none (empty) | recreate from migrations | ☐ |
| 10 | `betting_ledger` (1,050 rows) | data review | E — confirm SIM-era provenance | "no live staking" law — rows must be explained, then either archived or labelled SIM | n/a (review only) | n/a | ☐ |
| 11 | Secret rotation set (service-role, DB URL, Telegram, OpenRouter) | security | **F — rotation recommended** | plaintext local dumps existed; not in git | brief downtime while rotating | new keys | ☐ |
| 12 | Local dump files deletion (after #11) | file | F | remove plaintext at rest | none post-rotation | n/a | ☐ |

**Order:** 11 → 1 → 2 → 4(review) → 3 → 12 → 5/6 decision with cron strategy → 7 → 8 → 9/10.
**Must keep for Race Day 11 (tomorrow):** nothing on Railway — the entire June 11 chain runs from the operator box. That fact is itself the strongest evidence for the lean topology.
