# VÉLØ Session State — 2026-03-15
**Saved before context compaction**

---

## Production Status: FIXED AND DEPLOYED

Three bugs fixed, committed `2490218`, pushed to `origin/main`, Railway auto-deploy triggered.

| Bug | Fix | Status |
|---|---|---|
| Parser import crash (importlib hack) | Direct import from `ingestion_spine._parsers_base` | LIVE |
| Runner duplication ×10 (2,756→265 rows) | `conflict_keys=["race_id","horse_id"]` + UNIQUE constraint | LIVE |
| Stacked in_progress runs | `check_already_running()` guard in `run_pipeline()` | LIVE |

---

## Data Assets — Training Corpus

| File | Size | Rows | Content | In Git? |
|---|---|---|---|---|
| `data/backtest_50k.csv` | 19MB | 50,000 | UK/FR/IRE May-Aug 2015, labeled | NO (gitignored) |
| `data/backtest_50k_clean.csv` | 20MB | 49,996 | Cleaned version of above | NO |
| `data/raw_races_2024_2025.txt` | 69MB | 147,768 | JSON-lines, Jan 2024-Jul 2025 | YES |
| `data/train_5k.csv` | 1.8MB | 5,000 | Small subset | NO |
| `data/train_sample.csv` | 5.3MB | 15,000 | Sample subset | NO |
| `out/features_v11_train.parquet` | 292KB | ? | Pre-engineered features v11 | YES |
| `training_data/synthetic_dataset_v1.json` | 1.4MB | synthetic | Synthetic | YES |

**UK/IRE filter from raw_races_2024_2025.txt**: ~58,741 rows
**Top courses**: Wolverhampton AW (9,249), Newcastle AW (7,489), Southwell AW (7,080), Kempton AW (6,249)

**CSV columns**: `date, course, race_id, off, race_name, type, class, pattern, rating_band, age_band, sex_rest, dist, going, ran, num, pos, draw, ovr_btn, btn, horse, age, sex, wgt, hg, time, sp, jockey, trainer, prize, or, rpr, ts, sire, dam, damsire, owner, comment`

**User also mentioned 650MB of data** — likely local, not yet in repo. Location unknown. May need to ask.

---

## Existing Models

| Model | File | Size | Status |
|---|---|---|---|
| SQPE v15 | `models/sqpe_v15/sqpe_v15.pkl` | 409KB | LIVE — generating verdicts |
| SQPE v1_real | `models/v1_real/sqpe/sqpe_model.pkl` | 445KB | Confirmed loadable |
| TIE v9 | `models/tie_v9/tie_v9.pkl` | 126B | PLACEHOLDER (empty) |
| Longshot v6 | `models/longshot_v6/longshot_v6.pkl` | 131B | PLACEHOLDER (empty) |
| Overlay v5 | `models/overlay_v5/overlay_v5.pkl` | 126B | PLACEHOLDER (empty) |

---

## Next Actions (Ordered by Priority)

### 1. VERIFY Railway Redeploy
- Check Railway UI → ingestion-spine → latest deploy log
- Confirm no import crash
- Wait for 06:00 UTC cron fire → check `pipeline_runs` table for `status=success, runners_processed>0`

### 2. TRAIN New Model (User Priority)
- User wants: "one really training, slow but real"
- Training corpus: combine `backtest_50k_clean.csv` (50k, 2015) + `raw_races_2024_2025.txt` (filtered to UK/IRE ~58k)
- Template: `app/ml/trainers/train_sqpe_v15.py`
- Target: SQPE v16 — GradientBoosting, trained on ~108k real rows
- Key features from CSV: `sp` (Starting Price), `or`, `rpr`, `ts`, `draw`, `going`, `dist`, `ran`, `class`
- Label: `pos` (finishing position) → binary `won` (pos==1) or top-2/top-3
- Ask user about the 650MB file location before training

### 3. REMAINING RISKS (from fix report)
| ID | Severity | Issue |
|---|---|---|
| R-01 | HIGH | `race_results`/`runner_results` empty — wait for races to finish (~17:00-20:00 UTC) |
| R-02 | MEDIUM | Railway cron `0 10 *` should be `0 6 *` — change in Railway UI |
| R-03 | MEDIUM | `velo_verdicts.horse_name` stores `horse_id` — verdict generator not in repo |
| R-04 | LOW | `ingestion_anomalies` column mismatch — silent fail |
| R-05 | LOW | `market_snapshots` not polling — not scheduled in Railway |

### 4. RACING API MCP
- MCP config set in `~/.claude.json` — headers with `X-RacingAPI-Username/Password`
- Tools not loading in current session
- Restart Claude Code and verify with `/list-tools` or test tool call

---

## Supabase Post-Fix Snapshot

| Table | Rows | Status |
|---|---|---|
| `runners` | 265 | Clean, UNIQUE(race_id, horse_id) enforced |
| `races` | 32 | Correct |
| `runner_race_facts` | 243 | Correct |
| `horse_profiles` | 243 | Correct |
| `raw_payload_archive` | 25 | Active |
| `race_results` | 0 | Waiting for today's races |
| `runner_results` | 0 | Waiting for today's races |
| Active `in_progress` runs | 0 | Clean |

---

## Key Credentials (READ FROM .env — NEVER HARDCODE)
- Supabase project: `ltbsxbvfsxtnharjvqcm`
- Railway project: `sincere-empathy`
- All creds in `.env` — `.env` is gitignored

---

## Victory Conditions (Doctrine)
- [ ] Railway deploy succeeds (no import crash)
- [ ] Cron at 06:00 UTC fires → `pipeline_runs` closes `status=success`
- [ ] `runners_processed > 0`
- [ ] `race_results` + `runner_results` populate after races finish
- [ ] No stacked `in_progress` runs
- [ ] SQPE v16 trained on real 2024-2025 data
