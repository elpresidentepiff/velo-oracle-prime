# VÉLØ Daily Plot Engine — How It Works

## The Problem We're Solving

A handicap trainer plots a horse to win by deliberately running it badly over several races to get the handicapper to drop its Official Rating (OR). Once the OR drops far enough below the mark the horse last won off, the trainer enters it in a race where it can win. The horse looks out of form on paper. The market often underestimates it. That's the edge.

VÉLØ's job is to find these horses before the race.

---

## The 4 Inputs (Racing Post PDFs)

Every day, for every venue, Racing Post publishes 4 files:

| File Code | Name | What It Contains |
|---|---|---|
| **F_0015_OR** | Official Ratings | Each horse's current OR, the OR it last won off (best winning mark), and its RPR |
| **F_0032_TS** | Top Speed | Each horse's speed rating per run — last 6-8 outings with position, TS, distance, going |
| **F_0011_XX** | Postdata | A grid showing trainer form, going suitability, course suitability, draw, ability — each as positive/neutral/negative. Also flags headgear changes. |
| **F_0016_XX** | Spotlight | Free-text expert comments on every horse. Written by Racing Post analysts. |

You drop these 4 files per venue into the chat. That's your only job.

---

## Step 1 — PDF Parsing

The pipeline reads every PDF and extracts the data per horse.

**From F_0015_OR:**
- `current_or` — where the horse sits today on the handicap ladder
- `best_winning_life` — the highest OR it has ever won off
- `or_delta` — the gap between today's OR and the winning mark (negative = below it)

**From F_0032_TS:**
- Per-run history: for each of the last 6-8 runs — finishing position, speed rating (TS), distance, going
- `ts_peak` — the best TS it has run in the last 6 runs (true engine assessment)
- `ts_trend` — is the TS going up or down across the last 3 runs?

**From F_0011_XX (Postdata):**
- `trainer_form` — is the trainer's yard in form right now?
- `going_flag` — does today's going suit this horse?
- `course_flag` — has it run well here before?
- `ability_flag` — does the Racing Post rate its ability positively?
- `headgear_code` — is it wearing new gear today (blinkers, visor, cheekpieces)?

**From F_0016_XX (Spotlight):**
- Free-text comment per horse
- NLP extraction: 15 signal categories including trainer notes, market notes, ground suitability, trip suitability, positive/negative sentiment

---

## Step 2 — The Plot Score

For every horse, the engine computes a `plot_conviction` score from 0.0 to 1.0.

**Signal 1 — OR Delta (most important)**
- If the horse's current OR is at or below its best winning mark → score = 1.0
- Every 1lb above the winning mark reduces the score
- A horse 10lb above its winning mark → score ≈ 0.5

**Signal 2 — OR Trend**
- Is the OR dropping run by run? (trainer deliberately getting the mark down)
- 6 consecutive drops → strong signal
- No trend → neutral

**Signal 3 — TS Peak (engine assessment)**
- Peak TS in last 6 runs tells us what the horse is truly capable of
- High peak TS + low recent TS = horse has been running below its ability (setup runs)

**Signal 4 — Setup Runs**
- Count of runs where the horse finished unplaced (position 0 or 6+)
- 3+ setup runs in last 6 = possible deliberate poor performances

**Signal 5 — Postdata Flags**
- Trainer in form + going suits + course suits + ability positive = all systems go
- Cold stable (trainer out of form) + strong ability = deliberate hiding

**Signal 6 — Headgear**
- First-time blinkers, visor, or cheekpieces = trainer making a physical intervention today

**Signal 7 — Spotlight NLP**
- Positive expert comment (3+ positive phrases) = external confirmation

The final `plot_conviction` is a weighted combination of all 7 signals.

---

## Step 3 — Filtering

Only horses with `plot_conviction >= 0.7` make the list.

Horses are excluded if:
- They are 2-year-olds with no OR history (unraced, no data)
- Their name is a parser artifact (e.g. starts with "Xj", or is "Spotlight Verdict A")
- They have no OR data at all

---

## Step 4 — Verdict Rating

Each qualifying horse gets a star rating:

| Rating | Criteria |
|---|---|
| **★★★** | OR drop + OR trend downward + engine proven (high peak TS) + setup runs + at least 1 specialist signal (gear/cold stable/spotlight) |
| **★★** | OR drop + engine proven + some supporting signals |
| **★** | OR drop only, limited supporting evidence |

---

## Step 5 — The Report

One line per horse:

```
| 3.52 | Roundhay Park | ★★★ | 29lb below winning mark · engine proven (peak TS 76) · cold stable · TS improving |
```

That's it. No tables of numbers. No raw data. Just the verdict.

---

## Step 6 — Results Check (after racing)

After the races run, the engine calls the Racing API to fetch results for each venue. It matches every plot candidate by name, finds their finishing position and SP, and reports:

- **WON** — horse won, at what price
- **PLACED** — 2nd or 3rd, at what price
- **UNPLACED** — beaten

This builds the performance record day by day.

---

## What VÉLØ Is NOT Doing (Yet)

- Not checking jockey bookings (is today's jockey better than last time?)
- Not checking race class (is it dropping in class as well as OR?)
- Not checking days since last run (fresh horse vs. busy horse)
- Not using the Racing API form history (only the PDF data)
- Not filtering by race type (handicap vs. conditions race)

These are the next improvements. The engine is finding the right horses. The refinements will sharpen the precision.

---

## Day 1 Proof (21 April 2026)

28 picks resolved across Pontefract, Wolverhampton, Ffos Las, Yarmouth:
- **5 winners** including Betweenthesticks (7/4F), Daytona Lady (7/4F), Kaaranah (11/10F)
- **10 placed** (2nd or 3rd)
- **53.6% place rate** on Day 1

---

## Your Daily Workflow

1. Download the 4 Racing Post PDFs per venue (OR, TS, Postdata, Spotlight)
2. Drop them into the chat
3. Receive the verdict report — one line per horse
4. After racing, ask for results and I'll pull them from the API
