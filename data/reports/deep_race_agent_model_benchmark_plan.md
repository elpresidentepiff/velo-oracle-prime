# Deep Race Agent — GLM / Qwen / Kimi Blind Benchmark Plan (Phase 12)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. Design only — not executed in this evidence mission.

## Objective

Select a model for the provider-neutral Deep Race Agent adapter (see `deep_race_agent_contract.json`) based on measured performance against a fixed benchmark, not reputation or convenience.

## Benchmark set construction

- Draw a stratified sample of sealed race packets (target: 40-60 races) spanning multiple days already proven `MORNING_RUN_PROVEN` in prior forensic missions (e.g. 2026-07-14 per PR #150's evidence bundle, plus 2026-07-15's own morning run once this mission's `race_day_15_frozen_recount.json` is accepted), so packet correctness is not itself in question.
- Stratify by: field size (small/medium/large), data completeness (full passport coverage vs. sparse), and convergence pattern (all-models-agree vs. models-split), so the benchmark exercises contradiction-detection and low-data reasoning, not just easy consensus calls.
- Freeze the packets before benchmarking; identical packets go to all three providers so scores are directly comparable.

## Benchmark criteria (from the mission brief, made measurable)

| Criterion | Measurement method |
|---|---|
| Structured JSON validity | Percentage of responses that parse against `output_schema` with zero required-field omissions and zero type violations, on first attempt (no retry credit) |
| Source citation accuracy | Sample-audit: for each `evidence_used` entry, a human or a second LLM-as-judge confirms the cited field actually supports the stated reasoning; report % accurate |
| Coverage of OR/TS/Spotlight/Postdata/passport | Percentage of available fields in the packet that appear in `evidence_used` OR are explicitly listed in `evidence_missing` (never simply ignored) |
| Contradiction detection | Inject N synthetic packets with a known, deliberate conflict (e.g. RPR trending down while Old VÉLØ probability is high) and measure recall — did the agent's `contradictions` array catch the planted conflict? |
| Hallucination rate | Percentage of `primary_horse`/`counter_horse` values that do not match any runner name actually present in the packet, plus percentage of numeric claims in `reasoning` text that do not trace to any packet field |
| Latency | Wall-clock p50/p95 per packet, provider API call only |
| Cost | USD per packet at each provider's current pricing, using actual prompt/completion token counts returned |
| Consistency across repeated runs | Run the identical packet 5x per provider at temperature=0 (or lowest available); measure agreement rate on `primary_horse` and `value.assessment` across the 5 runs |

## Procedure

1. Implement `generate_deep_race_analysis(packet, provider)` for all three providers behind the single adapter interface defined in `deep_race_agent_contract.json`.
2. Run the full frozen benchmark set through all three providers, capturing raw responses, parsed structured output, and metadata (latency, tokens, cost) for every packet.
3. Score each criterion per provider per the measurement methods above.
4. Produce a scorecard (one row per provider, one column per criterion) with both raw scores and a normalized 0-100 composite. Do not pre-weight criteria to favor a particular provider; publish the weighting formula alongside the results so it can be challenged.
5. Flag any provider that fails structured-JSON validity below an operator-set floor (e.g. 95%) as **disqualified regardless of other scores** — an agent whose output the pipeline cannot reliably parse is not usable no matter how good its reasoning is.
6. Present the scorecard plus 3-5 concrete example transcripts (including at least one contradiction-detection success/failure per provider) to the operator. The operator makes the final selection; this plan explicitly does not pre-select a "recommended" winner — that would defeat the blind-benchmark requirement.

## What this plan deliberately does not do

- It does not hard-wire GLM, Qwen, or Kimi as default based on reputation, prior familiarity, or ease of integration.
- It does not run the benchmark against packets whose own ground truth (the sealed morning run) is itself unproven — using 2026-07-15's morning run only became valid for this purpose once Phase 1 of this mission classified it `MORNING_RUN_PROVEN`.
- It does not let the Deep Agent see race results at any stage of benchmarking; correctness is judged against internal consistency, citation accuracy, and contradiction-detection on synthetic injected conflicts, not against "did it pick the winner" (which would reward hindsight-shaped reasoning, not analytical quality).
