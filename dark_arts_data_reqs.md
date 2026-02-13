# Dark Arts Data Requirements

To detect the "Quiet Runs" and "Handicap Plots" without automated scraping, we need the following historical data points for each target horse.

## 1. The "Drift" (Market Weakness)
We need to know if the horse was "unwanted" in the market during its losing runs.
*   **Data Point:** Opening Odds vs. Starting Price (SP) for last 3 runs.
*   **Signal:** Drifting from 10/1 -> 25/1 implies "not today".
*   **Format:** `[Date] [Track] [Open Odds] -> [SP]`

## 2. The "Quiet" Ride (Jockey/Trainer Intent)
We need the "In Running" comments to spot tender handling.
*   **Data Point:** Racing Post "Close Up" comments.
*   **Signal:** Phrases like "held up in rear", "never involved", "tenderly handled", "not knocked about".
*   **Format:** `[Date] [Comment Snippet]`

## 3. The "Mark" (Official Rating History)
We need to see the handicap mark sliding down.
*   **Data Point:** Official Rating (OR) for last 5 runs.
*   **Signal:** Dropping 5-10lbs below last winning mark.
*   **Format:** `[Date] [OR]`

## 4. The "Gear" (Equipment Changes)
We need to know if headgear was left off during the quiet runs and is now back on.
*   **Data Point:** Headgear worn in last 3 runs vs. today.
*   **Signal:** "Blinkers OFF" for 3 runs, now "Blinkers ON".
*   **Format:** `[Date] [Gear]`

## Example "Shopping List" for User
Please provide screenshots or text for the following horses (if running tomorrow):
*   **Horse Name**
*   **Last 3 Runs:** Date, Track, OR, Odds (Open/SP), Comment, Gear.
