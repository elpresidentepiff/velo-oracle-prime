# PDF PARSER BENCHMARK PLAN

**Date:** 2026-06-11 · Harness: `scripts/ops/benchmark_pdf_parsers.py` (rerunnable; ground truth = same-date injection JSON runner names).

## First run (June 9 bypass-day corpus, 29 PDFs: BRI/CRL/SAL/SLI/STH)
| Parser | success | name recall | avg runtime | race-times |
|---|---|---|---|---|
| pdfplumber (current) | 100% | 53.8% (1926/3577) | **0.59s** | 162 |
| LiteParse 2.0.0 | 100% | 53.8% (1926/3577) | 4.18s | 162 |
| null control | 0% | 0% | — | 0 |

Reading: identical text extraction on digital RP PDFs (recall ceiling is corpus-structural — each F-file covers a subset of the course's runners, both parsers hit the same ceiling). LiteParse pays 7× runtime for OCR/bbox machinery these documents don't need. Smoke extras verified: JSON+bboxes (293KB), page screenshots, clean text.

## Corpus growth path (to 100 docs)
Add: `data/incoming_pdfs/2026-05-*` days · scanned/photographed cards if any appear · jumps vs AW vs flat · small/large fields · spotlight-comment pages. Manifest: extend the script's `--pdf-dir` runs; results append to `pdf_parser_benchmark_latest.json` history in DuckDB later.

## Verdict v1 (promotion gate NOT met)
- **Primary: pdfplumber stays.** No benchmark win for LiteParse on this class.
- **LiteParse role: SIDECAR + FALLBACK** — (a) screenshot generator for operator evidence/dashboards, (b) OCR fallback when pdfplumber returns empty/garbage text (scanned docs), (c) bbox source if table-structure extraction is built later.
- Re-run gate whenever a new document class appears; promotion needs: recall win + no identity risk + runtime within 2× + deterministic output + 23 truth-boundary tests green + operator approval.
