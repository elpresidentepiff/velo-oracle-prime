# LITEPARSE → SOURCE TRUTH INTEGRATION GATE

**Date:** 2026-06-11 · LiteParse enters the source-truth loop only as fallback/sidecar (benchmark v1 verdict).

## Rules (Loop 1 extensions)
1. Every parser output carries `file_sha256` + `parser_name` + `parser_version` → into the observability packet.
2. Parsed runner tables validate against expected runner count; shortfall ⇒ `PARSER_PARTIAL`.
3. Fallback trigger: pdfplumber text empty/under 500 chars/zero race-time anchors ⇒ LiteParse OCR attempt; **both-parser disagreement on runner count ⇒ `PARSER_DISAGREEMENT` ⇒ day classified SOURCE_DEGRADED minimum.**
4. LiteParse output flows through the SAME identity mapping (`rpdc_attach` normalizer + identity_aliases) — no parser may mint IDs (the June 9 law).
5. Parser failure on any required card ⇒ day cannot classify CLEAN.
6. Statuses: `PARSER_OK / PARSER_PARTIAL / PARSER_DISAGREEMENT / PARSER_FAIL / PARSER_UNKNOWN` — written into the source-truth packet, consumed by Mission Control.

## Wiring order (after June 11, behind roadmap step 7)
adapter (done) → fallback trigger in the bypass path only → packet fields → MC consumption. No live change before the strangler's golden replay protects the boundary.
