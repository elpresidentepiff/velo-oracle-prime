# VÉLØ Complexity Audit V1

**Status:** DESIGN ONLY  
**Phase:** 8 — System Health  
**Classification:** `COMPLEXITY_AUDIT_DEFINED` / `DESIGN_ONLY`

---

## Purpose

SQPE already contains sub-quadratic thinking at model level. Now audit system-level complexity.

Uncontrolled O(n²) logic in the pipeline means runtime degrades as data grows. This audit identifies every join, comparison, and loop that scales poorly and documents whether it is justified.

---

## Audit Targets

### Identity Matching

| Component | Current | Concern |
|---|---|---|
| Horse name matching | `difflib.SequenceMatcher` fuzzy match | O(n×m) per race — acceptable for field sizes ≤20 |
| Jockey ID resolution | `course_identity_resolver.py` | Verify index-based join, not pairwise scan |
| Trainer/jockey combo lookup | JTC-D tables | Needs hash join on (trainer, jockey, course, dist) |

### Feature Engineering

| Component | Current | Concern |
|---|---|---|
| Draw stats lagged | cumsum approach (prior dates only) | O(n log n) groupby — acceptable |
| International lagged features | `groupby.apply` + `shift` | FutureWarning on pandas groupby.apply — non-breaking but audit |
| Race-level field averages | `groupby.transform('mean')` | Acceptable — broadcast not pairwise |

### Evidence Corpus

| Component | Current | Concern |
|---|---|---|
| Corpus rebuild | `build_unified_evidence_corpus.py` | Full scan on every rebuild — check for incremental option |
| Router shadow audit | Append-only ledger | Acceptable |
| Signal tracker | Full dedup scan | Needs index on race_id for large corpora |

### Council Simulations (Phase 7)

| Component | Target | Concern |
|---|---|---|
| Multi-world simulation | 6 worlds × N days | Must be parallelisable — not sequential nested loops |
| Policy comparison | Per-race result matching | Hash join on race_id — no pairwise comparison |

---

## Complexity Targets

For every identified O(n²) component:
1. Document it: what is it, why does it scale poorly
2. Justify or fix: either confirm it only runs on small n (field size ≤ 20), or refactor to O(n log n) or better
3. Add a runtime assertion: if n > 1000, warn or fail fast

---

## Hard Rules

```
NO_UNCONTROLLED_PAIRWISE: any O(n²) operation must be documented and justified
HASH_JOINS_PREFERRED: groupby/merge operations should use hash joins
NO_BRUTE_FORCE_IDENTITY: fuzzy match only within race — never across full corpus
INCREMENTAL_WHERE_POSSIBLE: corpus builds should support incremental mode
```

```
COMPLEXITY_AUDIT_V1_STATUS: DEFINED
IMPLEMENTATION: PHASE 8 — run after Phase 3 harness established
```
