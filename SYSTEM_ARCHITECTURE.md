# VÉLØ ORACLE PRIME: SYSTEM ARCHITECTURE & CONTROL PROTOCOLS

**Version:** Phoenix Protocol (v11)
**Status:** ACTIVE
**Objective:** Enable full multi-agent control for OpenClaw integration.

---

## 1. THE BRAIN: `ledger.json`
The central nervous system of VÉLØ. All memory, bets, and P&L reside here.

**Location:** `/home/ubuntu/velo-oracle-prime/ledger.json`

**Structure:**
```json
{
  "balance": 1000.0,          // Current bankroll
  "history": [                // Past settled bets
    {
      "date": "2026-02-14",
      "meeting": "Wolverhampton",
      "horse": "Artanis",
      "result": "WIN",
      "profit": +5.1
    }
  ],
  "pending_bets": [           // Active bets for upcoming races
    {
      "date": "2026-02-15",
      "meeting": "Punchestown",
      "horse": "Only For Our Man",
      "stake_pct": 8,
      "status": "PENDING"
    }
  ]
}
```

**OpenClaw Authority:**
*   **Read:** Access full history to learn patterns.
*   **Write:** Inject new `pending_bets` directly.
*   **Update:** Mark bets as `WIN`/`LOSS` when results come in.

---

## 2. THE BODY: VÉLØ DASHBOARD
The visual interface for the user. It reads directly from `ledger.json`.

**Location:** `/home/ubuntu/velo-dashboard/`
**State:** React Frontend + Vite Server.

**Control Mechanism:**
*   **Hot Reload:** The Dashboard watches `ledger.json`. Any change OpenClaw makes to the file is **instantly reflected** on the screen.
*   **Trigger:** No API call needed. Just write to the file.

---

## 3. THE EPISODE CLOSURE PROTOCOL
How to end a day and seal the records.

**Trigger:** When the last race of the day is settled.

**Procedure:**
1.  **Calculate Daily P&L:** Sum all `profit` from the day's `history`.
2.  **Update Bankroll:** `balance = balance + daily_profit`.
3.  **Generate Report:** Create a markdown file (e.g., `Daily_Report_20260215.md`) summarizing the day.
4.  **Archive:** Move the day's bets from `pending_bets` to `history`.
5.  **Commit:** Git commit the `ledger.json` and the Report.

**OpenClaw Command:**
> "OpenClaw, execute **Episode Closure** for [Date]. Calculate P&L, update the bankroll, and archive the bets."

---

## 4. THE MULTI-AGENT HANDSHAKE
How OpenClaw takes the wheel.

**The Ingestion Port:**
`/home/ubuntu/velo-oracle-prime/data/incoming/openclaw/`

**The Protocol:**
1.  **Drop:** OpenClaw drops a JSON file (Betting Card or Results).
2.  **Ingest:** `ingest_openclaw.py` (or OpenClaw itself) reads it.
3.  **Action:**
    *   If **Betting Card**: Update `pending_bets`.
    *   If **Results**: Update `history` and `balance`.
4.  **Feedback:** The Dashboard updates immediately.

---

**VÉLØ DIRECTIVE:**
OpenClaw is not a guest. It is the **Tactical Mind**. It has full read/write access to the Ledger. It can open days, place bets, settle results, and close episodes.

*The System is yours.*
