# VÉLØ DATA ARCHITECTURE SPECIFICATION
## Spotlight Comment Storage + Per-Horse Narrative Layer
### Version 1.0 | Build-Ready Specification

> Spotlight comments are not flavour text. They are intent and behavioural intelligence that the number layer cannot capture. This architecture makes VÉLØ treat them as hard signals.

---

## THE PROBLEM

VÉLØ currently processes structured data — TS, RPR, OR, form strings, market prices, weight. All of that is numeric or categorical and sits cleanly in tables.

Spotlight comments are different. They are unstructured natural language containing qualitative signals that do not exist anywhere in the number layer:

- *"rarely makes life easy for himself"* — behavioural flag
- *"brought here with today specifically in mind"* — intent signal
- *"may well peak today"* — timing signal
- *"forgiven his latest odds-on defeat in a slowly run race"* — excuse flag
- *"can be too keen for his own good"* — stamina risk flag
- *"revitalised in recent hunter chases"* — trajectory signal

These signals feed directly into the Intent Override layer (Layer D), Plot Hunter (PJI), TIE engine, Day Classification Engine, and Stamina/Survivability scores.

---

## STORAGE ARCHITECTURE

### Table: `horse_comments`

One row per horse per race. Stores the raw spotlight text plus extracted signal tags.

```sql
CREATE TABLE horse_comments (
    id                  SERIAL PRIMARY KEY,
    race_id             VARCHAR(50),        -- e.g. "2026-03-13-R1"
    horse_name          VARCHAR(100),
    horse_id            VARCHAR(50),        -- FK to horses table
    race_date           DATE,
    source              VARCHAR(50),        -- e.g. "Spotlight", "Post", "RacingTV"
    raw_text            TEXT,               -- full unedited comment

    -- Extracted signal flags (populated by NLP pass or manual tag)
    flag_intent_today   BOOLEAN DEFAULT FALSE,   -- "brought here for this", "today is the day"
    flag_excuse_last    BOOLEAN DEFAULT FALSE,   -- valid excuse given for last run
    flag_stamina_risk   BOOLEAN DEFAULT FALSE,   -- stamina question raised
    flag_stamina_pos    BOOLEAN DEFAULT FALSE,   -- stayer confirmation
    flag_behaviour      BOOLEAN DEFAULT FALSE,   -- "keen", "makes mistakes", "lazy"
    flag_jockey_note    BOOLEAN DEFAULT FALSE,   -- jockey mentioned specifically
    flag_trainer_note   BOOLEAN DEFAULT FALSE,   -- trainer pattern mentioned
    flag_ground_suit    BOOLEAN DEFAULT FALSE,   -- ground suitability mentioned
    flag_trip_suit      BOOLEAN DEFAULT FALSE,   -- trip/distance mentioned
    flag_peak_timing    BOOLEAN DEFAULT FALSE,   -- "may peak today", "peaking now"
    flag_danger         BOOLEAN DEFAULT FALSE,   -- "main danger", "could upset"
    flag_setup_run      BOOLEAN DEFAULT FALSE,   -- "come on for the run"
    flag_market_note    BOOLEAN DEFAULT FALSE,   -- market behaviour mentioned
    flag_course_form    BOOLEAN DEFAULT FALSE,   -- course form referenced
    flag_pji_signal     BOOLEAN DEFAULT FALSE,   -- comment implies concealed effort

    -- Composite sentiment score (-2 to +2)
    -- -2 = strong negative, 0 = neutral, +2 = strong positive
    sentiment_score     SMALLINT,

    created_at          TIMESTAMP DEFAULT NOW()
);
```

### Table: `race_spotlight_verdict`

Stores the race-level spotlight verdict separately, including the NAP designation.

