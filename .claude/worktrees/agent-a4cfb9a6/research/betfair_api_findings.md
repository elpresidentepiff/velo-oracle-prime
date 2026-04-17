# Betfair Exchange API Research

## Overview

The Betfair Exchange API enables developers to build automated betting and trading systems.

### Key Components

1. **Betting API**
   - Navigation data
   - Odds and volumes retrieval
   - Bet placement operations
   - Back and Lay operations

2. **Accounts API**
   - Account balance retrieval
   - Account operations

3. **Exchange Stream API**
   - Low latency market data
   - Real-time price tracking
   - Order data streaming

### What You Can Do

- Build custom trading interfaces
- Automate trading strategies
- Access real-time market data
- Place back and lay bets programmatically
- Track odds movements
- Monitor account balance

### Pre-Race Trading Strategy

**The Opportunity:**
- Back horses at long odds (e.g., 20/1) days before race
- Monitor odds movements
- Lay the same horse when odds shorten (e.g., 10/1)
- Lock in guaranteed profit regardless of race outcome

**Example:**
- Day 1: Back £100 at 20/1 (potential return £2,000)
- Day 2: Odds shorten to 10/1
- Day 2: Lay £200 at 10/1 (liability £2,000)
- **Result:** Guaranteed profit whether horse wins or loses

### Next Steps

1. Get Betfair API credentials
2. Implement odds tracking system
3. Build odds movement predictor
4. Create automated back/lay trading agents


## Back-to-Lay Trading Strategy (CORE STRATEGY)

### How It Works

**Back-to-lay** is the foundation of Betfair Exchange trading. The strategy profits from odds shortening (decreasing).

**Process:**
1. **Back** a selection at higher odds (e.g., 20/1 or 5.0)
2. Wait for odds to shorten (e.g., to 10/1 or 3.0)
3. **Lay** the same selection at lower odds
4. **Result:** Guaranteed profit regardless of race outcome

### Example Calculation

**Scenario:** Horse trading
- **Day 1:** Back £100 at 20.0 (20/1)
  - Potential return: £2,000
- **Day 3:** Odds shorten to 10.0 (10/1)
- **Day 3:** Lay £200 at 10.0
  - Liability: £1,800

**Outcome:**
- **If horse wins:** Back bet wins £2,000, Lay bet loses £1,800 = **£200 profit**
- **If horse loses:** Back bet loses £100, Lay bet wins £200 = **£100 profit**

### Why Odds Shorten

**Strong Performance Indicators:**
- Horse shows good form in recent trials
- Positive trainer/jockey news
- Market confidence builds
- Heavy backing from informed traders

**Historical Tendencies:**
- Horse known to perform well at course/distance
- Favorable conditions (going, weather)
- Tactical advantage emerges
- Class advantage becomes apparent

### Best Scenarios for Back-to-Lay in Horse Racing

1. **Well-Handicapped Horses**
   - Identify horses on good marks
   - Back early at long odds
   - Wait for market to recognize value
   - Lay when odds shorten

2. **Class Droppers**
   - Horses dropping in class
   - Back before market adjusts
   - Lay when odds shorten

3. **Course Specialists**
   - Horses with strong course records
   - Back early before market recognizes
   - Lay when odds shorten

4. **Trainer Intent Signals**
   - Detect "go day" patterns
   - Back before market catches on
   - Lay when odds shorten

### Key Indicators for Success

**Back when you see:**
- Strong recent form
- Favorable matchup
- Market undervaluing selection
- Positive trainer/jockey news
- Class advantage
- Course/distance suitability

**Lay when:**
- Odds have shortened from back price
- Performance confirms thesis
- Market has corrected
- Target profit achieved

### Risk Management

**Advanced Tactics - Multiple Lays:**
Layer your exits for maximum profit:
- Back at 20.0
- Lay 30% at 15.0
- Lay 40% at 10.0
- Lay final 30% at 7.0
- **Result:** Maximize profit while managing risk

## How VÉLØ Oracle Enhances Back-to-Lay Trading

### VÉLØ's Unique Advantages

1. **Intent Engine**
   - Detects "go day" vs "no go day" patterns
   - Identifies when trainers are serious
   - Predicts which horses will be backed heavily

2. **Narrative Disruption Matrix**
   - Identifies horses whose story will change
   - Predicts market narrative shifts
   - Spots horses about to become favorites

3. **Behavioral Intelligence**
   - Models trainer psychology
   - Tracks jockey patterns
   - Detects syndicate activity

4. **Market Manipulation Radar**
   - Identifies artificial odds inflation
   - Detects late money patterns
   - Spots "show" patterns vs real intent

5. **Odds Movement Predictor**
   - Predicts which horses' odds will shorten
   - Calculates probability of odds movement
   - Identifies optimal entry and exit points

### The VÉLØ Edge

**Traditional traders:** React to odds movements after they happen
**VÉLØ traders:** Predict odds movements BEFORE they happen

This is the difference between:
- Following the market
- **Leading the market**

VÉLØ doesn't just predict race outcomes - it predicts the STORY that will move the market.
