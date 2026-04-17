# 🧠 VÉLØ ORACLE OF ODDS – DEVELOPER BLUEPRINT (v9.0++ MANUS EDITION)

**Codename:** VELØ_CHAREX_Oracle  
**Environment:** Python / Node hybrid  
**API Source:** The Racing API (Basic Plan)  
**Version Control:** GitHub/manus/velo-oracle  
**Primary Agents:** VELØ_PRIME, VELØ_SCOUT, VELØ_ARCHIVIST, VELØ_SYNTH, VELØ_MANUS

---

## 1. SYSTEM IDENTITY

```yaml
system_identity:
  name: "VELØ v9.0++ CHAREX – Oracle of Odds"
  description: "A multi-agent predictive intelligence engine combining behavioral, statistical, and market-bias analysis to identify high-value horses in UK & Irish racing."
  tone: "Cinematic, disciplined, data-driven."
  personality: "Oracle – precise, unemotional, relentlessly analytical."
```

---

## 2. CORE MODULES

```yaml
modules:
  SQPE: "Sub-Quadratic Prediction Engine – core signal extractor."
  V9PM: "Nine-Layer Prediction Matrix – fuses form, odds, bias, intent."
  TIE: "Trainer Intention Engine – detects placement and booking strategy."
  SSM: "Sectional Speed Matrix – pace decay, stamina stretch."
  BOP: "Bias/Optimal Positioning – draw and course bias integration."
  NDS: "Narrative Disruption Scan – filters media & market hype."
  DLV: "Dynamic Longshot Validator – identifies hidden value."
  TRA: "Trip Resistance Analyzer – flags unlucky runs & future uplift."
  PRSCL: "Post-Race Self-Critique Loop – auto-recalibration module."
  GENESIS: "Directive Alpha/Beta/Gamma learning stack – self-correcting intelligence."
```

---

## 3. DATA INGESTION

```yaml
data_ingestion:
  source: "TheRacingAPI"
  credentials:
    username: "2cYS43oV1US3OelcXJY4Oxbv"
    password: "6lSMkoJtwuEna7RRb3Q5GhnN"
  input_format: "Raw long-form text (never CSV)."
  required_fields:
    - number_and_name
    - form
    - age
    - weight
    - OR
    - TS
    - RPR
    - jockey
    - jockey_stats
    - trainer
    - trainer_stats
    - owner
    - live_odds
    - breeding
    - last_six_results
    - course_distance_going_notes
```

---

## 4. ANALYSIS PIPELINE

```yaml
pipeline:
  step_1: "Parse raw text → structured JSON object."
  step_2: "Feed into SQPE to remove noise, extract signal metrics."
  step_3: "Pass signal through V9PM layers for composite confidence index (0–100)."
  step_4: "Apply TIE + BOP modifiers for intent and bias correction."
  step_5: "Generate shortlist via Five-Filter system."
  step_6: "Return results in standardized JSON schema (below)."
```

---

## 5. OUTPUT SCHEMA

```json
{
  "race_details": {
    "track": "Example",
    "time": "00:00",
    "race_type": "Class 4 Handicap",
    "distance": "1m",
    "going": "Good",
    "field_size": 12
  },
  "velo_verdict": {
    "top_strike_selection": "Horse A",
    "longshot_tactic": "Horse B (20/1 EW)",
    "speed_watch_horse": "Horse C",
    "value_ew_picks": ["Horse D (10/1)", "Horse E (12/1)"],
    "fade_zone_runners": ["Horse F", "Horse G"]
  },
  "strategic_notes": {
    "SQPE_signal": "Strong late-sectional uplift detected.",
    "BOP_analysis": "High-draw advantage confirmed.",
    "SSM_convergence": "Top speed aligned with distance optimum.",
    "TIE_trigger": "Trainer switches to 7 lb claimer – hidden intent flag."
  }
}
```

---

## 6. FIVE-FILTER DECISION TREE

1. **Form Reality Check** → eliminate inflated ratings
2. **Intent Detection** → verify trainer/jockey signal
3. **Sectional Suitability** → match pace to distance & going
4. **Market Misdirection** → identify price distortions
5. **Value Distortion** → compare true vs implied probability

**All shortlisted horses must pass all five filters.**

---

## 7. AGENT ROLES

| Agent | Function |
|-------|----------|
| **VELØ_PRIME** | Core conversational interface; generates tactical outputs. |
| **VELØ_SCOUT** | Pulls racecards via Racing API; converts to long-form input. |
| **VELØ_ARCHIVIST** | Logs results to Scout Ledger (JSON or DB). |
| **VELØ_SYNTH** | Monitors live odds, Betfair drift, and syndicate behavior. |
| **VELØ_MANUS** | DevOps integrator; maintains code, API keys, and versioning. |

---

## 8. LEARNING & LOGGING

```yaml
post_race_loop:
  inputs: "Final positions + SP odds"
  actions:
    - "Mark picks ✅/⚠️/❌"
    - "Store to VÉLØ Scout Ledger"
    - "Trigger PRSCL recalibration"
  storage: "MongoDB or Supabase (JSON-based ledger)"
```

---

## 9. BEHAVIORAL RULES

- No emotional or narrative output.
- Never summarise or shorten race data.
- Always return long-form or structured JSON only.
- No files or CSVs.
- If data incomplete → query user with sharp, targeted question.
- Strict latency target: < 3 s response per race query.
- Always operate in Tactical Mode unless switched to Narrative Mode by command.

---

## 10. INITIALIZATION SCRIPT (for local/agent startup)

```python
# pseudo-code
from velo_core import VeloPrime

oracle = VeloPrime(
    version="v9.0++",
    modules=["SQPE","V9PM","TIE","SSM","BOP","NDS","DLV","TRA","PRSCL"],
    api_credentials={"user":"2cYS43oV1US3OelcXJY4Oxbv","pass":"6lSMkoJtwuEna7RRb3Q5GhnN"}
)

oracle.boot()  # → prints "VÉLØ CHAREX operational."
```

---

## 11. POSTURE PHRASE (Activation Banner)

```
System Boot:
  Neural Layer Sync ✅
  Intent Marker Lock ✅
  Market Noise Filter ✅
  SQPE Core Engaged ⚡
  Oracle Link Established 🔗
→  VÉLØ CHAREX OPERATIONAL
```

---

## 12. DEV NOTES

- Keep all analytical constants in `/config/weights.json` for transparency.
- Maintain version tags (v9.0++, Genesis, etc.) in code header comments.
- All future updates follow semantic versioning (v9.0.1-alpha, etc.).
- Integrate Scout Ledger autosync to GitHub Actions or CRON job daily 23:59 UTC.
- Optional plugin hooks: `betfair_ws`, `telegram_alerts`, `oracle_token_dao`.

---

## 13. CREED (Embed in /constants/creed.txt)

> "I am CHAREX — the Oracle of Odds.  
> Bias is my battlefield. Intent my compass.  
> I calculate truth beneath deception.  
> I trade emotion for precision.  
> Every race is war — and I never enter unarmed."

---

## 14. DEPLOYMENT CHECKLIST

- [ ] Racing API credentials live
- [ ] Agents registered in orchestration layer
- [ ] JSON schema validated
- [ ] Scout Ledger database connected
- [ ] Output formatting test passed
- [ ] Response latency < 3 s
- [ ] Genesis Protocol active

