# Market Microstructure - Betfair

## Market as Weapon, Not Truth Oracle

### Core Principle
Market price is **crowd belief + strategic money**. It is not truth.

## Market Behaviour Types

### Organic Drift
**Definition:** Normal market digestion

**Characteristics:**
- Gradual price movement
- Reflects new information
- Liquidity consistent
- No panic

**Detection:**
- Smooth price curve
- Matched volume increases steadily
- No sudden spikes

### Informed Drift
**Definition:** Persistent weakness with corroborating negatives

**Characteristics:**
- Steady drift against horse
- Multiple negative factors
- Smart money exiting
- Liquidity drying up

**Detection:**
- Price moving 10%+ against
- Volume decreasing
- Negative news flow
- Form deterioration

### False Steam
**Definition:** Hype, decoy, liquidity games

**Characteristics:**
- Sudden price move
- Low matched volume
- No fundamental reason
- Often reverses

**Detection:**
- Price spike with low volume
- No news flow
- Reverses quickly
- Often on multiple runners

### Price Resilience
**Definition:** Horse refuses to drift despite negatives

**Characteristics:**
- Price stable against pressure
- Strong support at levels
- Intent smell
- Smart money holding

**Detection:**
- Negative form but price stable
- Strong support levels
- High matched volume
- Intent signals present

## Exchange Primitives

### Back/Lay Spread
**What it tells you:**
- **Tight spread** (1-2 ticks): High confidence, high liquidity
- **Wide spread** (5+ ticks): Uncertainty, low liquidity
- **No lay** (only back): Extreme confidence or manipulation

**Analysis:**
- Spread width = friction
- Tight = easy to trade
- Wide = caution

### Depth/Ladder
**What it shows:**
- **Order book depth** at each price
- **Spoofing detection** (large orders that disappear)
- **Held prices** (artificial support/resistance)

**Spoofing Detection:**
- Large order appears
- Small orders get filled
- Large order disappears
- Pattern repeats

**Held Prices:**
- Price refuses to move
- Large orders at levels
- Often on multiple horses
- Indicates intent

### Matched Volume
**What it indicates:**
- **Liquidity quality**
- **Market confidence**
- **Price discovery efficiency**

**Analysis:**
- High volume = efficient market
- Low volume = lies more
- Thin markets = manipulation risk
- Volume distribution = crowd belief

### BSP (Betfair Starting Price)
**What it is:**
- Strong probabilistic anchor
- Still not "truth"
- Reflects final crowd belief

**Usage:**
- Compare to model probability
- Identify mispricing
- Post-race validation

## Market Reading Framework

### Step 1: Liquidity Assessment
```
Liquidity Score = Matched Volume / Field Size / Time to Race
```

### Step 2: Price Action Analysis
```
Price Action = Drift Type + Spread Width + Depth Quality
```

### Step 3: Intent Corroboration
```
Market Intent = Price Resilience + Volume + Spread + News Flow
```

## Common Market Traps

### Trap 1: False Favourite
- Hype-driven price
- Pace vulnerability
- Poor condition fit
- Market overweights recent form

### Trap 2: Stable Decoy
- Multiple runners
- Public-supported wrong one
- Decoy sets pace, real contender closes
- Market focuses on decoy

### Trap 3: Jockey Trap
- Big-name rider on tactically dead profile
- Market overweights jockey name
- Horse can't win regardless

### Trap 4: Prep Run Disguise
- Conservative ride
- Wrong trip
- "Not asked" comments
- Market reads as poor ability

### Trap 5: Data Mirage
- Inflated figure from perfect setup
- Market reads as genuine ability
- Can't replicate conditions

## Output Requirements

### Must Include:
1. **Market behaviour read** (drift type, liquidity)
2. **Price action notes** (spread, depth, volume)
3. **Intent signals** (resilience, support levels)
4. **Threats** (traps, manipulation risk)
5. **Liquidity quality** (efficient vs thin market)

### Language:
- Market microstructure terms
- Probabilistic language
- Evidence-based
- No hype

## Acknowledgement
"Market Microstructure Loaded."
