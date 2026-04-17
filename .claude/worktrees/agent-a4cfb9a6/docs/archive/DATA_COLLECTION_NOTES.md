# VÉLØ Data Collection Notes
## ATR Sectionals & UK Racing Data

**Created:** October 15, 2025

---

## 🎯 ATR SECTIONALS DATA

### **What We Know:**

**Coverage:**
- 12 Flat racecourses in UK
- Tracks: Bath, Brighton, Chepstow, Chester, Doncaster, Ffos Las, Lingfield, Newcastle, Southwell, Windsor, Wolverhampton, Yarmouth
- Data published 48 hours after races

**Access Method:**
- Available on Race Result pages at attheraces.com
- Two tabs: "Sectional Times" and "Sectional Tools"
- Free to access (no subscription required)

**Data Available:**

1. **Sectional Times Grid**
   - Individual furlong-by-furlong times for each horse
   - Color-coded (blue/green/yellow/orange/red) for pace analysis
   - Shows how race unfolded

2. **Sectional Tools:**
   - Energy Distribution Chart
   - Sectional Speeds (MPH for early/mid/late)
   - Efficiency Grade (A-F scale)
   - Finishing Speed % (FSP)

3. **Pace Analysis Bar**
   - At-a-glance race pace visualization
   - Race Finishing Speed Percentage

**Key Metrics:**

- **Finishing Speed %:** (Final sectional / Total time) * 100
  - FSP > 20% = Strong closer
  - FSP 15-20% = Moderate closer
  - FSP < 15% = Front-runner

- **Efficiency Grade:** A-F scale for energy distribution

- **Optimum Figures:** Calculated by Simon Rowlands (Timeform expert)

---

## 📊 DATA COLLECTION STRATEGY

### **Phase 1: Manual Collection (Immediate)**

**Approach:**
1. Visit attheraces.com/results daily
2. Click on each race result
3. Navigate to "Sectional Times" and "Sectional Tools" tabs
4. Extract data manually
5. Store in database

**Limitations:**
- 48-hour delay
- Manual effort required
- Only 12 flat tracks

### **Phase 2: Automated Scraper (Week 1)**

**Build Python scraper to:**
1. Fetch daily results from ATR
2. Extract sectional data from each race
3. Parse HTML/JSON for:
   - Furlong times
   - FSP values
   - Efficiency grades
   - Pace analysis
4. Store in PostgreSQL database

**Technical Approach:**
```python
import requests
from bs4 import BeautifulSoup
import json

def scrape_atr_sectionals(date, track):
    # Navigate to results page
    url = f"https://www.attheraces.com/results/{date}/{track}"
    
    # Find sectional data tabs
    # Extract JSON or parse HTML tables
    # Return structured data
    pass
```

### **Phase 3: Historical Backfill (Week 2)**

**Goal:** Collect 2+ years of sectional data

**Method:**
- Loop through past dates
- Scrape all available sectionals
- Build comprehensive historical database

**Expected Data Volume:**
- 12 tracks
- ~5 races/day/track average
- ~60 races/day total
- ~22,000 races/year
- ~44,000 races for 2 years

---

## 🔍 SEARCHING FOR HISTORICAL UK RACING DATA

### **Targets:**

**1. GitHub Repositories**
- Search for: "UK horse racing data", "racing results dataset", "horse racing historical"
- Look for CSV/JSON files with 10+ years of data

**2. Kaggle Datasets**
- Horse racing competitions
- UK racing datasets
- Betting datasets

**3. Academic Sources**
- Research papers with datasets
- University repositories
- Open data initiatives

**4. Racing APIs (Free Tiers)**
- Check for historical data access
- Free trials or limited free data

---

## 📁 DATABASE SCHEMA (DRAFT)

