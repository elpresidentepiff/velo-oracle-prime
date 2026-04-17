"""
Evidence Builder — gathers all deterministic intelligence for a race
and packages it into a structured dict ready for VOX to narrate.

Sources (in order):
  1. Racing API — racecard (runners, SP, going, trainer, jockey, form)
  2. Supabase runner_race_facts — rpdc_tag_base, rpdc_confidence, rpdc_evidence
  3. Supabase rpdc_tags_2025 / rpdc_tags_2024 — historical tag for each horse
  4. Supabase horse_comments — spotlight NLP flags
  5. Supabase trainer_profiles — trainer win%, course stats

This module is READ-ONLY — it never writes to the DB.
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rpd.rpdc_rules import tag_from_live_runner

# ── Racing API ────────────────────────────────────────────────────────────────
_RAPI_USER = os.getenv("RACING_API_USERNAME", "")
_RAPI_PASS = os.getenv("RACING_API_PASSWORD", "")
_RAPI_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")

# ── Supabase ──────────────────────────────────────────────────────────────────
_SB_TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN", "")
_SB_REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]


def _rapi(endpoint: str, params: dict | None = None) -> dict | list:
    r = requests.get(
        f"{_RAPI_BASE}/{endpoint.lstrip('/')}",
        auth=(_RAPI_USER, _RAPI_PASS),
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _fetch_race_from_card(race_id: str) -> dict:
    """Fetch today's racecards and return the matching race dict."""
    data = _rapi("racecards")
    races = data if isinstance(data, list) else data.get("racecards", [])
    for race in races:
        if str(race.get("race_id", "")) == str(race_id):
            return race
    raise ValueError(f"Race {race_id} not found in today's racecards ({len(races)} races available)")


def _sql(query: str, timeout: int = 30) -> list:
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{_SB_REF}/database/query",
        headers={
            "Authorization": f"Bearer {_SB_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=timeout,
    )
    result = r.json()
    if isinstance(result, dict) and "message" in result:
        raise ValueError(f"Supabase: {result['message']}")
    return result


def _fetch_rpdc_from_db(horse_name: str) -> dict | None:
    """
    Look up the most recent historical RPD-C tag for a horse from the intelligence stack.

    Priority:
      1. Exact name match in 2025 (most recent year first)
      2. LIKE match in 2025 (handles "(GB)", "(IRE)" suffix differences)
      3. Exact match in 2024
      4. LIKE match in 2024

    Returns the richest tag: if operator has set an override, surfaces that too.
    Uses the view (includes rpdc_evidence_json for clean retrieval).
    """
    safe = horse_name.replace("'", "''")

    for year in [2025, 2024]:
        # Exact first, then LIKE fallback
        for where in [
            f"lower(horse_name_raw) = lower($${horse_name}$$)",
            f"lower(horse_name_raw) LIKE lower('%{safe}%')",
        ]:
            rows = _sql(f"""
                SELECT
                    rpdc_tag_base,
                    rpdc_confidence,
                    rpdc_evidence,
                    rpdc_evidence_json,
                    rpdc_blockers_json,
                    rpdc_explanation,
                    rpdc_override_tag,
                    rpdc_override_reason,
                    date,
                    horse_name_raw
                FROM intelligence.rpdc_tags_{year}_view
                WHERE {where}
                ORDER BY date DESC
                LIMIT 1
            """)
            if rows:
                row = rows[0]
                # If operator override is set, it wins
                if row.get("rpdc_override_tag"):
                    row["_overridden"] = True
                    row["rpdc_tag_base"] = row["rpdc_override_tag"]
                return row
    return None


def _fetch_rpdc_history(horse_name: str, limit: int = 5) -> list[dict]:
    """Return last N historical RPD-C tags for a horse (for trend context in briefings)."""
    safe = horse_name.replace("'", "''")
    rows = _sql(f"""
        SELECT date, rpdc_tag_base, rpdc_confidence, rpdc_evidence_json, rpdc_explanation
        FROM intelligence.rpdc_tags_2025_view
        WHERE lower(horse_name_raw) LIKE lower('%{safe}%')
        ORDER BY date DESC LIMIT {limit}
    """)
    if not rows:
        rows = _sql(f"""
            SELECT date, rpdc_tag_base, rpdc_confidence, rpdc_evidence_json, rpdc_explanation
            FROM intelligence.rpdc_tags_2024_view
            WHERE lower(horse_name_raw) LIKE lower('%{safe}%')
            ORDER BY date DESC LIMIT {limit}
        """)
    return rows or []


