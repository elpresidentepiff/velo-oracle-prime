# Racing Post PDF Parsing

## Architecture

**One truth: canonical JSON from validated PDF parse.**

Parse flow:
1. Parse XX card (identity backbone: races + runners)
2. Enrich with OR/TS/PM (ratings, speed, prices)
3. Merge by (race_id, runner_number)
4. Validate (hard gates)
5. Insert to Supabase ONLY if clean

## Hard Validation Gates

If ANY hard gate fails → batch status = `rejected_bad_output` → **NO INSERT**

### Gate 1: No Placeholder Names
Rejects placeholder names like:
- TBD
- RUNNER A, RUNNER B, RUNNER C, etc.
- UNKNOWN
- N/A
- TO BE ADVISED

**Why:** Placeholder names indicate incomplete data from the source. These will cause downstream matching failures and corrupt historical statistics.

### Gate 2: Impossible Ages
Horses must be between 2 and 15 years old (realistic for racing).

**Why:** The age bug (confusing days-since-run with age) was causing ages like `122`. This gate catches such errors.

**Fix:** The parser now explicitly separates:
- Line 1 (form line): `days_since_run` - e.g., "21 D 5" means 21 days
- Line 2 (details line): `age` - e.g., "4" means 4 years old

### Gate 3: Runner Count Consistency
Declared runner count must match actual runners parsed.

**Exception:** If Non-Runner marker found, allows `declared - 1 == actual`.

**Why:** Mismatches indicate parsing failures or incomplete data.

### Gate 4: Distance Must Be Mapped
Every race distance must map to canonical `distance_yards`.

**Why:** Unmapped distances break downstream features that rely on distance calculations.

### Gate 5: Distance Consistency
`distance_yards` and `distance_furlongs` must be consistent.

**Formula:** `expected_furlongs = distance_yards / 220.0`

**Tolerance:** ±0.1 furlongs

**Why:** Catches conversion errors or data corruption.

### Gate 6: No All-Zero Predictions
If predictions exist, at least one must be non-zero.

**Why:** All-zero scores indicate prediction failure, not valid output.

## Distance Canonicalization

**Source of truth:** `distance_yards`

**Derived fields:**
- `distance_furlongs` = `distance_yards / 220.0`
- `distance_meters` = `distance_yards * 0.9144`

### Distance Map

```python
DISTANCE_MAP = {
    "5f": 1100,
    "6f": 1320,
    "7f": 1540,
    "1m": 1760,
    "1m 1f": 1980,
    "1m 2f": 2200,
    "1m 4f": 2640,
    "2m": 3520,
    "2m 4f": 4400,
    # ... etc
}
```

All Racing Post distance strings are mapped to yards. If a distance cannot be mapped, the race is **rejected** (Gate 4).

## Age vs Days-Since-Run

**The Bug:** Previous parsers confused days-since-run with age.

**The Fix:** XX racecards have TWO numbers in different locations:

### Format
```
Line 1 (Form): [number] [form] [NAME] [DAYS] D [other]
Line 2 (Details): [AGE] [weight] [jockey] [ratings]
```

### Example
```
1  09353-  BRAVE EMPIRE  21 D 5
4  9-8  William Cox  OR: 70  TS: 65
```

- **Days since run:** `21` (from "21 D 5" on form line)
- **Age:** `4` (first number on details line)

### Parser Strategy
1. Extract `days_since_run` from form line using pattern `(\d+)\s*D`
2. Extract `age` from details line (first integer 2-15)
3. Validate age with hard gate (2-15 range)
4. Store both fields separately in `Runner` model

## Module Structure

```
workers/ingestion_spine/racingpost_pdf/
  __init__.py           # Main parse_meeting() function
  types.py              # Pydantic models
  normalize.py          # Distance, name, weight normalization
  extract_words.py      # pdfplumber helpers
  parse_xx.py           # XX racecard parser (identity backbone)
  parse_or.py           # OR parser (Official Ratings)
  parse_ts.py           # TS parser (Timeform Speed)
  parse_pm.py           # PM parser (Price/Market)
  merge.py              # Merge runners across sources
  validate.py           # Hard validation gates
  cli.py                # Command-line interface
  __main__.py           # Module entry point
```

## Usage

### Python API
```python
from racingpost_pdf import parse_meeting

# Parse PDFs
report = parse_meeting([
    "fixtures/WOL_20260109_XX.pdf",
    "fixtures/WOL_20260109_OR.pdf",
    "fixtures/WOL_20260109_TS.pdf",
    "fixtures/WOL_20260109_PM.pdf"
])

if report.success:
    meeting = report.meeting
    print(f"Parsed {len(meeting.races)} races")
    
    for race in meeting.races:
        print(f"{race.off_time} {race.race_name} ({race.distance_text})")
        print(f"  Distance: {race.distance_yards} yards")
        
        for runner in race.runners:
            print(f"  {runner.runner_number}. {runner.name} ({runner.age}yo)")
else:
    print("Parse failed:")
    for error in report.errors:
        print(f"  - {error.message}")
```

