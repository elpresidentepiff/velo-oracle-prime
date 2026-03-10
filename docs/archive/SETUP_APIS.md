# VÉLØ Oracle 2.0 - API Setup Instructions

This guide will help you set up the Betfair API and The Racing API credentials so Oracle 2.0 can access **live market data** and **historical race data**.

---

## Step 1: Set Up Betfair API

### 1.1 Create Betfair Account
1. Go to https://www.betfair.com
2. Create an account (if you don't have one)
3. Verify your identity (required for API access)

### 1.2 Enable API Access
1. Log in to Betfair
2. Go to **Account** > **API Access**
3. Apply for API access (may take 24-48 hours for approval)

### 1.3 Generate App Key
1. Once approved, go to https://developer.betfair.com
2. Navigate to **My Account** > **My Application Keys**
3. Click **Create New App Key**
4. Choose **Delayed** app key (free) or **Live** app key (requires deposit)
5. Copy the **App Key** (looks like: `aBcDeFgHiJkLmNoP`)

### 1.4 Get Your Credentials
- **Username**: Your Betfair login username
- **Password**: Your Betfair login password
- **App Key**: The app key you just generated

---

## Step 2: Set Up The Racing API

### 2.1 Sign Up for The Racing API
1. Go to https://www.theracingapi.com
2. Create an account
3. Choose a subscription plan:
   - **Free Tier**: Limited access (good for testing)
   - **Starter**: £29/month (recommended for Oracle 2.0)
   - **Pro**: £99/month (full historical access)

### 2.2 Get Your API Key
1. Log in to The Racing API dashboard
2. Go to **Account** > **API Keys**
3. Copy your **API Key** (looks like: `tra_1234567890abcdef`)

---

## Step 3: Configure Oracle 2.0

### 3.1 Create .env File
```bash
cd /home/ubuntu/velo-oracle
cp .env.example .env
nano .env
```

### 3.2 Fill in Your Credentials
Edit the `.env` file and replace the placeholder values:

```bash
# Betfair API
BETFAIR_USERNAME="your_actual_username"
BETFAIR_PASSWORD="your_actual_password"
BETFAIR_APP_KEY="your_actual_app_key"

# The Racing API
RACING_API_KEY="your_actual_api_key"

# Database (set up later)
VELO_DB_CONNECTION="postgresql://velo_user:your_password@localhost:5432/velo_racing"
```

**Important**: Never commit the `.env` file to GitHub. It's already in `.gitignore`.

---

## Step 4: Test the APIs

### 4.1 Test Betfair API
```bash
cd /home/ubuntu/velo-oracle
python3 src/integrations/betfair_api.py
```

Expected output:
```
✓ Betfair login successful!
✓ Session token: [token]
✓ Fetching horse racing markets...
✓ Found X markets
```

### 4.2 Test The Racing API
```bash
python3 src/integrations/racing_api.py
```

Expected output:
```
✓ Racing API connection successful!
✓ Fetching race results for 2025-10-18...
✓ Found X races
```

---

## Step 5: Run Data-Driven Analysis

Once both APIs are working, you can run the full Oracle 2.0 analysis:

```bash
python3 analyze_race_data_driven.py \
  --market-id 1.249166696 \
  --course Ascot \
  --time "13:30" \
  --save
```

This will:
1. Pull **live Betfair odds and volumes**
2. Fetch **historical data** for each horse
3. Calculate **ML win probabilities**
4. Detect **market manipulation**
5. Identify **value bets** (EV > 10%)

---

## Troubleshooting

### Betfair API Issues

**Error: "Invalid username or password"**
- Double-check your credentials in `.env`
- Make sure you're using your Betfair **username**, not email

**Error: "INVALID_APP_KEY"**
- Verify your app key is correct
- Make sure API access is approved (check Betfair account)

**Error: "Insufficient funds"**
- Betfair requires a minimum balance for API access
- Deposit £5-10 to activate

### Racing API Issues

**Error: "Invalid API key"**
- Check your API key in `.env`
- Make sure your subscription is active

**Error: "Rate limit exceeded"**
- You've hit the API rate limit
- Wait 60 seconds and try again
- Consider upgrading your subscription

---

## What You Get

Once the APIs are set up, Oracle 2.0 can:

✅ **Live Market Data**: Real-time odds, matched volumes, back/lay prices  
✅ **Market Manipulation Detection**: Identify odds crashes, volume spikes, smart money  
✅ **Historical Data**: 500,000+ races, horse form, jockey/trainer stats  
✅ **ML Probabilities**: Benter model calculates true win probabilities  
✅ **Value Identification**: Find bets with positive expected value  
✅ **No Narratives**: Pure data, no Racing Post opinions  

---

## Next Steps

1. **Set up PostgreSQL database** (see `ORACLE_2.0_DEPLOYMENT.md`)
2. **Load historical data** from Kaggle datasets
3. **Train the ML model** on 20 years of UK/Ireland racing
4. **Run daily analysis** on upcoming races

---

**Once your APIs are live, Oracle 2.0 becomes a true data-driven prediction engine.**

No more narratives. Just math.

