# VÉLØ Website / App MVP Specification V1

**Date:** 2026-04-28
**Status:** Spec only — no build started
**Positioning:** Race intelligence and decision support (not gambling tips)

---

## Core Principle

VÉLØ's product is the evidence, not the picks. The website shows what the intelligence engine sees, how confident it is, and how accurate it has been. Users make their own decisions.

---

## Pages

### 1. Home / Today
- Today's date + race schedule
- VÉLØ's picks for today (if available) with VP score and confidence band
- Quick stats: "Yesterday: X races, Y% frame rate"
- CTA: View full intelligence / Sign up

### 2. Daily Intelligence Feed
For each race today:
```
EPSOM 2:05  |  VÉLØ Confidence: HIGH (VP=0.62)
Runman      |  Tier A  |  Frame: 98% historical  |  Signal: VP+MDS+IMP
───────────────────────────────────────────────────────
Post-race: WON ✓  |  SP 1.08
```

Fields shown:
- Venue + time
- VÉLØ's top pick
- VP score (0.00–1.00)
- Confidence band (Exceptional / High / Medium / Low)
- Active signals (VP, MDS, improvement, place_prob)
- Tier (A/B/C/D)
- Historical frame rate for this confidence band
- Post-race result (evening update)

### 3. Historical Performance Dashboard
- 49-day+ evidence table by confidence band
- VP band chart (VP<0.20 through VP≥0.40)
- SR and frame rate by tier
- Cumulative SR trend chart
- Honest: includes all days, including below-baseline days

### 4. Signal Intelligence
- What is VP score?
- What is Tier A/B/C/D?
- What are the proven signals?
- Signal rankings table (from `VELO_SIGNAL_RANKINGS_V1.md`)
- Methodology overview (plain English)

### 5. Post-Race Audit
For each completed day:
- Date header
- Every race: prediction → actual → outcome
- Wins highlighted
- Misses classified (mid-priced, short fav, outsider)
- SR and frame for the day
- Honest miss analysis

### 6. Evidence Vault (public read)
- Link to GitHub evidence vault
- Latest unified audit results
- Router ledger status (V1/V2/V6)
- Signal ranking summary

### 7. About
- What VÉLØ is (auditable intelligence OS)
- What it is not (gambling service)
- Team
- Methodology
- Contact

---

## Confidence Band Display

| Band | VP Range | Label | Historical SR | Historical Frame |
|---|---|---|---|---|
| Exceptional | VP ≥ 0.40 | ⬛⬛⬛⬛ | 44.0% | 85.0% |
| High | VP 0.30–0.40 | ⬛⬛⬛⬜ | 27.3% | 62.9% |
| Medium | VP 0.20–0.30 | ⬛⬛⬜⬜ | 18.0% | 47.8% |
| Low | VP < 0.20 | ⬛⬜⬜⬜ | 14.5% | 33.5% |

(Historical figures from 49-day evidence base, updated after each Unified Audit)

---

## Subscription Tiers

| Tier | Price | Access |
|---|---|---|
| Free | £0 | Previous day's intelligence (24hr delay), summary stats |
| Standard | £9.99/month | Today's intelligence, full historical dashboard, email alerts |
| Pro | £49.99/month | Full signal detail, sidecar scores, router lane status, API access |

---

## Tech Stack (existing infrastructure)

- **Backend:** FastAPI (app/main.py) — already running on Railway
- **Database:** Supabase — sigma_audits, velo_verdicts, learned_patterns already live
- **Frontend:** To be built — React or NextJS recommended
- **Auth:** Supabase Auth
- **Hosting:** Railway (already set up)
- **Data pipeline:** run_prime_today.py + run_results_sigma.py — already running

---

## Legal Disclaimers (required on every page)

> VÉLØ provides race intelligence data for informational and analytical purposes only. It does not constitute financial, betting, or gambling advice. Past performance does not guarantee future results. Gamble responsibly. BeGambleAware.org — 0808 8020 133.

---

## Not Included in MVP

- Live odds integration
- Betfair API connection
- Automated staking
- Social sharing of picks
- League tables or competition features
- Push notifications for race outcomes

---

*VÉLØ Oracle Prime — Website/App MVP Spec V1 | 2026-04-28*