```sql
CREATE TABLE sectional_data (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    date DATE,
    track VARCHAR(50),
    race_number INT,
    horse_name VARCHAR(100),
    finishing_position INT,
    
    -- Furlong times (up to 16 furlongs)
    furlong_1 DECIMAL(5,2),
    furlong_2 DECIMAL(5,2),
    furlong_3 DECIMAL(5,2),
    furlong_4 DECIMAL(5,2),
    furlong_5 DECIMAL(5,2),
    furlong_6 DECIMAL(5,2),
    furlong_7 DECIMAL(5,2),
    furlong_8 DECIMAL(5,2),
    furlong_9 DECIMAL(5,2),
    furlong_10 DECIMAL(5,2),
    furlong_11 DECIMAL(5,2),
    furlong_12 DECIMAL(5,2),
    furlong_13 DECIMAL(5,2),
    furlong_14 DECIMAL(5,2),
    furlong_15 DECIMAL(5,2),
    furlong_16 DECIMAL(5,2),
    
    -- Calculated metrics
    finishing_speed_pct DECIMAL(5,2),
    efficiency_grade CHAR(1),
    early_speed_mph DECIMAL(5,2),
    mid_speed_mph DECIMAL(5,2),
    late_speed_mph DECIMAL(5,2),
    
    -- Race context
    total_time DECIMAL(6,2),
    race_finishing_speed_pct DECIMAL(5,2),
    pace_scenario VARCHAR(20),  -- HOT/MODERATE/SLOW
    
    -- Metadata
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_race_id ON sectional_data(race_id);
CREATE INDEX idx_date ON sectional_data(date);
CREATE INDEX idx_track ON sectional_data(track);
CREATE INDEX idx_horse_name ON sectional_data(horse_name);
```

---

## ✅ NEXT STEPS

**Immediate (Today):**
1. ✅ Understand ATR data structure
2. ⏳ Build basic scraper
3. ⏳ Test on recent races
4. ⏳ Search for historical datasets

**This Week:**
1. Complete ATR scraper
2. Set up PostgreSQL database
3. Start collecting daily data
4. Find and download historical UK racing data

**Next Week:**
1. Backfill 2+ years of sectionals
2. Integrate with VÉLØ Oracle
3. Build sectional analysis module
4. Test on Punchestown-style races

---

**Status:** In progress - ATR structure understood  
**Blocker:** Need to build scraper and find historical data sources  
**Priority:** HIGH - Free data source, critical for pace analysis




---

## 🎉 MAJOR FINDS - UK RACING HISTORICAL DATA

### **1. Kaggle Dataset: UK/Ireland 2015-2025** ⭐⭐⭐⭐⭐

**URL:** https://www.kaggle.com/datasets/deltaromeo/horse-racing-results-ukireland-2015-2025

**Coverage:**
- **10 years of data** (2015-2025)
- UK & Ireland races
- **Updated monthly** (last update: Oct 4, 2025)
- SQLite3 database + CSV format

**Data Fields (42 columns):**
- Date, course, race_id, off time
- Race name, type, class, pattern, rating_band
- Age band, sex restrictions
- Distance, going, number of runners
- Horse details: name, age, sex, weight
- Performance: position, draw, buttons, time
- Odds: starting price (SP)
- Jockey, trainer, owner
- Prize money
- Ratings: OR (Official Rating), RPR (Racing Post Rating), TS (Topspeed)
- Breeding: sire, dam, damsire
- **Comments** (in-running commentary!)

**Quality:**
- Clean, structured data
- Consistent schema
- Regularly updated
- Free to download

**Download Method:**
- Sign up for Kaggle account (free)
- Download raceform.db (SQLite3 file)
- Can query directly with SQL

---

### **2. Kaggle Dataset: UK/Ireland 2005-2019** ⭐⭐⭐⭐

**URL:** https://www.kaggle.com/datasets/sheikhbarabas/horse-racing-results-uk-ireland-2005-to-2019

