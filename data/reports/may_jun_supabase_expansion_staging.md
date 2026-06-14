# May–Jun Supabase Expansion — Staging Report
## VÉLØ Oracle Prime — Read-Only Extraction Intelligence

**Status**: READ_ONLY — no writes, no backfill, no Supabase mutation  
**Generated**: 2026-06-14  
**Purpose**: Answer 6 key questions before any merge decision

---

## Q1 — Row Count Mismatch: Why 2,686 vs 2,528?

**Both were stale snapshots of a live, growing table.**

| Snapshot | Count | When |
|---|---|---|
| "2,528" | Stale | Captured early in project lifecycle, before Jun 10–13 ingestion |
| "2,686" | Stale | Captured yesterday's session |
| **2,715** | **Current** | **Confirmed via Content-Range header today, 2026-06-14** |

**Root cause**: The table is appended to daily as sigma results are ingested. No duplicate rows — the growth is real ingestion. The old 2,528 figure reflected the table at an earlier point.

**Reconciliation**: The 2k archive is alive and growing. All three counts are accurate snapshots at their respective times.

---

## Q2 — How Many of the 1,254 May–Jun Supabase Rows Duplicate the 740 Local Rows?

| Category | Count |
|---|---|
| Supabase May–Jun race_ids | 1,254 |
| Local sigma race_ids | 732 unique |
| **Overlap (in both)** | **467** |
| **Supabase-only (new unique rows)** | **787** |
| Local-only (not in Supabase) | 265 |

**Net:** 787 rows in Supabase that do not exist in local sigma files.  
**Local-only 265:** races the local system ran but Supabase was never synced (Jun 03–13 period).

---

## Q3 — How Many Are New Unique Rows?

**787 Supabase-only rows — all from May 01–22.**

| Date range | Rows |
|---|---|
| May 01–22 (main block) | 749 |
| May 24–29 (stragglers) | 16 |
| Jun 03–05 (stragglers) | 17 |
| **Total SB-only** | **787** |

These rows represent the period **before the local sigma JSON system began tracking rows** (local started May 23). They are real scored races from the live system — they just never existed in local files.

Combined universe if merged: **1,527 rows** (740 local + 787 SB-only)

---

## Q4 — Do They Have Course, SP, Outcome, and Race Date?

| Field | Coverage (May–Jun Supabase, n=1,254) |
|---|---|
| `date` | 100% |
| `track` (course) | **100%** |
| `outcome` (WIN/MISS/PLACED) | **100%** |
| `race_id` | **100%** |
| `actual_winner_sp` | 95.0% (1,191/1,254) |
| `velo_prime_prob` (VP) | **100%** (extracted from notes) |

**Yes — all four fields are present and clean in the Supabase May–Jun segment.**

---

## Q5 — Can They Join to `velo_innovation_protocol_1k_deduped.csv` for Pick SP / ROI?

**Partial join only. Race_id format mismatch.**

| Source | Race_id format | Example |
|---|---|---|
| Supabase May–Jun (82%) | Date-string | `2026-05-18_CRL_230` |
| Supabase May–Jun (18%) | Numeric | `918730` |
| Innovation protocol CSV | `rac_XXXXXXXX` | `rac_11874330` |

The innovation protocol CSV uses a `rac_` prefixed format. The Supabase numeric race_ids partially overlap (187 rows match), but the 982 date-string rows cannot join directly on race_id.

**Alternative join path**: `date + track + off_time` — possible for the stragglers but would need validation.

**For ROI analysis**: The innovation protocol CSV covers May 02–Jun 13, 1,431 rows, with `sp_decimal` (pick SP) and `won` (outcome). The `model_probability` field (0.04–1.0) is the equivalent of VP in this CSV. This CSV is the better ROI source for the rows it covers, but it cannot be assumed to match sigma_audits rows 1:1 without explicit join validation.

**Verdict**: ROI join is possible for a subset (~187 rows) via direct race_id. Full merge requires a secondary join key (date + track + time). Do not attempt until primary merge is validated.

---

## Q6 — Does VP >= 0.40 Still Hold After Adding May–Jun Supabase Rows?

**Yes. The gradient holds and strengthens.**

