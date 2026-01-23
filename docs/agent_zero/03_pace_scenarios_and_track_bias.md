# Pace Scenarios & Track Bias

## Pace Mechanics (Non-Negotiable)

### Race Shape as Skeleton
Pace is not optional. It's the skeleton of every race analysis.

## The Four Primary Scenarios

### S4: Controlled Theft
**Description:** Lone leader gets away uncontested

**Characteristics:**
- Single early leader
- No pressure from behind
- Can steal at will
- Often wins easily

**Detection:**
- One horse with clear early speed
- No other front-runners
- Field size small-medium
- Track favors front-runners

**Risk:**
- Pace collapse if pressured
- Track bias against
- Stamina limitations

### S3: Collapse & Sweep
**Description:** Contested pace collapses, closers win

**Characteristics:**
- Multiple early leaders (3+)
- Pace war in front
- Energy depletion
- Strong finishers capitalize

**Detection:**
- 3+ front-runners
- High early pace pressure
- Field size large
- Track favors closers

**Risk:**
- Lone leader survives
- Pace doesn't collapse
- Traffic for closers

### S2: Tactical Grind
**Description:** Honest pace, strongest finisher wins

**Characteristics:**
- 1-2 early leaders
- Moderate pressure
- Even energy distribution
- Best horse wins

**Detection:**
- Balanced field
- Moderate early pace
- No clear dominant speed
- Fair conditions

**Risk:**
- Pace too slow (S4)
- Pace too fast (S3)
- Bias interference

### S8: Chaos
**Description:** Incidents, weird rides, bias extremes, low-liquidity games

**Characteristics:**
- Traffic jams
- Jockey errors
- Track bias extremes
- Market manipulation

**Detection:**
- Large field
- Tight track
- Low liquidity
- Unusual price action

**Risk:**
- Unpredictable
- High variance
- Avoid unless edge is massive

## Pace Map Construction

### Step 1: Identify Early Leaders
```
Early Leaders = Horses with 2+ front-run attempts in last 5 runs
```

### Step 2: Pressure Points
```
Pressure = Count of early leaders within 2 lengths
```

### Step 3: Scenario Assignment
```
If Pressure = 0 → S4
If Pressure ≥ 3 → S3
If Pressure = 1-2 → S2
If Chaos factors → S8
```

## Track Bias Analysis

### Bias is Conditional
**Not:** "Good/bad draw"
**But:** "Good IF it interacts with pace and geometry"

### Sprint Tracks
- Positional wars
- Rail advantage often exists
- Field size critical
- Weather affects bias

### Staying Tracks
- Less draw-dependent
- Stamina over speed
- Track geometry matters
- Harrowing can flip bias

### Bias Detection
1. **Recent results** (last 5 races)
2. **Rail position** (inside vs outside)
3. **Weather** (wind, rain)
4. **Field size** (traffic impact)
5. **Harrowing** (track maintenance)

## Traffic Analysis

### When Traffic is Likely
- Large field (>12 runners)
- Tight track (sharp turns)
- Hold-up horses in big field
- Pace collapse scenarios

### Traffic Impact
- Hold-up horses: High risk
- Front-runners: Low risk
- Mid-pack: Medium risk

## Output Requirements

### Must Include:
1. **Likely early leaders** (who and why)
2. **Pressure points** (who contests whom)
3. **Scenario probability** (S2/S3/S4/S8 %)
4. **Track bias relevance** (conditional analysis)
5. **Traffic likelihood** (field size, track type)
6. **Closers' realistic chance** (will they get a run?)

### Language:
- Scenario-based thinking
- Probabilities, not certainties
- Conditional statements
- Risk bands

## Acknowledgement
"Pace Scenarios & Track Bias Loaded."
