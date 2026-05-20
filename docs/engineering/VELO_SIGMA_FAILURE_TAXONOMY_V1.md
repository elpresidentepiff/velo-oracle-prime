# VÉLØ Sigma Failure Taxonomy V1

This document defines the standard error codes for reconciliation failures in the VÉLØ system.

| Error Code | Description |
| :--- | :--- |
| **MISSING_RESULT** | Race present in ingested card but absent in API results. |
| **IDENTITY_MISMATCH** | Runner identity cannot be resolved (Name/ID mismatch). |
| **NON_RUNNER_CONFLICT** | Prediction exists for a horse officially declared a non-runner. |
| **MISSING_PREDICTION** | Official result found for a race/runner that was not scored. |
| **API_FAILURE** | Connection error or malformed response from external API. |
| **DB_WRITE_FAILURE** | Persistence error when writing reconciliation status. |
| **DUPLICATE_RACE** | Multiple race records found for the same course/time. |
| **DUPLICATE_RUNNER** | Multiple runner records for the same horse in a single race. |
| **AMBIGUOUS_MATCH** | Multiple potential matches found during reconciliation. |
| **CONTEXT_VOID** | Essential HFS fields (mpi, chaos) missing from prediction. |
| **ODDS_MISSING** | Result present but SP/BSP is missing. |
| **RESULT_PARTIAL** | Result data exists but is incomplete (e.g., missing positions). |
| **UNKNOWN_UNCLASSIFIED** | Catch-all for unhandled exceptions. |