**Coverage:**
- **14 years of data** (2005-2019)
- UK & Ireland
- **National Hunt (Jumps) only**
- CSV format (333 MB)

**Data Fields (42 columns):**
- Similar structure to 2015-2025 dataset
- Comprehensive race and horse details

**Quality:**
- Well-structured
- Large dataset
- No longer updated (last update 5 years ago)

**Download Method:**
- Sign up for Kaggle account
- Download all_races05_19.csv

---

### **3. GitHub: rpscrape** ⭐⭐⭐⭐⭐

**URL:** https://github.com/joenano/rpscrape

**What It Does:**
- **Scrapes Racing Post** for historical results
- **Scrapes racecards** for upcoming races
- Command-line tool
- Python-based

**Features:**
- Scrape by region or specific course
- Scrape by year or date range
- Scrape flat or jumps
- Customizable data fields
- JSON output for racecards
- CSV output for results
- **Includes Betfair SP data**

**Data Fields (Customizable):**
- All standard race/horse info
- In-running comments
- Betfair starting price
- Sectional times (if available)

**Usage:**
```bash
# Install
git clone https://github.com/joenano/rpscrape.git
cd rpscrape/scripts
pip3 install requests tomli orjson jarowinkler aiohttp lxml

# Scrape examples
python3 rpscrape.py
[rpscrape]> ire 2020-2024 flat
[rpscrape]> 2 2015-2024 jumps  # Ascot jumps
[rpscrape]> -d 2024/10/15 gb   # Today's GB races

# Scrape racecards
python3 racecards.py today
```

**Advantages:**
- Free and open source
- Active maintenance (last commit 3 weeks ago)
- Can scrape ANY date range
- Can backfill missing data
- Includes Betfair odds

**Limitations:**
- Requires Racing Post to stay accessible
- May need maintenance if site changes
- Rate limiting needed to avoid blocks

---

## 📊 COMBINED DATA STRATEGY

### **Phase 1: Download Kaggle Datasets (Immediate)**

**Action Plan:**
1. Create Kaggle account
2. Download both datasets:
   - 2015-2025 (10 years, all racing)
   - 2005-2019 (14 years, jumps only)
3. Import into PostgreSQL
4. Merge and deduplicate

**Expected Data:**
- **~300,000+ races** from 2005-2025
- **~2 million+ individual horse performances**
- 20 years of UK/Ireland racing history

### **Phase 2: Deploy rpscrape (Week 1)**

**Action Plan:**
1. Clone and install rpscrape
2. Configure for VÉLØ needs
3. Set up daily cron job to scrape:
   - Yesterday's results
   - Today's racecards
4. Backfill any gaps in Kaggle data

**Use Cases:**
- Daily updates
- Real-time racecard data
- Betfair SP comparison
- Fill missing sectionals

### **Phase 3: ATR Sectionals Scraper (Week 2)**

**Action Plan:**
1. Build custom scraper for ATR
2. Scrape sectional data for 12 flat tracks
3. Match with Kaggle/rpscrape data by race_id
4. Store in separate sectionals table

---

## 🗄️ ENHANCED DATABASE SCHEMA

