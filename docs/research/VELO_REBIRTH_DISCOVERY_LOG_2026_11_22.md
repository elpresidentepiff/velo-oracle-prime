# VÉLØ Rebirth — Discovery Log

**Date:** 2026-11-22
**Scope:** research-only discovery; no production scoring, configuration, model, data, or deployment changes.
**Purpose:** preserve what VÉLØ has learned before designing a clean successor.

## Discovery rules

1. Preserve Legacy VÉLØ and its evidence. Do not replace it while a successor is researched.
2. A claim is classified as **proved**, **candidate**, or **unverified**. Narrative is never proof.
3. Historical SP is settlement evidence, not evidence of an executable pre-off price.
4. A feature is ineligible for fitting unless its source, availability time, identity mapping, schema version, and transformation are known.
5. Provider predictions remain benchmarks only; they never enter a VÉLØ feature vector.

## Confirmed assets

| Asset | State | Evidence |
|---|---|---|
| UK/IRE historical base | **Candidate research corpus** | `data/new_build/training/core_v0_historical_dataset.parquet`: 1,162,031 runner rows, 116,111 races, 148,741 horses, 2015-01-01 through 2025-07-05. |
| Chronological splits | **Candidate research protocol** | Train 2015–2023: 987,511 rows; validation 2024: 117,299; test 2025: 57,221. |
| Current operational data | **Proved system-of-record evidence** | Supabase holds races, verdicts, Sigma, horse runs and canonical scorecards, but coverage differs by table/date. |
| Racing Post captures | **Valuable raw evidence** | RP cards, HTML, PDFs, results and parsed artifacts exist, but not yet one universal normalized as-of feature store. |
| Passports / connections / intent | **High-potential candidate features** | Existing passports, trainer-jockey-course-distance sidecars and intent research exist; historical coverage/provenance must be certified. |
| Market research | **Hypothesis, not a production market feed** | Market-deception and mid-price work is valuable, but timestamped market snapshots are not yet a complete historical execution dataset. |
| World data | **Separate research corpus** | Jurisdiction-specific FormFav evidence is shadow-only and must not mix with UK/IRE learning. |

## Hard blockers discovered

1. **Identity/provenance break:** broad sidecar tables use race IDs incompatible with the Core V0 historical corpus and lack date/version lineage. They are unjoinable until reconciled.
2. **Narrative/runtime drift:** several historical whitepapers and architecture documents describe capabilities which later code/runtime audits disproved.
3. **Too many execution paths:** production, research, legacy source adapters, dated repairs and experimental lanes share one repository namespace.
4. **No immutable universal prediction object:** downstream reporting can still reconstruct truth from a mixture of daily/local artifacts rather than one frozen prediction ID.
5. **Comment intelligence not validated for scoring:** RP narrative evidence must remain factual, source-spanned and separately shadow-evaluated.
6. **Market-event history incomplete:** do not claim market-movement/decoy ability until time-stamped price, liquidity and source data exist.

## Core VÉLØ insight worth preserving

The market is an adversarial information source: neither a guide to follow nor noise to ignore. The successor must compare a market baseline with independently derived racing context, identify disagreement and uncertainty, and explain why it abstains.

## Rebuild target

```text
Raw Source Ledger
  -> Immutable Entity & Race Identity
  -> As-of Feature Snapshots
  -> Reproducible Research / Replay Lab
  -> Frozen Prediction Packets
  -> Results / Settlement / Calibration
  -> Decision Desk for explanation and education
```

## Next discovery tasks

- Catalogue model binaries, feature contracts, datasets, research reports and papers with hashes and status.
- Build a field-level lineage map: source -> parser -> feature -> model -> prediction -> settlement.
- Separate current Prime, shadow lanes, legacy experiments and retired code.
- Certify a minimal, reproducible UK/IRE baseline replay before any new model work.
- Locate and catalogue the operator's external racing books/papers when their folder is identified.

## V3 factual-context feasibility census — 2026-11-23

Read-only Supabase census of `rich_context_shadow_packets` from 2026-11-06 to 2026-11-22:

- 4,173 immutable pre-off packets exist.
- FormFav raw, pace and class families are present on almost all packets from the captured UK/IRE days.
- Track-bias evidence is sparse: present on 659 packets on 2026-11-07 and 12 on 2026-11-12, absent on most other observed dates.
- RP Spotlight factual coverage ranges from 23 to 100 runners per observed day.
- Pre-off passport evidence is absent until 2026-11-21; then present for 267 runners on 2026-11-21 and 155 on 2026-11-22.
- Only **85 packets** contain every declared V3 factual family; they first appear on 2026-11-21.

**Decision:** do not fit or promote Full Factual Context V3.  The next-generation feature contract is implemented as a collection-only shadow contract until enough genuinely prospective, complete packets exist.  The dashboard must show this coverage honestly rather than calling V3 fully enriched.