### Command Line
```bash
# Parse PDFs to JSON
python -m racingpost_pdf parse \
  --inputs fixtures/WOL_*.pdf \
  --out meeting.json

# Skip validation (for testing)
python -m racingpost_pdf parse \
  --inputs fixtures/WOL_*.pdf \
  --out meeting.json \
  --no-validate
```

## Integration with Ingestion Endpoint

Update `POST /imports/{batch_id}/parse`:

```python
from racingpost_pdf import parse_meeting
from racingpost_pdf.validate import validate_meeting

@app.post("/imports/{batch_id}/parse")
async def parse_batch(batch_id: str):
    """Parse PDFs → validate → insert only if clean"""
    
    batch = await db.get_batch(batch_id)
    
    # 1. Parse PDFs
    report = parse_meeting(batch.pdf_paths)
    
    if not report.success:
        # Update batch status to rejected_bad_output
        await db.execute(
            """UPDATE import_batches 
               SET status = 'rejected_bad_output',
                   validation_errors = $1
               WHERE id = $2""",
            [e.message for e in report.errors],
            batch_id
        )
        
        return {
            "status": "rejected_bad_output",
            "errors": [e.dict() for e in report.errors],
            "message": "Parse failed validation gates. NO INSERT."
        }
    
    # 2. Insert to Supabase (only if clean)
    meeting = report.meeting
    await db.insert_meeting(meeting)
    
    # 3. Update batch status
    await db.execute(
        "UPDATE import_batches SET status = 'parsed' WHERE id = $1",
        batch_id
    )
    
    return {
        "status": "parsed",
        "races_count": len(meeting.races),
        "runners_count": sum(len(r.runners) for r in meeting.races)
    }
```

## Testing

### Golden Test Suite
Use Wolverhampton 2026-01-09 PDFs as golden fixtures.

```python
def test_parse_wolverhampton_meeting():
    """Golden test: parse Wolverhampton 2026-01-09"""
    from racingpost_pdf import parse_meeting
    
    pdf_paths = [
        "fixtures/WOL_20260109_XX.pdf",
        "fixtures/WOL_20260109_OR.pdf",
        "fixtures/WOL_20260109_TS.pdf",
        "fixtures/WOL_20260109_PM.pdf"
    ]
    
    report = parse_meeting(pdf_paths)
    
    assert report.success
    assert len(report.meeting.races) == 9
    
    # Check ages are valid (no 122!)
    for race in report.meeting.races:
        for runner in race.runners:
            assert 2 <= runner.age <= 15
    
    # Check distances mapped
    for race in report.meeting.races:
        assert race.distance_yards > 0
    
    # Check no placeholders
    for race in report.meeting.races:
        for runner in race.runners:
            assert runner.name not in {'TBD', 'RUNNER A'}
```

### Validation Gates Test
```python
def test_validation_gates():
    """Test that hard gates catch bad data"""
    from racingpost_pdf.validate import validate_meeting
    from racingpost_pdf.types import Meeting, Race, Runner
    
    # Bad age
    bad_meeting = Meeting(
        course_code="TEST",
        course_name="Test",
        meeting_date="2026-01-09",
        races=[
            Race(
                race_id="test_001",
                course="Test",
                off_time="13:30",
                distance_text="6f",
                distance_yards=1320,
                runners_count=1,
                runners=[
                    Runner(
                        runner_number=1,
                        name="Test Horse",
                        age=122  # ← impossible
                    )
                ]
            )
        ]
    )
    
    is_valid, errors = validate_meeting(bad_meeting)
    assert not is_valid
    assert any("Impossible age" in e for e in errors)
```

## Deterministic Output

The parser produces **deterministic output**:
- Same PDFs → Same JSON (byte-for-byte)
- No random IDs or timestamps in output
- Stable sort orders

This enables:
- Reliable testing with golden fixtures
- Detecting true changes vs. noise
- Reproducible pipelines

## Future Enhancements

1. **Fuzzy Name Matching:** Match runners across sources even with slight name variations
2. **OCR Fallback:** If pdfplumber fails, fall back to OCR with tesseract
3. **Historical Validation:** Check against historical data (e.g., known horse ages)
4. **Incremental Parsing:** Parse only changed races in update scenarios
5. **Multi-Meeting PDFs:** Handle PDFs with multiple meetings

## Troubleshooting

### "Distance not mapped"
Add missing distance to `DISTANCE_MAP` in `normalize.py`.

### "Impossible age"
Check parser logic in `parse_xx.py`. Ensure age extraction targets the correct line.

### "Runner count mismatch"
Check for Non-Runner markers. Verify runner parsing logic.

### "All-zero predictions"
Check prediction source data. May indicate upstream model failure.
