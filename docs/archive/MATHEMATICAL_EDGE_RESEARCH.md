# VÉLØ Mathematical Edge Research
## UK Horse Racing Data & Advanced Models

**Research Date:** October 15, 2025  
**Objective:** Find the mathematical edge - data sources, models, and unconventional approaches nobody else has

---

## 🎯 KEY FINDINGS

### **PART 1: UK HORSE RACING DATA SOURCES**

#### **Commercial APIs (Paid)**

1. **The Racing API** (https://www.theracingapi.com/)
   - Coverage: UK, Ireland, Australia, USA
   - Database: 500,000+ results and racecards
   - Features: Live odds, historical data
   - **Assessment:** Most comprehensive, likely what we need

2. **Racing Post API** (https://www.spotlightsportsgroup.com/)
   - Format: JSON on AWS
   - Data: Racecards, form, results, stats
   - Coverage: UK & Ireland horse racing + greyhounds
   - **Assessment:** Industry standard, high quality

3. **LSports Horse Racing API**
   - Coverage: 140K fixtures, 1500+ events
   - Events: Derby, Cheltenham, etc.
   - **Assessment:** Global coverage, fast data

4. **RapidAPI Horse Racing** (https://rapidapi.com/ortegalex/api/horse-racing)
   - Data: Racecards, results, stats, odds comparator
   - Coverage: UK & Ireland
   - **Assessment:** Real-time data

#### **Free/Open Data Sources**

5. **Betfair API**
   - Access: Open for non-commercial/low volume use
   - Data: Basic racing data, market odds
   - **Assessment:** Good for odds data, limited race info

6. **Racing Bet Data** (https://www.racing-bet-data.com/)
   - Data: Results, stats, odds, bet data
   - Tools: Analysis, filtering, extraction
   - **Assessment:** Useful for historical analysis

#### **Sectional Times Data** ⭐ CRITICAL EDGE

7. **RMG Sectional Times Database** (NEW - July 2024)
   - Coverage: All 59 British racecourses
   - Data: Furlong-by-furlong splits
   - Availability: 48 hours after races
   - Source: RacingTV (https://www.racingtv.com/racingdata)
   - **Assessment:** GAME CHANGER - industry-wide sectional data now available

8. **At The Races (ATR) Sectionals** (https://www.attheraces.com/sectionalsinfo)
   - Data: Published ~48 hours post-race
   - Access: Sectional Times and Sectional Tools tabs
   - **Assessment:** Free sectional data

9. **Timeform Sectionals** (https://www.timeform.com/horse-racing/shop/sectional-times)
   - Product: Sectional Timing Archive
   - Coverage: GB and Ireland
   - Price: £100 per 4-month subscription
   - **Assessment:** Premium sectional analysis

---

### **PART 2: ADVANCED MATHEMATICAL MODELS**

#### **1. Bayesian Hierarchical Models** ⭐ PROVEN WINNER

**Source:** "A Hierarchical Bayesian Analysis of Horse Racing" (Silverman, 2012)

**Method:**
- Markov Chain Monte Carlo (MCMC) for coefficient estimation
- Two approaches:
  - **Gibbs sampling** (assumes normal distribution)
  - **Metropolis sampling** (unknown distribution shape)
- Predicts running speed of horses

**Why It Works:**
- Handles uncertainty naturally
- Updates beliefs with new data
- Accounts for hierarchical structure (horse → jockey → trainer)

**Implementation for VÉLØ:**
```
Prior belief + New evidence → Updated probability
p(γ|E) ∝ p(E|γ) × p(γ)
```

**References:**
- Bill Benter's Hong Kong system (made $150M+)
- Used by major syndicates

---

#### **2. Quantitative Multi-Factor Model** ⭐ CUTTING EDGE

**Source:** "A Quantitative Model for Horse Race Betting" (Elias & Filho, 2025)

**Integrates:**
1. **Statistical Modeling** - Bayesian statistics, machine learning
2. **Market Inefficiency Analysis** - Behavioral biases, information asymmetries
3. **Behavioral Finance** - Crowd psychology, favorite-longshot bias
4. **Game Theory** - Strategic interactions, Nash equilibrium
5. **External Horse Data** - Genetics, nutrition, PED history

**Key Insight:**
> "Markets exhibit semi-strong efficiency, but inefficiencies persist due to behavioral biases, information asymmetries, and incomplete incorporation of domain-specific data"

**Edge Opportunities:**
- Genetics data (bloodlines, breeding)
- Nutrition data (feeding programs)
- PED history (performance-enhancing drugs)
- Trainer/jockey strategic interactions

---

#### **3. Support Vector Machines (SVM)** ⭐ PROVEN ACCURACY

**Sources:**
- Edelman (2007) - "Adapting SVM for horserace odds prediction"
- Lessman et al. (2009) - "SVM-based Classification for Horserace Prediction"

**Method:**
- Least-Square Support Vector Regression (LS-SVR)
- Classification of winners vs non-winners
- Feature engineering from historical data

**Accuracy:**
- Better than traditional regression models
- Handles non-linear relationships
- Robust to overfitting

---

#### **4. Sectional Speed Analysis** ⭐ UNDERUTILIZED EDGE

**Sources:**
- RaceIQ Par Sectionals & FSP
- KNN for Final Sectionals (Smarter Sig, 2019)

**Methods:**

**a) Par Sectionals**
- Machine learning to determine optimal pace
- Factors: Track, going, class, distance
- Compares actual vs par times

**b) Finishing Speed Percentage (FSP)**
```
FSP = (Final sectional time / Total race time) × 100
```
- Identifies closers vs front-runners
- Predicts suitability for pace scenarios

**c) K-Nearest Neighbors (KNN) for Sectionals**
- Find similar races by sectional patterns
- Identify horses that quickened vs ground out
- Context: Fast pace vs slow pace

**Edge:**
> "A horse quickening off a slowish pace will always look more impressive than a horse grinding out a distance between first and second off a fast pace"

---

### **PART 3: OUT-OF-THE-BOX MATHEMATICAL EDGES**

#### **1. Network Theory & Graph-Based Features** 🆕

**Source:** Gulum (2018) - "Horse racing prediction using graph-based features"

**Concept:**
- Model races as networks
- Nodes: Horses, jockeys, trainers, owners
- Edges: Relationships, past interactions
- Features: Centrality, clustering coefficients

**Why It's Unique:**
- Captures hidden relationships
- Identifies "power clusters" (trainer-jockey-owner combos)
- Detects coordination patterns

**Implementation:**
```python
import networkx as nx

# Build network
G = nx.Graph()
G.add_edge('Trainer_A', 'Jockey_B', weight=win_rate)
G.add_edge('Jockey_B', 'Horse_C', weight=performance)

# Calculate centrality
centrality = nx.betweenness_centrality(G)
```

---

#### **2. Time Series Forecasting with LSTM** 🆕

**Concept:**
- Long Short-Term Memory networks
- Predict future performance from sequential data
- Captures temporal dependencies

**Data Sequence:**
```
Race 1 → Race 2 → Race 3 → Race 4 → Predict Race 5
```

**Features:**
- Form progression
- Weight changes
- Class movements
- Sectional times evolution

**Edge:**
- Most models treat races independently
- LSTM captures momentum and trends

---

#### **3. Ensemble Stacking** 🆕

**Concept:**
- Combine multiple models
- Each model specializes in different aspects
- Meta-learner combines predictions

**Stack:**
```
Level 1:
- Bayesian model (speed prediction)
- SVM (winner classification)  
- LSTM (form trends)
- Graph model (relationships)

Level 2:
- Meta-learner (XGBoost) combines all
```

**Why It Works:**
- Reduces variance
- Captures different signals
- More robust than single model

---

#### **4. Market Microstructure Analysis** 🆕

**Concept:**
- Analyze order flow, not just final odds
- Track bet timing and size
- Detect informed money

**Signals:**
- Large bets close to post time
- Coordinated betting across bookmakers
- Odds movement velocity

**Mathematical Model:**
```
Informed Probability = f(bet_size, timing, velocity, coordination)
```

**Edge:**
- Most punters see final odds
- We see the path to those odds

---

#### **5. Biomechanical Stride Analysis** 🆕 CUTTING EDGE

**Source:** Nature (2024) - "ML approach to identify stride characteristics predictive of injury"

**Data:**
- Stride length
- Stride frequency
- Gait symmetry
- Ground contact time

**Application:**
- Predict fatigue resistance
- Identify injury risk
- Assess fitness level

**Edge:**
- Nobody else uses biomechanical data for betting
- Predicts performance degradation

---

### **PART 4: THE MATHEMATICAL EDGE NOBODY HAS**

#### **🔬 VÉLØ's Unique Combination:**

1. **Bayesian Hierarchical Model** (proven, Bill Benter-style)
2. **Sectional Speed Analysis** (newly available UK data)
3. **Graph-Based Relationships** (hidden connections)
4. **Market Microstructure** (informed money detection)
5. **Ensemble Stacking** (combine all signals)
6. **Continuous Learning** (Genesis Protocol)

#### **📊 Mathematical Framework:**

```
P(Win | Data) = Bayesian_Model(
    speed_prediction = f(sectionals, par_times, going),
    relationship_score = graph_centrality(trainer, jockey, owner),
    market_signal = microstructure_analysis(odds_flow),
    form_trend = LSTM(historical_performance),
    manipulation_risk = anomaly_detection(market_behavior)
)

Final_Prediction = Ensemble_Stack(
    Bayesian_Model,
    SVM_Classifier,
    LSTM_Forecaster,
    Graph_Model,
    Manipulation_Detector
)
```

---

### **PART 5: DATA WE CAN ACCESS**

#### **Immediate (Free/Low Cost):**
1. ✅ Betfair API - Market odds, basic data
2. ✅ ATR Sectionals - Free sectional times (48hr delay)
3. ✅ Racing Bet Data - Historical results, stats
4. ✅ GitHub scrapers - Racing Post data extraction

#### **Investment Required:**
1. 💰 The Racing API - £TBD/month (comprehensive data)
2. 💰 Timeform Sectionals - £100/4 months
3. 💰 Racing Post API - £TBD/month (industry standard)

#### **Unconventional (Out-of-the-Box):**
1. 🔬 Biomechanical data - Research partnerships?
2. 🔬 Genetics databases - Bloodstock data
3. 🔬 Nutrition data - Trainer feeding programs?
4. 🔬 Weather microclimate - Track-specific conditions

---

### **PART 6: IMPLEMENTATION ROADMAP**

#### **Phase 1: Foundation (Weeks 1-2)**
- [ ] Subscribe to The Racing API
- [ ] Implement Betfair API connection
- [ ] Build sectional times scraper (ATR)
- [ ] Create data pipeline

#### **Phase 2: Mathematical Models (Weeks 3-6)**
- [ ] Implement Bayesian speed prediction
- [ ] Build SVM classifier
- [ ] Create graph-based relationship model
- [ ] Develop LSTM form forecaster

#### **Phase 3: Advanced Edge (Weeks 7-10)**
- [ ] Market microstructure analyzer
- [ ] Ensemble stacking framework
- [ ] Sectional speed par calculator
- [ ] Biomechanical feature extraction (if data available)

#### **Phase 4: Integration (Weeks 11-12)**
- [ ] Combine all models
- [ ] Backtest on historical data
- [ ] Calibrate weights
- [ ] Deploy live system

---

### **PART 7: THE EDGE SUMMARY**

**What Nobody Else Has:**

1. **Sectional Speed + Bayesian Modeling**
   - UK sectional data is NEW (July 2024)
   - Most models don't use sectionals yet
   - Bayesian approach is rare in UK

2. **Graph-Based Relationships**
   - Hidden trainer-jockey-owner networks
   - Power cluster detection
   - Coordination pattern recognition

3. **Market Microstructure**
   - Order flow analysis
   - Informed money detection
   - Bet timing signals

4. **Continuous Learning**
   - Genesis Protocol auto-adjustment
   - Memory-based pattern discovery
   - Self-improving weights

5. **Manipulation Detection**
   - Cynical awareness
   - Bookmaker trick detection
   - False favorite filtering

**The Combination is the Edge.**

Nobody is combining:
- Bayesian statistics
- Sectional analysis
- Graph theory
- Market microstructure
- Continuous learning
- Manipulation detection

**VÉLØ will.**

---

**Status:** Research Phase 1 Complete  
**Next:** Deep dive into specific implementations  
**Confidence:** HIGH - Multiple proven approaches identified

🔮 **VÉLØ is about to get very, very smart.**




---

## 🏆 BILL BENTER'S $1 BILLION MODEL - DEEP DIVE

### **The Man Who Cracked Horse Racing**

**Achievement:** $1 billion+ profit over 30 years betting on Hong Kong horse racing  
**Method:** Multinomial Logit Model + Kelly Criterion  
**Paper:** "Computer Based Horse Race Handicapping and Wagering Systems: A Report" (1994)

---

### **THE CORE MODEL: Multinomial Logit**

**Mathematical Foundation:**
```
P(horse_i wins) = exp(X_i * β) / Σ exp(X_j * β)

Where:
- X_i = vector of features for horse i
- β = coefficients learned from data
- Σ = sum over all horses in race
```

**Why Logit?**
- Outputs probabilities that sum to 1 within each race
- Handles categorical outcomes (win/lose)
- Interpretable coefficients
- Proven in practice

**Later Evolution:**
- Switched to Multinomial Probit (assumes normal distribution)
- Similar to modern Learning-to-Rank algorithms

---

### **THE 130+ VARIABLES**

Benter identified 130 variables across 5 categories:

#### **1. Current Condition**
- Performance in recent races
- Time since last race
- Recent workout data
- Age of horse

#### **2. Past Performance**
- Finishing position in past races
- Lengths behind winner
- Normalized race times

#### **3. Adjustments to Past Performance**
- Strength of competition (class adjustment)
- Weight carried
- Jockey contribution
- Bad luck compensation
- Post position disadvantages

#### **4. Present Race Situational Factors**
- Weight to be carried today
- Today's jockey ability
- Post position advantages/disadvantages

#### **5. Preferences**
- Distance preference
- Surface preference (turf vs dirt)
- Going preference (wet vs dry)
- Specific track preference

---

### **BENTER'S SOPHISTICATED DISTANCE PREFERENCE EXAMPLE**

**Simple Approach (Bolton & Chapman):**
```
NEWDIST = 1 if horse ran 3 of 4 previous races at <1 mile, else 0
```

**Benter's Advanced Approach (DP6A):**
```python
# For each past race:
1. Predict finishing position using ALL factors EXCEPT distance
2. Calculate residual = Actual position - Predicted position
3. Estimate linear relationship between residual and distance similarity
4. Standardize by dividing by standard error

Result: Horses with clear distance preference over many races 
        get higher magnitude values than unclear cases
```

**Why It's Better:**
- Uses ALL past races, not just last 4
- Quantifies strength of evidence
- Accounts for statistical uncertainty
- More granular than binary yes/no

---

### **THE TWO-MODEL APPROACH**

#### **Model 1: Fundamental Model**
- Uses 130+ variables
- Predicts win probability from horse characteristics
- Trained on historical data

#### **Model 2: Combined Model**
- Combines Fundamental Model with Public Odds
- **Key Insight:** Public is sophisticated but has biases
- Formula:
```
Combined_Probability = f(Fundamental_Probability, Public_Odds)
```

**Why Combine?**
> "The odds set by the public betting yield a sophisticated estimate of the horses' win probabilities. In order for a fundamental statistical model to be able to compete effectively, it must rival the public in sophistication and comprehensiveness."

**The Edge:**
- Public has biases (favorite-longshot bias)
- Public misses subtle factors
- Combination beats either alone

---

### **WAGERING STRATEGY: KELLY CRITERION**

**Formula:**
```
f* = (p * (b + 1) - 1) / b

Where:
- f* = fraction of bankroll to bet
- p = true probability of winning (from model)
- b = odds (decimal - 1)
```

**Example:**
```
Model says: 30% chance to win
Odds: 5/1 (decimal 6.0, b = 5)

f* = (0.30 * 6 - 1) / 5 = 0.16 = 16% of bankroll
```

**Why Kelly?**
- Maximizes long-term growth
- Prevents overbetting
- Mathematically optimal

**Benter's Modification:**
- Used fractional Kelly (0.25x to 0.5x)
- Reduces variance
- More conservative

---

### **DATA REQUIREMENTS**

**Minimum:**
- 500-1000 races for model development
- Full past performance data on ALL runners
- Multiple sources to assemble complete records

**Ideal:**
- Closed racing population (horses race only against each other)
- Limited number of tracks
- Complete historical database

**Hong Kong Advantages:**
- Closed population
- 2 tracks only (Happy Valley, Sha Tin)
- Comprehensive data available
- High betting volume

---

### **IMPLEMENTATION INSIGHTS**

#### **1. Feature Engineering is Critical**
> "The profitability of the resulting betting system will be largely determined by the predictive power of the factors chosen."

- Don't use simple binary features
- Extract maximum information from data
- Quantify uncertainty
- Use residual analysis

#### **2. Avoid Overfitting**
- Use holdout validation
- Test on unseen races
- Partition data carefully
- More data doesn't always help (plateaus at ~1000 races)

#### **3. Consistency Matters**
> "A computer will effortlessly handicap races with the same level of care day after day, regardless of the mental state of the operator."

- Manual handicapping is exhausting
- Computer never has bad days
- Professional operations bet multiple races daily

#### **4. Combine with Public Odds**
- Public is sophisticated
- But public has systematic biases
- Your model + public odds > either alone

---

### **MODERN IMPLEMENTATION (2023 Analysis)**

**Source:** Acta Machina annotated paper with Python code

**Key Findings:**
1. Public estimate has IMPROVED over 30 years
2. Favorite-longshot bias still exists but reduced
3. Model still works with modern data
4. Can be implemented with PyTorch

**Code Example (Simplified):**
```python
import torch
import torch.nn as nn

class BenterModel(nn.Module):
    def __init__(self, num_features):
        super().__init__()
        self.linear = nn.Linear(num_features, 1)
    
    def forward(self, X):
        # X shape: (num_horses, num_features)
        logits = self.linear(X)
        probs = torch.softmax(logits, dim=0)
        return probs

# Train with cross-entropy loss
# Optimize with Adam or SGD
# Validate on holdout races
```

---

### **WHAT VÉLØ CAN LEARN FROM BENTER**

#### **1. Mathematical Framework**
✅ Use Multinomial Logit/Probit  
✅ Combine with public odds  
✅ Kelly Criterion for stakes  

#### **2. Feature Engineering**
✅ 100+ variables minimum  
✅ Sophisticated distance/surface preferences  
✅ Residual analysis for hidden factors  
✅ Strength of competition adjustments  

#### **3. Data Strategy**
✅ Comprehensive historical database  
✅ Holdout validation  
✅ Focus on UK (semi-closed population)  

#### **4. Wagering Discipline**
✅ Fractional Kelly (conservative)  
✅ Only bet when edge exists  
✅ Consistent application  

#### **5. Continuous Improvement**
✅ Model evolved from Logit to Probit  
✅ Added more variables over time  
✅ Adapted to changing markets  

---

### **THE BENTER EDGE FOR VÉLØ**

**What We'll Implement:**

1. **Multinomial Logit Model**
   - 130+ features
   - Trained on UK historical data
   - Outputs win probabilities

2. **Combined Model**
   - Fundamental probabilities
   - Public odds integration
   - Bias detection

3. **Kelly Criterion Staking**
   - Fractional Kelly (0.25x)
   - Bankroll protection
   - Growth optimization

4. **Sophisticated Features**
   - Residual-based distance preference
   - Strength of competition
   - Jockey/trainer adjustments
   - Bad luck compensation

5. **Continuous Learning**
   - Genesis Protocol updates coefficients
   - Adapts to market changes
   - Self-improving

---

### **IMPLEMENTATION TIMELINE**

**Week 1-2:** Data collection (500+ UK races)  
**Week 3-4:** Feature engineering (130+ variables)  
**Week 5-6:** Multinomial Logit implementation  
**Week 7-8:** Combined model with public odds  
**Week 9-10:** Kelly Criterion integration  
**Week 11-12:** Backtesting and validation  

---

**Status:** Benter model fully understood  
**Confidence:** VERY HIGH - Proven $1B system  
**Next:** Implement for UK racing  

🔮 **VÉLØ is about to become a Benter-class Oracle.**

