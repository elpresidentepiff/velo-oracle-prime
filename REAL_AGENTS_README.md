# VÉLØ Oracle - Real Agent System

## Overview

This implementation replaces placeholder agents (SQPE, TIE, NDS, V9PM) with 5 real working agents that analyze race data and produce actionable betting verdicts.

## Architecture

### 1. Five Real Agents

Each agent analyzes different aspects of a race and produces a score (0-100):

#### **Agent 1: Form Analyzer** (`app/engine/agents/form_analyzer.py`)
- Analyzes recent race form
- Evaluates finishing positions
- Identifies improvement/decline trends
- No database required

#### **Agent 2: Connections Analyzer** (`app/engine/agents/connections_analyzer.py`)
- Queries `trainer_velocity` and `jockey_velocity` tables
- Calculates combined strike rates
- Identifies "hot combos" (both profitable in last 14 days)
- **Requires database connection**

#### **Agent 3: Course/Distance Analyzer** (`app/engine/agents/course_distance_analyzer.py`)
- Queries `horse_velocity` table
- Checks course/distance/going suitability
- Identifies specialists (SR > 15%)
- **Requires database connection**

#### **Agent 4: Ratings Analyzer** (`app/engine/agents/ratings_analyzer.py`)
- Uses OR/TS/RPR ratings
- Calculates race average
- Identifies well-handicapped horses
- No database required

#### **Agent 5: Market Analyzer** (`app/engine/agents/market_analyzer.py`)
- Analyzes odds
- Compares market rank vs ratings rank
- Identifies value bets
- No database required

### 2. Orchestrator (`app/engine/orchestrator.py`)

Runs all 5 agents and produces final betting verdicts:

**Agent Weights:**
- Connections: 25%
- Ratings: 20%
- Form: 20%
- Course/Distance: 20%
- Market: 15%

**Betting Rules:**
- **BACK @ 2%**: Score > 70 + hot connections + specialist
- **BACK @ 1%**: Score > 60 + value bet
- **LAY @ 0.5%**: Score < 40
- **PASS**: Everything else or outside 3/1-20/1 range

### 3. Audit Trail

All agent executions and verdicts are saved to database:

- **`agent_executions`**: Individual agent scores and evidence
- **`race_verdicts`**: Final betting decisions

## Database Schema

### Migration: `supabase/migrations/006_add_velocity_stats.sql`

Creates 5 new tables:

1. **`trainer_velocity`**: Trainer performance statistics
2. **`jockey_velocity`**: Jockey performance statistics  
3. **`horse_velocity`**: Horse course/distance/going stats
4. **`agent_executions`**: Agent execution audit trail
5. **`race_verdicts`**: Final betting verdicts

## Data Ingestion

### Script: `workers/ingestion_spine/ingest_velocity_stats.py`

Ingests velocity statistics from CSV files:

```bash
python -m workers.ingestion_spine.ingest_velocity_stats \
  --trainers trainers.csv \
  --jockeys jockeys.csv \
  --horses horses.csv
```

**CSV Formats:**

**trainers.csv:**
```csv
trainer_name,last_14d_record,last_14d_sr,last_14d_pl,overall_record,overall_sr,overall_pl
A. King,3-15,20.00,5.50,45-230,19.57,12.30
```

**jockeys.csv:**
```csv
jockey_name,last_14d_record,last_14d_sr,last_14d_pl,overall_record,overall_sr,overall_pl
J. Doyle,4-20,20.00,8.40,156-789,19.77,34.50
```

**horses.csv:**
```csv
horse_name,stat_type,record,sr
UNITED APPROACH,course_kempton,2-5,40.00
UNITED APPROACH,distance_2m,3-8,37.50
```

## CLI Usage

### Script: `app/engine/run_analysis.py`

Run complete race analysis:

```bash
# From database
python -m app.engine.run_analysis \
  --race-id WOL_20260109_1625 \
  --output results.json

# From JSON file
python -m app.engine.run_analysis \
  --race-id WOL_20260109_1625 \
  --input sample_race.json \
  --output results.json
```

**Output Format:**
```json
{
  "verdicts": [
    {
      "horse_name": "MASTER GREY",
      "final_score": 78.5,
      "action": "BACK",
      "stake_pct": 2.0,
      "reason": "Strong play: Score=78.5, Hot combo + Specialist",
      "agent_scores": {
        "form": 75.0,
        "connections": 85.0,
        "course_distance": 90.0,
        "ratings": 82.0,
        "market": 65.0
      },
      "evidence": { ... }
    }
  ],
  "summary": {
    "total_runners": 5,
    "back_plays": 1,
    "lay_plays": 0,
    "pass": 4
  }
}
```

## Testing

### Run System Tests

```bash
# Test without database (uses sample data)
cd /home/runner/work/velo-oracle-prime/velo-oracle-prime
PYTHONPATH=. python /tmp/velo_test_data/test_system.py
```

### Test Data Ingestion

```bash
# Ingest sample data
python -m workers.ingestion_spine.ingest_velocity_stats \
  --trainers /tmp/velo_test_data/trainers.csv \
  --jockeys /tmp/velo_test_data/jockeys.csv \
  --horses /tmp/velo_test_data/horses.csv
```

### Test Analysis

```bash
# Run analysis on sample race
python -m app.engine.run_analysis \
  --race-id WOL_20260109_1625 \
  --input /tmp/velo_test_data/sample_race.json \
  --output /tmp/results.json
```

## Environment Variables

Required for database connectivity:

```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

## Key Features

✅ **5 Real Agents**: Not placeholders - actual working analysis
✅ **Weighted Scoring**: Sophisticated multi-agent decision making
✅ **Betting Rules**: Clear BACK/LAY/PASS logic
✅ **Audit Trail**: Complete transparency in database
✅ **CLI Interface**: Easy to use command-line tools
✅ **CSV Ingestion**: Import velocity stats from Racing Post data
✅ **Database Integration**: Full Supabase integration
✅ **Graceful Degradation**: Works without database (reduced functionality)

## Agent Scoring Examples

### Form Analyzer
- Last time winner: +30 points
- Recent top-3: +20 points
- Consistency: up to +20 points
- Improving form: up to +15 points

### Connections Analyzer
- Trainer hot (25%+ SR): +25 points
- Jockey in form (20%+ SR): +20 points
- Hot combo (both profitable): +20 points

### Course/Distance Analyzer
- Specialist (33%+ SR): +40 points
- Proven record (20%+ SR): +25 points
- Multi-specialist: +15 points bonus

### Ratings Analyzer
- Top-rated: +35 points
- Well-handicapped: +25 points
- Below average: -20 points

### Market Analyzer
- Value (rated higher than priced): +35 points
- Optimal odds range: +20 points
- Overbet favorite: -25 points

## Next Steps

1. Deploy migration to Supabase
2. Ingest real velocity stats from Racing Post
3. Test with live race data
4. Monitor agent performance in production
5. Tune agent weights based on results

## Notes

- Agents work independently and can be tested/improved separately
- Orchestrator weights can be adjusted based on performance
- Betting rules can be modified for different risk profiles
- Audit trail enables complete backtesting and analysis
