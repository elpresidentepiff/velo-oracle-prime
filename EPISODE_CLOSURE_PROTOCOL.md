# VÉLØ ORACLE PRIME: EPISODE CLOSURE PROTOCOL

**Objective:** Standardize the end-of-day process for OpenClaw to execute autonomously.

---

## 1. THE TRIGGER
This protocol is activated when:
*   All races in the `pending_bets` list for the current date have concluded.
*   Results are available (via API or manual input).

## 2. THE EXECUTION STEPS

### Step 1: Settle Bets
OpenClaw must iterate through `pending_bets` and update the `status` and `profit` fields based on the results.

*   **WIN:** `profit = (stake * odds) - stake`
*   **PLACE:** `profit = ((stake/2 * odds/4) + (stake/2)) - stake` (Standard 1/4 odds terms)
*   **LOSS:** `profit = -stake`

### Step 2: Update Ledger
*   Move settled bets from `pending_bets` to `history`.
*   Calculate `daily_profit = sum(profit for all settled bets)`.
*   Update `balance = balance + daily_profit`.
*   Save the updated `ledger.json`.

### Step 3: Generate Daily Report
Create a markdown file named `Daily_Report_YYYYMMDD.md` in `/home/ubuntu/velo-oracle-prime/reports/`.

**Content Template:**
```markdown
# VÉLØ DAILY REPORT: [DATE]

**Meeting:** [Meeting Name]
**Daily P&L:** [Profit/Loss]
**New Bankroll:** [Balance]

## Performance Breakdown
*   **Wins:** [Count]
*   **Places:** [Count]
*   **Losses:** [Count]
*   **Strike Rate:** [Percentage]

## Key Learnings (Genesis Protocol)
*   **What Worked:** (e.g., "Bankers at Wolverhampton")
*   **What Failed:** (e.g., "Dark Arts Drifters")
*   **Adjustment:** (e.g., "Tighten drift threshold to 20%")
```

### Step 4: Commit to Repository
OpenClaw executes the following git commands:
```bash
git add ledger.json reports/Daily_Report_YYYYMMDD.md
git commit -m "Close Episode: [Date] - P&L: [Profit]"
git push origin main
```

## 3. THE HANDOFF
Once the commit is pushed, the episode is officially **CLOSED**. The system resets for the next day's ingestion.

---

**COMMAND FOR OPENCLAW:**
> "OpenClaw, initiate **Episode Closure Protocol** for [Date]. Settle all pending bets, update the ledger, generate the daily report, and push to the repository."