def build_race_evidence(race_id: str) -> dict:
    """
    Build a complete evidence packet for a race.

    Returns:
        {
          "race": { venue, date, time, class, distance, going, prize, type },
          "runners": [
            {
              "name", "trainer", "jockey", "sp_decimal", "or_rating", "form",
              "rpdc_tag_base", "rpdc_confidence", "rpdc_evidence", "rpdc_explanation",
              "rpdc_source",          # "historical" | "live"
              "trainer_win_pct",
              "spotlight_flags",
              "days_since_last_run",
              "headgear",
            }
          ]
        }
    """
    print(f"[evidence] Fetching racecard for race_id={race_id}")

    # 1. Racing API racecard — fetch all today's races, find this one
    race_raw = _fetch_race_from_card(race_id)

    race_info = {
        "venue":       race_raw.get("course", ""),
        "date":        race_raw.get("date", ""),
        "time":        race_raw.get("off_time", ""),
        "class":       str(race_raw.get("race_class", "")),
        "distance":    race_raw.get("distance", ""),
        "going":       race_raw.get("going_detailed") or race_raw.get("going", ""),
        "prize":       race_raw.get("prize", ""),
        "type":        race_raw.get("type", ""),
        "race_name":   race_raw.get("race_name", ""),
        "num_runners": race_raw.get("field_size", len(race_raw.get("runners", []))),
        "surface":     race_raw.get("surface", ""),
    }

    runners_out = []
    for runner in race_raw.get("runners", []):
        horse_name = runner.get("horse", "")
        trainer    = runner.get("trainer", "")
        jockey     = runner.get("jockey", "")

        # trainer 14-day stats come directly from the runner payload
        t14 = runner.get("trainer_14_days") or {}

        # 2. Live RPD-C tag
        live_tag = tag_from_live_runner(runner, race_raw)

        # 3. Historical intelligence stack tag (higher confidence)
        hist_tag = None
        try:
            hist_tag = _fetch_rpdc_from_db(horse_name)
        except Exception as e:
            print(f"  [evidence] rpdc db lookup failed for {horse_name}: {e}")

        # Resolve RPD-C tag: historical intelligence stack > live tagger
        # Historical tags (from 253k-row intelligence stack) carry real evidence.
        # Live tagger (rpdc_rules.tag_from_live_runner) is always low-confidence fallback.
        if hist_tag and hist_tag.get("rpdc_tag_base"):
            overridden  = hist_tag.get("_overridden", False)
            rpdc_tag    = hist_tag["rpdc_tag_base"]
            rpdc_conf   = hist_tag["rpdc_confidence"]
            # Use JSONB evidence if available (from view), else fall back to TEXT[]
            ev_json = hist_tag.get("rpdc_evidence_json")
            rpdc_ev = (
                ev_json if isinstance(ev_json, list)
                else hist_tag.get("rpdc_evidence") or []
            )
            rpdc_expl   = hist_tag.get("rpdc_explanation") or ""
            rpdc_src    = (
                f"operator-override ({hist_tag.get('date','')})" if overridden
                else f"intelligence-stack ({hist_tag.get('date','')})"
            )
            rpdc_override_tag    = hist_tag.get("rpdc_override_tag")
            rpdc_override_reason = hist_tag.get("rpdc_override_reason")
        else:
            rpdc_tag             = live_tag.rpdc_tag_base
            rpdc_conf            = live_tag.rpdc_confidence
            rpdc_ev              = live_tag.rpdc_evidence
            rpdc_expl            = live_tag.rpdc_explanation
            rpdc_src             = "live-only (no historical record)"
            rpdc_override_tag    = None
            rpdc_override_reason = None

        # RPD-C history (trend context — last 3 runs from intelligence stack)
        rpdc_history = []
        try:
            rpdc_history = _fetch_rpdc_history(horse_name, limit=3)
        except Exception:
            pass

        # Spotlight: Racing API runner payload (primary — always fresh)
        spotlight_text = runner.get("spotlight", "") or runner.get("comment", "")

        runners_out.append({
            "name":               horse_name,
            "horse_id":           runner.get("horse_id", ""),
            "trainer":            trainer,
            "trainer_rtf":        runner.get("trainer_rtf", ""),
            "trainer_14d_runs":   t14.get("runs", ""),
            "trainer_14d_wins":   t14.get("wins", ""),
            "trainer_14d_pct":    t14.get("percent", ""),
            "jockey":             jockey,
            "number":             runner.get("number", ""),
            "draw":               runner.get("draw", ""),
            "or_rating":          runner.get("ofr", ""),
            "rpr":                runner.get("rpr", ""),
            "ts":                 runner.get("ts", ""),
            "form":               runner.get("form", ""),
            "age":                runner.get("age", ""),
            "weight_lbs":         runner.get("lbs", ""),
            "headgear":           runner.get("headgear", ""),
            "days_since_last_run": runner.get("last_run", ""),
            "past_results_flags": runner.get("past_results_flags", []),
            "spotlight":          spotlight_text,
            "rpdc_tag_base":         rpdc_tag,
            "rpdc_confidence":       rpdc_conf,
            "rpdc_evidence":         rpdc_ev,
            "rpdc_explanation":      rpdc_expl,
            "rpdc_source":           rpdc_src,
            "rpdc_override_tag":     rpdc_override_tag,
            "rpdc_override_reason":  rpdc_override_reason,
            "rpdc_history":          rpdc_history,
        })

    return {"race": race_info, "runners": runners_out}
