# COLD STORAGE & JUNK QUARANTINE PLAN

**Date:** 2026-06-10 · Nothing deleted/moved yet. Manifest-first; each group gets one reversible commit after approval.

| Group | Size | Status | Action | Approval |
|---|---|---|---|---|
| `data/racing_post_account_raw/` | **8.3G** | parsed downstream; archive-grade | compress per-day to `tar.zst` (~10:1) → cold dir/external drive; keep last 14 days hot | ☐ |
| `data/racing_post_racecards_raw/` | 207M | same class | same | ☐ |
| `data/browser_profiles/` | 403M | one live session needed | keep newest profile; archive rest | ☐ |
| `models/{tie_v9,sqpe_v14,overlay_v5,longshot_v6}` | 0 bytes | empty dirs; docs claim they exist | delete dirs + fix CLAUDE.md claims | ☐ |
| `velo_memory.db` | 1 race/17 runners | vestigial | archive | ☐ |
| `training_data/synthetic_dataset_v1.json` | 1.3M | toy data | archive | ☐ |
| `scripts/data/velo_unified_evidence_corpus_v1.csv` | header-only | dead placeholder | archive | ☐ |
| `hackathon/ presentation*/ moltbook/ feast_repo/ mlruns/` | ~12M | side-quests | archive wholesale | ☐ |
| `data/racing_api_raw/` | 23M | dead source | archive per Racing API audit | ☐ |
| `tmp/ incoming/ quarantine/app` | ~2M | scratch | sweep after review | ☐ |
| `railway_*_env.txt` | 284K | secret-risk | DELETE after rotation (packet F) | ☐ |
| KEEP HOT | — | parsed layer, racecard_merged, results, features/, new_build training, models live+shadow, raceform parquets | no action | — |

**Rules:** manifest in the commit message per group · `git mv`/tar only, no `rm` without its own approved line · raw HTML is never deleted, only compressed/cold-stored.
