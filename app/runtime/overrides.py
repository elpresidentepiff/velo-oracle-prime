"""
VÉLØ Runtime Override Loader
============================
Loads active scoring-time configuration from the runtime_overrides table.

Architecture (3-tier separation — immutable rule):
  learned_patterns  = observations     → written by close_sigma_loops.py
  patch_proposals   = candidates       → written by close_sigma_loops.py
  runtime_overrides = live config      → THIS MODULE reads from here

The scoring layer reads ONLY from this module.
It never reads learned_patterns directly.
SQPE / specialist .pkl weights are never altered.

Fallback chain:
  1. Supabase runtime_overrides WHERE status='ACTIVE' (effective window respected)
  2. config/runtime_overrides.json  (local override file, status='ACTIVE' entries only)
  3. {} (empty — synthesize_decision() hardcoded constants take over, zero behaviour change)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("velo.runtime_overrides")

ROOT = Path(__file__).parent.parent.parent
_FALLBACK_JSON = ROOT / "config" / "runtime_overrides.json"

# Module-level cache — populated by load_runtime_overrides()
_cache: dict[str, Any] = {}
_loaded_at: str | None = None


def load_runtime_overrides(db=None) -> dict[str, Any]:
    """
    Load all ACTIVE runtime overrides.  Call once at scoring start.

    Returns a dict keyed by override_key → parsed value_json.
    Example:
      {
        "tier_thresholds": {
            "A": {"min_prob": 0.32, "min_gap": 0.08, "min_place": 0.52},
            ...
        },
        "tier_promotion_blockers": {
            "blockers": [{"when": {...}, "max_tier": "B"}, ...]
        },
      }

    An empty dict means no active overrides — hardcoded constants apply,
    which is identical behaviour to before this module existed.
    """
    global _cache, _loaded_at

    result: dict[str, Any] = {}
    now = datetime.now(UTC)

    # ── Primary: Supabase ──────────────────────────────────────────────────────
    if db is not None:
        try:
            rows = (
                db.table("runtime_overrides")
                .select("override_key, value_json, effective_from, effective_to")
                .eq("status", "ACTIVE")
                .execute()
            )
            for row in rows.data or []:
                # Respect effective_from / effective_to windows
                ef = row.get("effective_from")
                et = row.get("effective_to")
                if ef:
                    try:
                        ef_dt = datetime.fromisoformat(ef.replace("Z", "+00:00"))
                        if now < ef_dt:
                            log.debug("Override %s: effective_from %s not yet reached", row["override_key"], ef)
                            continue
                    except Exception:
                        pass
                if et:
                    try:
                        et_dt = datetime.fromisoformat(et.replace("Z", "+00:00"))
                        if now > et_dt:
                            log.debug("Override %s: effective_to %s expired", row["override_key"], et)
                            continue
                    except Exception:
                        pass

                val = row.get("value_json")
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except Exception:
                        log.warning("Override %s: could not parse value_json as JSON", row["override_key"])
                        continue
                result[row["override_key"]] = val

            if result:
                log.info("Runtime overrides loaded from Supabase: %s", sorted(result.keys()))
            else:
                log.info(
                    "Runtime overrides: no ACTIVE rows in Supabase — hardcoded synthesize_decision() constants apply"
                )

        except Exception as e:
            log.warning("Supabase runtime_overrides load failed (will try JSON fallback): %s", e)

    # ── Fallback: local JSON ───────────────────────────────────────────────────
    if not result and _FALLBACK_JSON.exists():
        try:
            raw = json.loads(_FALLBACK_JSON.read_text(encoding="utf-8"))
            for key, entry in raw.items():
                if entry.get("status") == "ACTIVE" and key not in result:
                    result[key] = entry.get("value_json", entry)
            if result:
                log.info(
                    "Runtime overrides loaded from JSON fallback (%s): %s", _FALLBACK_JSON.name, sorted(result.keys())
                )
        except Exception as e:
            log.warning("JSON override fallback read failed: %s", e)

    # ── Final state ───────────────────────────────────────────────────────────
    _cache = result
    _loaded_at = now.isoformat()

    if not result:
        log.info("Runtime overrides: empty — hardcoded thresholds apply (normal baseline)")

    return result


def get_overrides() -> dict[str, Any]:
    """
    Return the last-loaded override cache without hitting Supabase again.
    Call load_runtime_overrides() first at process start.
    """
    return _cache