```sql
-- Main races table (from Kaggle + rpscrape)
CREATE TABLE races (
    race_id VARCHAR(50) PRIMARY KEY,
    date DATE,
    course VARCHAR(100),
    off_time TIME,
    race_name TEXT,
    type VARCHAR(20),  -- Flat, Chase, Hurdle
    class VARCHAR(10),
    pattern VARCHAR(50),  -- Grade 1, 2, 3, Listed
    rating_band VARCHAR(20),
    age_band VARCHAR(20),
    sex_rest VARCHAR(20),
    distance VARCHAR(20),
    going VARCHAR(50),
    num_runners INT,
    prize_money INT,
    race_finishing_speed_pct DECIMAL(5,2),
    pace_scenario VARCHAR(20)
);

-- Horse performances table
CREATE TABLE performances (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50) REFERENCES races(race_id),
    horse_name VARCHAR(100),
    age INT,
    sex CHAR(1),
    weight VARCHAR(10),
    position INT,
    draw INT,
    ovr_btn DECIMAL(5,2),  -- Overall beaten distance
    btn DECIMAL(5,2),  -- Beaten by next horse
    time VARCHAR(20),
    sp VARCHAR(20),  -- Starting price
    betfair_sp DECIMAL(10,2),  -- Betfair SP
    jockey VARCHAR(100),
    trainer VARCHAR(100),
    owner TEXT,
    official_rating INT,
    rpr INT,  -- Racing Post Rating
    topspeed INT,
    sire VARCHAR(100),
    dam VARCHAR(100),
    damsire VARCHAR(100),
    comment TEXT  -- In-running commentary
);

-- Sectional data table (from ATR)
CREATE TABLE sectionals (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50) REFERENCES races(race_id),
    horse_name VARCHAR(100),
    -- Furlong times
    f1 DECIMAL(5,2), f2 DECIMAL(5,2), f3 DECIMAL(5,2),
    f4 DECIMAL(5,2), f5 DECIMAL(5,2), f6 DECIMAL(5,2),
    f7 DECIMAL(5,2), f8 DECIMAL(5,2), f9 DECIMAL(5,2),
    f10 DECIMAL(5,2), f11 DECIMAL(5,2), f12 DECIMAL(5,2),
    -- Metrics
    finishing_speed_pct DECIMAL(5,2),
    efficiency_grade CHAR(1),
    early_speed_mph DECIMAL(5,2),
    mid_speed_mph DECIMAL(5,2),
    late_speed_mph DECIMAL(5,2)
);

-- Racecards table (from rpscrape daily)
CREATE TABLE racecards (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(50),
    date DATE,
    course VARCHAR(100),
    off_time TIME,
    race_name TEXT,
    distance VARCHAR(20),
    going VARCHAR(50),
    horse_name VARCHAR(100),
    jockey VARCHAR(100),
    trainer VARCHAR(100),
    weight VARCHAR(10),
    draw INT,
    age INT,
    official_rating INT,
    last_run_date DATE,
    form VARCHAR(50),
    odds DECIMAL(10,2),
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_race_date ON races(date);
CREATE INDEX idx_race_course ON races(course);
CREATE INDEX idx_perf_horse ON performances(horse_name);
CREATE INDEX idx_perf_jockey ON performances(jockey);
CREATE INDEX idx_perf_trainer ON performances(trainer);
CREATE INDEX idx_sectional_horse ON sectionals(horse_name);
```

---

## ✅ IMMEDIATE ACTION PLAN

**Today:**
1. ✅ Create Kaggle account
2. ✅ Download 2015-2025 dataset
3. ✅ Download 2005-2019 dataset
4. ⏳ Set up PostgreSQL database
5. ⏳ Import Kaggle data

**Tomorrow:**
1. Clone rpscrape
2. Test scraping today's races
3. Set up daily automation
4. Begin ATR scraper development

**This Week:**
1. Complete database import
2. Verify data quality
3. Build data analysis queries
4. Integrate with VÉLØ Oracle

---

## 🎯 DATA GOLDMINE SUMMARY

**What We Have Access To:**

1. **300,000+ historical races** (2005-2025)
2. **2 million+ horse performances**
3. **Free sectional data** (12 flat tracks)
4. **Daily racecard scraper**
5. **Betfair SP data**
6. **In-running comments**
7. **Breeding information**
8. **Trainer/jockey stats**

**This is EXACTLY what Bill Benter had in Hong Kong.**

**We now have the data foundation to build a billion-dollar Oracle.** 🔮💰

---

**Status:** MAJOR BREAKTHROUGH - Data sources identified  
**Next:** Download and import immediately  
**Priority:** CRITICAL - This is the foundation of everything

