# ACCA_LANE_V2 Shadow Spec

## Status

```text
SHADOW ONLY
OPERATOR VISIBILITY ONLY
NOT LIVE
NOT STAKING
NOT TELEGRAM BETTING
NOT ROUTER
NOT MODEL
NOT EXECUTION
```

ACCA_LANE_V2 exists only as a replay-governed shadow specification.

It is not a live feature.
It is not an execution feature.
It is not an approval for wider acca freedom.

---

## Current Truth

The current ACCA replay and ablation evidence says:

- VP30 core is mandatory
- Racing API enrichment improves chain quality
- CASHRUN is not yet isolated as an ACCA lift input
- the current trap filter is too strict
- `BANKER_ONLY` is the strongest clean replay shape
- `BANKER_PLUS_GLUE_ONLY` is the second-best clean replay shape
- full ACCA freedom is not approved

---

## Approved Replay Shapes

Only two replay shapes are approved for V2 shadow work:

1. `BANKER_ONLY`
2. `BANKER_PLUS_GLUE_ONLY`

Everything else remains exploratory only.

---

## Explicit Blocks

The following are explicitly blocked:

- full ACCA freedom
- trap-heavy chain construction
- CASHRUN as required ACCA input
- any live promotion
- any paper promotion
- any staking or execution use

---

## BANKER_ONLY Gate

Minimum replay requirement:

- `14` race days minimum

Required thresholds:

- `2-fold` hit rate must stay above `70%`
- trusted-leg failure rate below `10%`
- trap false-positive rate below `5%`
- no live use

If any threshold fails:

- remain shadow only
- do not widen chain complexity

---

## BANKER_PLUS_GLUE_ONLY Gate

Minimum replay requirement:

- `14` race days minimum

Required thresholds:

- `2-fold` hit rate above `65%`
- `3-fold` hit rate above `45%`
- trusted-leg failure rate below `15%`
- trap false-positive rate below `7%`
- no live use

If any threshold fails:

- remain shadow only
- do not widen chain complexity

---

## Racing API Enrichment

Racing API enrichment remains included as a positive chain-quality input.

Status:

```text
SHADOW ONLY
POSITIVE INPUT
NOT LIVE-WEIGHTED
NOT CAUSALLY PROVEN UNTIL ABLATION HOLDS
```

The next proof requirement is not “does it feel useful?”
It is:

- does the enrichment-on shape beat enrichment-off over replay?

---

## Trap Filter

The trap filter must be softened and retested.

New replay mode required:

- `TRAP_FILTER_SOFTENED`

Rules:

- do not disable trap logic globally
- do not remove trap logic from the lane contract
- reduce overblocking pressure on strong VP legs
- retest false positives vs trusted-leg failures

---

## CASHRUN

CASHRUN remains standalone operator intelligence.

For ACCA purposes:

```text
EXCLUDE FROM CHAIN WEIGHT FOR NOW
OPTIONAL CONTEXT ONLY
NO REQUIRED CHAIN DEPENDENCY
```

It may return later only if isolated lift is proven in replay.

---

## Next Replay Modes

The next controlled replay pass should focus on:

1. `BANKER_ONLY`
2. `BANKER_PLUS_GLUE_ONLY`
3. `TRAP_FILTER_SOFTENED`
4. `WITHOUT_RACING_API_ENRICHMENT` as control check

This is enough to answer the real operational question:

What is the cleanest shadow chain shape that survives replay?

---

## Governance Lock

ACCA_LANE_V2 remains:

- shadow only
- operator only
- replay-governed
- blocked from live promotion

Nothing in this spec authorizes:

- live betting
- staking
- Telegram betting alerts
- router promotion
- model change
- execution bridge change

This lane stays behind glass until evidence survives.
