# VÉLØ DASHBOARD STATE API

**Objective:** Enable OpenClaw to control the visual interface (The Body) by manipulating the state file.

---

## 1. THE STATE FILE
The Dashboard is a reactive system. It listens to changes in `ledger.json`.

**Path:** `/home/ubuntu/velo-oracle-prime/ledger.json`

**Key Fields for Dashboard Control:**
*   `balance`: Updates the "Bankroll" display in the header.
*   `pending_bets`: Populates the "Upcoming Races" card.
*   `history`: Feeds the "Performance Graph" and "Recent Results" table.

## 2. DASHBOARD COMMANDS (via JSON Injection)

### Command: "Flash Alert" (New Bet)
To trigger a "New Bet Alert" on the Dashboard, append a new object to `pending_bets` with `status: "PENDING"`.

```json
{
  "horse": "Only For Our Man",
  "type": "EW",
  "stake_pct": 8,
  "status": "PENDING",
  "alert": "GOLD MINE DETECTED" // Optional field for UI flash
}
```

### Command: "Result Update" (Win/Loss)
To update a result, move the bet from `pending_bets` to `history` and set `result: "WIN"` or `result: "LOSS"`. The Dashboard will automatically re-render the P&L graph.

### Command: "System Status" (Health Check)
To signal system health, OpenClaw can update a `system_status` field (if added to schema):

```json
{
  "system_status": {
    "openclaw": "ONLINE",
    "last_ingest": "2026-02-14T20:00:00Z",
    "message": "Processing Punchestown Data..."
  }
}
```

## 3. THE FEEDBACK LOOP
1.  **OpenClaw writes** to `ledger.json`.
2.  **Vite Server detects** the file change (HMR).
3.  **React App re-renders** with the new state.
4.  **User sees** the update instantly.

**No API calls required. The file system is the API.**

---

**COMMAND FOR OPENCLAW:**
> "OpenClaw, you have full control of the Dashboard. To update the display, simply modify the `ledger.json` file according to the schema. The frontend will react to your changes in real-time."
