# VÉLØ MCP Workflow (Foundation Layer)

## 1. RaceIndexAgent (Mandatory First)
- Input: Raw PDF
- Output: { venue, date, races: [{race_time, race_name, ...}] }
- Failure: System halt

## 2. RunnerParserAgent
- Input: PDF (Official Ratings)
- Output: List of runners with {horse_name, horse_number, age, weight, trainer, jockey}
- No opinions, just facts

## 3. RatingsParserAgent
- Input: PDF (Topspeed, RPR)
- Output: List of ratings with {horse_name, horse_number, official_rating, rpr, topspeed}
- Explicit nulls only, never inferred

## 4. SanityCheckAgent (Hard Gate)
- Input: RaceIndex + Runners + Ratings
- Validates: race count matches, runner names align, no ghost runners, no missing mandatory fields
- Veto power: if FAIL, system halts

## 5. Output to Intelligence Layer
- Consolidated data structure
- Ready for SQPEAgent, TIEAgent, etc.

## Current Status
✅ Foundation layer agents created (mock data)
✅ MCP coordinator created
✅ Sanity check implemented

## Next Steps
1. Replace mock data with real PDF parsing
2. Add parallel execution for parsing agents
3. Integrate with existing VÉLØ intelligence layer
4. Implement learning layer (ResultIngestAgent, PostRaceAuditAgent, DoctrinePatchAgent)
