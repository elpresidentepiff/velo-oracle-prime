# VÉLØ Media Engine V1

**Status:** DEFERRED — DESIGN ONLY  
**Phase:** 10 — Product Layer  
**Classification:** `MEDIA_ENGINE_DEFERRED` / `PREDICTION_CORE_SEPARATED` / `DESIGN_ONLY`

---

## Purpose

Ghost/Listmonk-style publishing layer for public and private VÉLØ intelligence content.

This layer cannot affect prediction, scoring, learning, or live state. It is a read-only consumer of published reports and evidence artifacts.

---

## Content Types

| Content | Audience | Format |
|---|---|---|
| Daily intelligence brief | Private / operator | Markdown → email + web |
| Weekly Council report | Private / investor | PDF-ready Markdown |
| International expansion notes | Private | Structured update |
| Premium research drops | Subscriber | Long-form analysis |
| Investor updates | VC / angel | Quarterly brief |

---

## Hard Boundary

The Media Engine:
- Reads `data/reports/*.md` and `data/council_reports/*.md`
- Formats and distributes content
- CANNOT query Supabase live tables
- CANNOT read model weights
- CANNOT receive feedback that affects scoring
- CANNOT trigger any prediction pipeline component

---

```
MEDIA_ENGINE_V1_STATUS: DEFERRED
ACTIVATION: After prediction layer proven at production scale
PREDICTION_CORE_SEPARATED: enforced — media cannot affect scoring
```
