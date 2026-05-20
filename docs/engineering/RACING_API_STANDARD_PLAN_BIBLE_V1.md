# Racing API Standard Plan Bible V1

**Date:** 2026-05-05

## 1. Operating Constraint
VÉLØ operates on **The Racing API - Standard Plan**.
**Rate Limit:** STRICTLY 3 requests per second.

## 2. Official OpenAPI Routes (Standard)
- `GET /v1/racecards/standard?day=YYYY-MM-DD`
  - Returns: standard racecards, runner details, `headgear`, `spotlight`, `wind_surgery`, `ofr`, `rpr`, `ts`, `form`, `medical`, `quotes`.
- `GET /v1/horses/{horse_id}/results`
  - Returns: historical results for a specific horse.

## 3. Inaccessible Data
We DO NOT have access to Pro endpoints, advanced sectional timing (unless in standard text), or native Betfair BSP streams through this specific API. Do not attempt to guess or probe unauthorized routes.

## 4. Required Parameters
- `Authorization`: Basic Auth (`RACING_API_USERNAME`:`RACING_API_PASSWORD`)
- `User-Agent`: Must be set (e.g., `Mozilla/5.0`) to avoid Cloudflare blocking.
- `Accept`: `application/json`

## 5. Safe Extraction Order
1. **Daily Fetch:** Call `/racecards/standard` once per day. Cache the JSON locally (e.g., `data/racecards_YYYY_MM_DD_standard.json`).
2. **Runner Enrichment:** Parse the cached JSON to extract Spotlight, headgear, and ratings.
3. **Targeted Fetch:** If individual horse history is needed, queue requests at a maximum rate of 2 per second to ensure a buffer against the 3 req/sec limit.
4. **Retry Logic:** Implement exponential backoff for HTTP 429 (Too Many Requests). Start at 1s, double up to 3 times. Fail gracefully.
