# VÉLØ SLM CLAIM ENGINE V1

**Status:** SPEC — no training yet. Approval required before any model training.  
**Purpose:** Convert Racing Post text into structured machine features. Extraction, not generation.

---

## Mission Statement

The SLM Claim Engine is not a predictor. It is a translator.

Its sole job: take unstructured racing language (RP comments, spotlight text, trainer quotes, jockey notes) and produce structured, schema-validated claim rows that downstream models can consume.

```
Racing Post text
    ↓
SLM Claim Engine
    ↓
Structured claims (handicap_claim, improvement_claim, stable_intent_claim, ...)
    ↓
Feature store → SQPE / VP / Sigma
```

This is Stage 3 of the training roadmap. Do not build until Stage 1 (model arena) and Stage 2 (horse career memory) are complete.

---

## Output Schema (Claim Row)

Each claim row corresponds to one horse in one race.

```python
{
    "race_id": str,                    # canonical VÉLØ race_id
    "horse_id": str,                   # canonical horse_id
    "horse": str,                      # display name
    "source_text": str,                # raw RP comment / spotlight text
    "source_type": str,                # "spotlight" | "rpd_comment" | "form_guide"
    "extraction_model": str,           # model version that produced this
    "extraction_confidence": float,    # 0.0–1.0

    # ── Claim flags (bool) ────────────────────────────────────────────────────
    "handicap_claim": bool,            # "runs off a good mark", "still ahead of handicapper"
    "improvement_claim": bool,         # "should improve", "better for the run", "step up"
    "stable_intent_claim": bool,       # trainer language suggesting intent (not fitness)
    "market_expectation_claim": bool,  # "expected to go off favourite", "heavily backed"
    "ground_claim": bool,              # "loves cut in ground", "unsuited by going"
    "trip_claim": bool,                # "step up in trip", "better over this distance"
    "class_claim": bool,               # "dropping in class", "out of depth"
    "fitness_claim": bool,             # "fresh and well", "needs this run", "blow-the-cobwebs"
    "negative_claim": bool,            # "may struggle to score", "hard to win off this mark"
    "unsupported_hype_claim": bool,    # "exciting prospect" with no evidence

    # ── Claim magnitudes (float 0.0–1.0) ─────────────────────────────────────
    "improvement_magnitude": float,    # 0.0=none, 1.0=transformative improvement expected
    "intent_strength": float,          # 0.0=vague, 1.0=explicit stable confidence signal
    "negative_strength": float,        # 0.0=mild reservation, 1.0=hard negative flag

    # ── Metadata ──────────────────────────────────────────────────────────────
    "extracted_at": str,               # ISO timestamp
    "verified": bool,                  # whether Sigma outcome matched claim direction
    "verification_lag_days": int,      # days between extraction and sigma close
}
```

---

## Training Data Sources

When training begins, use only these sources:

| Source | Content | rows available |
|---|---|---|
| `rp_runner_profile_latest.parquet` horse_comment | Current day RP text | 306 (rolling) |
| `horse_comments` (Supabase) | Historic NLP flags | 1,765 |
| `velo_unified_evidence_corpus_v1.csv` + sigma outcomes | Ground truth labels | 1,310 |
| `sigma_audits` + `velo_verdicts` combined | Outcome verification | 28+ per day |

Labels for supervised training come from Sigma outcomes:
- If `improvement_claim=True` AND sigma outcome=WIN → label=1
- If `improvement_claim=True` AND sigma outcome=MISS → label=0

**Hard rule:** `actual_sp` / `sp_decimal` must NOT be a training feature. Use it for ROI analysis only, never as a predictive signal.

---

## Training Approach

### Phase A — Rule-based extraction (build now, no GPU needed)
Use regex + keyword matching against RP comment text to produce claim flags. This creates training labels and establishes a baseline.

### Phase B — DSPy pipeline (SHADOW_TEST approved)
Use DSPy to build an LM-powered extraction pipeline. Prompt is optimised against Phase A ground truth. DSPy compiles the prompt into a repeatable extraction program.

### Phase C — Fine-tuned SLM (GPU required, operator approval)
Fine-tune a small open model (e.g. Phi-3-mini, Qwen2.5-1.5B, Gemma-2-2B) on the structured claim extraction task. Use Unsloth or Axolotl.

Only proceed to Phase C when Phase B precision >= 0.80 on held-out validation.

---

## Model Selection Criteria (for Phase C)

| Model | Params | VRAM (Q4) | Claim extraction suitability |
|---|---|---|---|
| Phi-3-mini | 3.8B | ~2.5GB | HIGH — strong on structured extraction |
| Qwen2.5-1.5B | 1.5B | ~1GB | HIGH — compact, fast CPU inference |
| Gemma-2-2B | 2B | ~1.5GB | HIGH — Google quality, small size |
| Llama-3.2-3B | 3B | ~2GB | MEDIUM — generation-focused |

Default to Qwen2.5-1.5B for CPU inference via llama.cpp.

---

## Inference Integration

The claim engine outputs are written to a feature store:
- `data/features/slm_claims_YYYY_MM_DD.parquet`

These feed into SQPE/VP as additive features — they do not replace existing signals.

The engine runs POST-INGEST, PRE-SCORING:
```
RP PDF parsed → spotlight_parser → SLM Claim Engine → feature store → run_prime_today.py
```

If the SLM fails, scoring continues without claim features (graceful degradation).

---

## Governance

```
SLM_CLAIM_ENGINE_STATUS    = SPEC (not trained)
PHASE_A_EXTRACTION         = PENDING (regex baseline)
PHASE_B_DSPY               = PENDING (requires DSPy install)
PHASE_C_FINETUNE           = BLOCKED (requires Phase B gate)
PRODUCTION_INTEGRATION     = BLOCKED (requires Phase C gate)
SP_AS_PREDICTIVE_FEATURE   = NEVER
OPERATOR_APPROVAL_REQUIRED = YES (before each phase)
```
