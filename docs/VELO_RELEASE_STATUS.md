# VÉLØ Oracle Prime — Release Status

**Revision:** 2026-04-18.02 | **Judgment:** CONDITIONAL GO (Pending Deploy Truth)

---

## 1. Release Organism
*The "Minimum Honest VÉLØ" as verified on current `main`.*

- **Production Engine:** VÉLØ Prime Meta-Ensemble (SQPE v17 + 7 Specialists).
- **Control Layer:** BHA Macro Context (Structural Regime dampening).
- **Audit Layer:** Nightly Sigma forensic reconciliation loop.
- **Safety Valve:** Shadow-mode Playbook G (No-mutation sentient bridge).

---

## 2. Proven Strengths
- **Integrity:** Leakage firewall is verified; model training is temporal-safe.
- **Observability:** 60-column live `velo_verdicts` schema fully audited and synced.
- **Hardening:** Production dependencies and environment-aware runtime are live.
- **Performance:** 2026 Wolverhampton/Naas benchmarks show viable Top-1 and Place hit rates.

---

## 3. Known Degraded Risks
- **Ingestion Sequencing:** Single-fetch risk (06:00 UTC) remains. Late-arriving horses or declarations may result in a "Horse Set Divergence" in the Sigma Loop. **Status: Documented & Shippable.**
- **Migration Debt:** All repo migrations are synced, but future changes require strict DB audit.
- **Test Gap:** 5 minor "expected" failures in backtest JSON serialization (non-blocking for live scoring).

---

## 4. Final Release Checks (Audit Checklist)
- [x] **Health Truth:** `GET /health` returns 200/REACHABLE.
- [x] **Deploy Truth:** Railway service linked to `sincere-empathy`.
- [ ] **Fingerprint Truth:** **STALE / UNVERIFIED.** Endpoint `/api/v1/build-fingerprint` returns hardcoded commit `3b78e9d`. This is a blocking honesty gate.
- [x] **API Guard:** X-API-KEY required on all prediction routes.
- [x] **Truth Ledger:** `docs/VELO_RELEASE_TRUTH_LEDGER.md` is canonical.

---

## 5. Go / No-Go Judgment
**JUDGMENT: CONDITIONAL GO**

The system architecture and model logic are release-ready, but the **Deploy Truth** is not yet trustworthy. We cannot claim a definitive "GO" until the build fingerprint is resolved dynamically to prove that Railway is serving the audited code. The release is blocked until the build-fingerprint is fixed and verified live.