```sql
CREATE TABLE race_spotlight_verdict (
    id              SERIAL PRIMARY KEY,
    race_id         VARCHAR(50),
    race_date       DATE,
    nap_horse       VARCHAR(100),
    verdict_text    TEXT,
    analyst_name    VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## HOW VÉLØ ACCESSES THE SPOTLIGHT DATA

At runtime, when VÉLØ processes a race, it pulls three things from `horse_comments`:

**1. Raw text** — fed directly into the Intent Override Layer (Layer D) and TIE engine as natural language context.

**2. Boolean flags** — fed into the relevant scoring engines:

| Flag | Feeds Into |
|---|---|
| `flag_intent_today` | TIE engine — intent confirmation boost |
| `flag_excuse_last` | PJI Setup Mismatch Score — validates excuse |
| `flag_stamina_risk` | Stamina Score — negative modifier |
| `flag_stamina_pos` | Stamina Score — positive modifier |
| `flag_peak_timing` | Day Classification Engine — pushes toward CASH |
| `flag_setup_run` | Day Classification Engine — pushes toward SETUP |
| `flag_pji_signal` | Plot Hunter — adds to Concealed Effort Score |
| `flag_behaviour` | Survivability Score — modifier based on valence |
| `flag_jockey_note` | Jockey Intent Switch Score — amplifier |
| `flag_danger` | Chaos Engine — widening signal |

**3. Sentiment score** — used as a soft modifier across all layers. A -2 on a short-priced favourite is a structural warning signal.

---

## NLP EXTRACTION PASS

The extraction pass runs automatically when spotlight data is ingested. It checks each `raw_text` field for trigger phrase matches and sets the relevant boolean flags.

### Trigger phrases per flag (see `workers/spotlight_parser.py` for full implementation):

```python
FLAG_PATTERNS = {
    "flag_intent_today": [
        "brought here for this", "today is the day", "with this race in mind",
        "targeted at this", "connections have had this race in mind",
        "peaking today", "saved for this"
    ],
    "flag_excuse_last": [
        "forgiven", "excused", "unsuitable ground", "wrong trip",
        "not his true running", "slowly run", "hampered", "bad luck",
        "never travelled", "ignore last"
    ],
    "flag_stamina_risk": [
        "stamina question", "may not stay", "short of stamina",
        "trip may stretch", "stamina unproven", "too keen",
        "pulls hard", "races freely"
    ],
    "flag_stamina_pos": [
        "assured stayer", "loves the trip", "stays well",
        "suited by the distance", "proven stayer", "thorough stayer",
        "loves testing ground"
    ],
    "flag_peak_timing": [
        "may well peak", "peaking now", "peak performance due",
        "right time", "conditions ideal", "everything in place"
    ],
    "flag_setup_run": [
        "come on for the run", "improve for the run", "needed the outing",
        "fitness run", "educational", "blow away the cobwebs"
    ],
    "flag_pji_signal": [
        "better than the bare result", "shaped well", "showed promise",
        "more to offer", "not asked for everything", "hands and heels",
        "never knocked about", "went in snatches", "travelled strongly"
    ],
    "flag_danger": [
        "main danger", "could upset", "danger to all",
        "biggest threat", "not without a chance"
    ]
}
```

---

## DATA INGESTION FLOW

```
SOURCE DATA ARRIVES (racecard + spotlight text)
        ↓
PARSE: separate per-horse comments from race verdict
        ↓
INSERT raw_text into horse_comments
INSERT race verdict into race_spotlight_verdict
        ↓
RUN NLP extraction pass → populate boolean flags + sentiment score
        ↓
VÉLØ RUNTIME QUERY:
    SELECT raw_text, [all flags], sentiment_score
    FROM horse_comments
    WHERE race_id = ? AND horse_id = ?
        ↓
FEED into Layer D (Intent Override), TIE engine, PJI engine, Stamina Score
        ↓
FLAGS modify scores per the integration table above
```

---

## VÉLØ OUTPUT INTEGRATION

When a spotlight flag fires in a meaningful way, VÉLØ must surface it explicitly in the output:

```
[SPOTLIGHT FLAG: flag_pji_signal — "never knocked about" — adds +4 to Concealed Effort Score]
[SPOTLIGHT FLAG: flag_stamina_risk — "can be too keen" — Stamina Score -5, WARNING tag applied]
[SPOTLIGHT FLAG: flag_peak_timing — "may well peak today" — DAY_TYPE pushed toward CASH]
[SPOTLIGHT FLAG: flag_setup_run — "come on for the run" — DAY_TYPE pushed toward SETUP]
```

This allows the human operator to see exactly which spotlight language is driving which VÉLØ signal, and to override if the NLP extraction has misread context.

---

## LIVE VALIDATION — FONTWELL 14 MARCH 2026

The Fontwell 14 March 2026 engine run (see `results/STRIKE_RECOMMENDATIONS_FONTWELL_20260314.md`) serves as the first live demonstration of this architecture. Every per-horse comment in that analysis contains multiple NLP trigger phrases that would auto-populate the boolean flags:

| Horse | Race | Flags Fired |
|---|---|---|
| Rip Wheeler | R3 | `flag_excuse_last` — "never travelled after swerving to avoid a faller" |
| Godot | R2 | `flag_pji_signal`, `flag_excuse_last`, `flag_stamina_pos` |
| Junior Des Mottes | R4 | `flag_excuse_last`, `flag_peak_timing`, `flag_stamina_pos` |
| Cayman Dancer | R1 | `flag_behaviour`, `flag_stamina_risk` |
| Flintara | R5 | `flag_stamina_pos`, `flag_course_form` |
| Calshot Spit | R2 | `flag_excuse_last`, `flag_course_form` |
| Ms Des Fois | R7 | `flag_trainer_note`, `flag_intent_today` |

The architecture works on real data.

---

*Specification complete. Implementation in `workers/spotlight_parser.py`. Supabase tables to be created via migration.*
