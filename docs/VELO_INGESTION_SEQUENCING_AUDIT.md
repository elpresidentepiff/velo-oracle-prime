# VÉLØ Ingestion Sequencing Audit

**Status:** Technical Risk Assessment | **Revision:** 2026-04-18.01

This audit defines the "Structural Ingestion Sequencing Bug" identified during the release truth audit.

---

## 1. The Sequencing Bug Defined
The VÉLØ scoring engine operates on a "Single-Fetch" model. When `scripts/run_prime_today.py` fires (currently at 06:00 UTC), it performs the following sequence:
1. **Fetch:** Downloads the `Standard` racecard from the Racing API.
2. **Normalize:** Standardizes the race and runner data.
3. **Score:** Immediately runs the Ensemble and Specialist models.
4. **Persist:** Writes the final verdict to `velo_verdicts` in Supabase.

**The Conflict:** The Racing API's `Standard` racecard is not always static at 06:00 UTC. Late declarations, reserve runners, and final jockey changes can populate the API *after* the initial VÉLØ fetch.

---

## 2. Impact on Scoring Truth
- **Incomplete Fields:** If a race has 10 runners at 06:00 UTC but 12 runners by 10:00 UTC, VÉLØ's probability distribution is mathematically incorrect. The probabilities sum to 1.0 based on 10 horses, ignoring the 2 newcomers who may carry significant signal.
- **Top-Pick Corruption:** If one of the late-arriving horses is a strong statistical candidate (e.g., a "PrepRelease" archetype), the system will have already issued a "Strike" verdict on a horse that is now suboptimal.
- **Sigma Loop Divergence:** The nightly `close_sigma_loops.py` fetches *results*, which include all 12 runners. When it reconciles against the 10-runner `velo_verdict`, it detects a "Horse Set Divergence." This corrupts the forensic attribution and Playbook G's learning data.

---

## 3. Affected Tables
- `velo_verdicts`: Contains probabilities and tiers based on the "stale" field.
- `pipeline_runs`: Records a "PASS" for a scoring run that was technically incomplete.
- `learned_patterns`: Receives noisy attribution data from the Sigma Loop.

---

## 4. Release-Blocker Assessment
**Verdict: DEGRADED-BUT-SHIPPABLE (with caveats)**

While structurally "ugly," this is not a fatal release-blocker for the following reasons:
1. **UK/IRE Market Norms:** The majority of declarations are finalized well before 06:00 UTC. Late changes are the exception, not the rule.
2. **Auditability:** The `velo_verdicts` table includes a `field_size` column. By comparing this to the final result field size in the Sigma Loop, we can algorithmically flag "Incomplete Verdicts."
3. **Shadow Mode Safety:** Since Playbook G is in Shadow Mode, the corrupted learning data does not yet mutate live betting decisions.

**Required Action for "Clean" Release:**
- Add a "Pre-Race Re-Scoring" trigger. The system should re-fetch and re-score the racecard 15 minutes before the off-time for any "A-Tier" or "B-Tier" races to catch late declarations.
- Update `close_sigma_loops.py` to explicitly handle "Horse Set Divergence" as a valid skip reason for learning updates.
