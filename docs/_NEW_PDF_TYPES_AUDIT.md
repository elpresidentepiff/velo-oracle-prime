# New PDF Types Audit — Pontefract 21.04.26

## F_0011_XX — POSTDATA + TOPSPEED SUMMARY (Full Card)

This is a GOLD summary sheet. One page covers the ENTIRE card with two data blocks per horse:

### POSTDATA Block (per horse, per race):
- TRAINER FORM (1st time / overall)
- GOING (G = good)
- DIST (distance in furlongs)
- COURSE (course form)
- DRAW (stall position advantage)
- ABILITY (? = unknown, blank = none)
- RECENT FORM

Each cell is either: blank (no data), "-" (negative), "?" (uncertain/possible)

This is a QUICK REFERENCE for trainer intent signals:
- If TRAINER FORM = "?" and GOING = "?" → trainer hasn't proven at this going
- If COURSE = "?" → horse hasn't run here before
- If ABILITY = "?" → ability is uncertain/unproven

### TOPSPEED Block (per horse, per race):
- LATEST BEST: e.g. "56 56-Apr 10 Thsk 5.0g" = TS 56, achieved Apr 10 at Thirsk, 5f Good
- ADJUSTED: The adjusted TS figure

This gives us the WHEN and WHERE of the best speed figure — crucial for plot detection.
E.g. "28 83-Sep 30 Ayr 6.0s" = Azure Zain's best TS was 83 at Ayr in September on soft.

## O_0001_XX — PROFILE (Per Race)

One page per RACE (not per card). Contains per-horse LIFETIME STATISTICS:

For each horse:
- Placings count
- Lifetime record: Starts | Wins | Places | Best TS | Best RPR
- Distance record (at today's distance)
- Going record (at today's going)
- Course record (at today's course)
- Time of year record (at today's time of year)
- Days since run
- Field size record (at today's field size)
- Weight carried record
- Race value record
- Race type record (2yo, Class X, Mdn, etc.)

This is MASSIVE for the Plot Engine:
- Course + Distance + Going = C/D/G proven flag
- Time of year = seasonal pattern
- Race value = class level performance
- Weight carried = how horse handles today's weight

## O_0008_XX — FORM (Racing Post Race Report, Per Race)

One page per RACE. Contains the FULL RACING POST FORM GUIDE:

For each horse:
- Breeding: Sire, Dam, G Sire, Sales price
- Trainer + Jockey + Owner + Breeder
- Draw position
- Trainer 14-day record (rtf%)
- Detailed breeding commentary
- LAST RUN DETAILS: date, course, type, distance, going, position, beaten distance,
  jockey, weight, SP, comment, OR, TS, RPR
- NOTE-BOOK entries (expert analysis of last run)

This is the RICHEST source. The NOTE-BOOK entries contain:
- "a February foal who is out of an unraced half-sister to winners..."
- "shaped encouragingly on her debut, while leaving the impression a stiffer test of..."
- "kept on final 110yds"

The last-run comments tell us EXACTLY what happened — whether the horse was unlucky,
ran green, stayed on, etc.

## O_0006_XX — FORM DETAILED (Full Form Guide, Per Race)

2 pages per RACE. Contains EVERYTHING from O_0008 PLUS:
- Full lifetime statistics table (Wins/Pcs/Runs/RPR by Life/2026/Dist/Crs/Class/GF-Hd/6-15ms/9-1to9-7)
- Sire/Dam breeding analysis
- Full race replay of last run with all runners, SPs, distances
- Race PM (Race Post Mark) for last run

## Summary: What Each PDF Gives Us

| Code | Type | Scope | Key Intelligence |
|------|------|-------|-----------------|
| F_0015_OR | Official Ratings | Full card | OR, Best winning OR, Highest entered, Lowest win, RPR |
| F_0032_TS | Top Speed | Full card | TS latest/course/dist/going, Base, Master |
| F_0016_XX | Spotlight | Full card | Free-text comments, NLP sentiment |
| F_0011_XX | Postdata+TS Summary | Full card | Quick-ref trainer/going/course/draw flags + TS with date/venue |
| O_0001_XX | Profile | Per race | Lifetime stats by C/D/G/time/weight/value |
| O_0008_XX | Form Short | Per race | Breeding, last run details, NOTE-BOOK comments |
| O_0006_XX | Form Detailed | Per race | Everything in O_0008 + full stats table + race replay |

## Priority for VÉLØ Integration

1. **F_0011_XX (Postdata)** — HIGH. The "?" flags are instant trainer intent signals.
   The adjusted TS with date/venue is better than the TS PDF for trend analysis.

2. **O_0006_XX (Form Detailed)** — HIGH. The lifetime C/D/G stats and last-run comments
   are the missing piece for education run detection.

3. **O_0001_XX (Profile)** — MEDIUM. Useful for C/D/G proven flags but O_0006 has more.

4. **O_0008_XX (Form Short)** — MEDIUM. Subset of O_0006, useful if O_0006 not available.
