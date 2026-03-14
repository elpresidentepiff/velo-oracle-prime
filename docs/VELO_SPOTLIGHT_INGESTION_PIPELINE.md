# VÉLØ Spotlight Ingestion Pipeline — Specification
## Version 1.0 | Canonical Doctrine

---

## 1. Objective

To create a robust, automated pipeline that extracts per-horse spotlight comments from raw race card data, runs the NLP parsing via `spotlight_parser.py`, and makes the resulting structured `spotlight_records` available to the `PlaybookOrchestrator` for engine analysis.

The pipeline's primary design constraint is **resilience**. A failure at any point in the spotlight pipeline must **never** block the main VÉLØ engine from running. The system must default to a clean, structural-only verdict if spotlight data is absent, corrupt, or unavailable.

---

## 2. Architecture

- **New Worker:** `workers/spotlight_ingestion_worker.py`
- **Trigger:** The main VÉLØ ingestion spine will call this worker after successfully parsing a race card and before triggering the main engine analysis.
- **Input:** `race_id`, `meeting_date`, and the file path to the raw race card PDF/text file.
- **Output:**
    1. **Primary:** Writes structured NLP data to the `horse_comments` and `race_spotlight_verdict` tables in the Supabase database, keyed by `race_id` and `horse_name`.
    2. **Secondary:** The main engine orchestrator will query these tables for a given `race_id` to retrieve the `spotlight_records` before calling `analyze_race()`.

---

## 3. Failure Modes & Null Pathway Contract

This is the most critical part of the specification. The pipeline is designed to fail silently and gracefully, allowing the main engine to proceed without interruption.

| Failure Mode | Cause | Pipeline Behaviour | Orchestrator Behaviour |
|:---|:---|:---|:---|
| **No Per-Horse Comments** | The source race card data (e.g., Racing Post PDF) contains no spotlight comment text for any horse in the race. | The `spotlight_parser` will find no text to parse. The worker will log a `NO_COMMENT_DATA_FOUND` info message and exit cleanly. No records will be written to Supabase for this race. | The orchestrator will query Supabase and receive an empty result set. It will proceed with `spotlight_records` as an empty dict. The `null_reason` will be `SPOTLIGHT_RECORDS_EMPTY`. The engine runs on structural data only. |
| **PDF Parse Failure** | The upstream PDF parsing tool (e.g., `manus-speech-to-text` or a PyPDF2 script) fails to extract any text from the source file. | The ingestion worker will receive an empty or malformed input. It will log a `PDF_PARSE_FAILURE` warning and exit cleanly. | Same as above. The orchestrator receives no data and proceeds with a structural-only verdict. |
| **Source Unavailable** | The script that fetches the raw race card data fails (e.g., 404 error, network issue). | The ingestion worker is never triggered. | Same as above. The orchestrator receives no data and proceeds with a structural-only verdict. |
| **Parser Exception** | An unexpected error occurs within `spotlight_parser.py` (e.g., a regex error, a data type mismatch). | The worker's main function will be wrapped in a `try...except` block. It will log the full exception traceback as an `INGESTION_PIPELINE_EXCEPTION` error, but will **not** raise the exception further. It will exit with a status code indicating a non-blocking failure. | Same as above. The orchestrator receives no data and proceeds with a structural-only verdict. The `null_reason` will be `PIPELINE_EXCEPTION`. |

---

## 4. Orchestrator Contract (Implemented in v1.2)

The `PlaybookOrchestrator` already adheres to this contract as of version 1.2.

- **`analyze_race(oracle_data, spotlight_records=None)`:** The `spotlight_records` argument is optional and defaults to `None`.
- **Null Pathway Logic:** The orchestrator contains an explicit `try...except` block and checks for `None` or empty `spotlight_records`. If any of these conditions are met, it sets a `spotlight_null_reason` and proceeds without error.
- **Output Transparency:** The final engine output JSON will always contain the `spotlight_layer` block, which includes:
    - `"active": false`
    - `"null_reason": "NO_SPOTLIGHT_RECORDS_PROVIDED"` (or `SPOTLIGHT_RECORDS_EMPTY`, `PIPELINE_EXCEPTION`, etc.)

This ensures that every engine verdict is auditable. It is always clear whether the spotlight layer contributed to the analysis or was bypassed due to a pipeline failure.

---

## 5. Build Priority

This pipeline is the **highest priority** next build item. It is the final step required to make the Spotlight Layer fully autonomous. The Supabase migration and further integration tests should be completed in parallel or immediately after the pipeline worker is built.