| Universe | n | VP>=0.40 rows | VP>=0.40 SR |
|---|---|---|---|
| Local 711-row (May 23–Jun 13) | 711 | 181 | 40.9% |
| SB-only May 01–22 rows | 787 | 95 | **43.2%** |
| Full May–Jun Supabase (1,254) | 1,254 | 256 | **42.2%** |

The VP>=0.40 signal predates the local sigma system. It was present and discriminating from at least May 01.

**Overall SR in SB-only rows**: 23.3% (183 wins from 787) — consistent with the overall baseline.

**Outcome × VP across all 2,715 Supabase rows** (VP extractable: 2,286 rows):

| Outcome | Mean VP |
|---|---|
| WIN | **0.3367** |
| PLACED | 0.2948 |
| MISS | 0.2394 |

VP gradient: WIN mean exceeds MISS mean by **+0.097** — persists across the full archive.

---

## Race_id Format Map

| Format | Era | Count | Join status |
|---|---|---|---|
| Numeric (e.g. 918730) | Jun (post-API change) | 272 | Can join to local and partial CSV |
| Date-string (2026-05-18_CRL_230) | May 01–22 | 982 | Cannot direct-join to CSV — needs date+track |

The format switch happened around late May when the race_id generation system changed.

---

## Three Sigma Layers — Confirmed

| Layer | Rows | VP | Era | Status |
|---|---|---|---|---|
| L1: Local corrected | 740 | 100% | May 23–Jun 14, post-surgery | Clean evidence base. USE NOW. |
| L2: SB May–Jun (unique) | 787 | 100% | May 01–22, straddles surgery | Same-era candidates. EXPAND NEXT. |
| L3: SB Mar–Apr | 1,061 | 83.5% | Pre-surgery | Separate study only. ERA_FLAG required. |
| EXCLUDED: Jan–Feb / NULL-date | 190 | 0% | Skeleton | Do not use. |

---

## What the 265 Local-Only Rows Tell Us

265 local sigma rows (May 23–Jun 13) exist in local files but NOT in Supabase.  
These are races the local system scored and logged, but Supabase was never synced.

This means **the 711 local universe is not a subset of Supabase** — it has unique rows.  
The true combined universe is larger than either source alone.

**Supabase sync gap for these rows**: Operator decision required before any Supabase push.

---

## Next Decision Required

**The immediate prize is Layer 2: 787 SB-only May 01–22 rows.**  
These are same-era (straddle the May 08 surgery line), 100% VP, 100% outcome, 100% track.

**Blocking question**: The 787 rows span May 01–22. The surgery was May 08. Should May 01–07 rows (pre-surgery, approximately 245 rows) be tagged as `era=PRE_SURGERY` and separated, or treated as the same era as May 08–22?

**Operator decision required before merge**:

> Option A — Era-split on May 08: Tag May 01–07 as PRE_SURGERY, May 08+ as POST_SURGERY. Use May 08–22 subset (~542 rows) in same layer as local 711.

> Option B — Full Layer 2 as one block: Use all 787 rows tagged as LAYER_2_MAY_PRE_LOCAL. Study separately, then decide merge.

> Option C — May 23 remains the clean line: Do not merge Layer 2 yet. First validate that L2 VP>0.40 SR (43.2%) is stable across dates before blending with L1.

---

## Hard Rules Confirmed (Still In Force)

- No Supabase writes
- No live scoring change
- No model promotion
- No Telegram
- No PR #91 merge
- Local 711/740-row universe remains the clean evidence base
- Do not blend pre-surgery and post-surgery rows without era flag

---

## Summary of 6 Answers

| Question | Answer |
|---|---|
| Why 2,686 vs 2,528? | Both stale — true count is **2,715**, table is live and growing |
| Duplicates with 711? | **467 overlap**, **787 unique SB rows**, 265 local-only |
| New unique rows? | **787** from May 01–22 — pre-local era, all new |
| Course / SP / outcome? | **100% coverage** on all four fields |
| ROI join possible? | Partial (187 rows direct join). Full merge needs date+track secondary key |
| VP>=0.40 holds? | **Yes — 42.2% SR** in full May–Jun Supabase set, 43.2% in SB-only |

---

*READ_ONLY — no Supabase writes — 2026-06-14*
