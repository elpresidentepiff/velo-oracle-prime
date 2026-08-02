#!/usr/bin/env python3
"""
build_canonical_model_scorecard.py

Read-only canonical model scorecard builder. Produces one row per
(race, model/lane/proxy) with model rank, policy decision, dashboard
visibility, odds, and result kept as separate, explicit columns -- per
docs/current/MODEL_RESULT_REPORTING_LAW.md.

No Supabase writes. No Telegram. No scoring. No model changes.

Usage:
  PYTHONPATH=. python scripts/ops/build_canonical_model_scorecard.py --date 2026-07-05
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.verdict_loader import load_verdicts  # noqa: E402


def _date_tag(date: str) -> str:
    return date.replace("-", "_")


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ensure_env() -> None:
    """Load .env into os.environ. Kept separate from _sb_get because
    verdict_loader reads SUPABASE_URL directly at call time and raises if it
    is unset -- and it is now called before the first _sb_get, so the old
    lazy load inside _sb_get was no longer early enough."""
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass


def _sb_get(path: str) -> list[dict]:
    """Read-only Supabase REST GET. Returns [] on any failure -- never raises,
    never writes."""
    _ensure_env()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return []
    req = urllib.request.Request(
        url + "/rest/v1" + path,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return []


def _load_results(date: str) -> dict[str, dict]:
    path = ROOT / "data" / "results" / f"rp_results_{_date_tag(date)}.json"
    payload = _load_json(path, {})
    return {str(r.get("race_id") or ""): r for r in payload.get("results") or [] if r.get("race_id")}


def _runner_lookup(result_race: dict, horse_name: str) -> dict:
    """Find a runner's horse_id/sp_dec/position/win/frame from a results race dict, by name."""
    if not result_race:
        return {}
    key = _norm(horse_name)
    for runner in result_race.get("runners") or []:
        if _norm(runner.get("horse")) == key:
            pos = str(runner.get("position") or runner.get("pos") or "").upper()
            return {
                "horse_id": runner.get("horse_id"),
                "sp_dec": runner.get("sp_dec"),
                "position": pos,
                "win": pos == "1",
                "frame": pos in {"1", "2", "3"},
            }
    return {}


def _tie_status(values: list[float]) -> str:
    if not values:
        return "NO_DATA"
    max_v = max(values)
    tied = sum(1 for v in values if v == max_v)
    if tied <= 1:
        return "CLEAN"
    return f"TIED_{tied}_WAY"


def build_scorecard(date: str) -> tuple[list[dict], dict]:
    tag = _date_tag(date)
    results = _load_results(date)

    rows: list[dict] = []
    audit: dict[str, Any] = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_found": {},
        "sources_missing": {},
        "row_count": 0,
        "ties_found": [],
    }

    def _add_row(**kw) -> None:
        base = {
            "date": date, "race_id": None, "course": None, "off_time": None,
            "model_name": None, "lane_name": None, "source_path": None,
            "source_field": None, "sort_direction": None, "rank": None,
            "horse": None, "horse_id": None, "score": None, "sp_dec": None,
            "result_position": None, "win": None, "frame": None,
            "policy_decision": None, "stake_authorised": None,
            "dashboard_visible": None, "learning_class": None,
            "tie_status": "N/A", "notes": "",
        }
        base.update(kw)
        rows.append(base)

    # ── Main VELO Prime + No-RPR shadow (Supabase, read-only) ──────────────
    # generated_at is WRITE time, not race date. Filtering by a same-day
    # generated_at window silently returned zero rows whenever a day was not
    # scored inside its own calendar day -- i.e. the normal evening-before
    # manual pattern, and any recovery/backfill run. Caught 2026-08-01 while
    # recovering 2026-07-31: the day scored cleanly (49 races, 49 verified
    # Supabase writes) yet the canonical scorecard recorded
    # velo_verdicts=MISSING and persisted no MAIN_VELO_PRIME rows at all.
    # This is the documented bug class from docs/current/ONE_TRUTH.md; the
    # shared loader resolves by race_id membership first and reports which
    # path it used. This script was missed by the 12-script sweep.
    _ensure_env()
    try:
        verdicts, _verdict_method = load_verdicts(
            date, select="race_id,full_analysis,top_rank_horse_id"
        )
    except Exception as _e:
        verdicts, _verdict_method = [], f"LOAD_ERROR:{_e}"
    if not verdicts:
        audit["sources_missing"]["velo_verdicts"] = f"no rows for date (verdict_loader method={_verdict_method})"
    else:
        audit["sources_found"]["velo_verdicts"] = len(verdicts)
        audit["verdict_load_method"] = _verdict_method

    for v in verdicts:
        race_id = str(v.get("race_id") or "")
        fa = v.get("full_analysis")
        if isinstance(fa, str):
            try:
                fa = json.loads(fa)
            except Exception:
                fa = {}
        preds = (fa or {}).get("predictions") or []
        result_race = results.get(race_id)
        course = (result_race or {}).get("course")
        off_time = (result_race or {}).get("off")

        # Main VELO top pick = highest velo_prime_prob
        if preds:
            ranked_vp = sorted(preds, key=lambda p: p.get("velo_prime_prob") or 0.0, reverse=True)
            vp_values = [p.get("velo_prime_prob") or 0.0 for p in preds]
            top = ranked_vp[0]
            outcome = _runner_lookup(result_race, top.get("horse", ""))
            _add_row(
                race_id=race_id, course=course, off_time=off_time,
                model_name="MAIN_VELO_PRIME", lane_name="main",
                source_path="Supabase velo_verdicts.full_analysis.predictions[]",
                source_field="velo_prime_prob", sort_direction="descending",
                rank=1, horse=top.get("horse"), horse_id=outcome.get("horse_id") or top.get("horse_id"),
                score=top.get("velo_prime_prob"), sp_dec=outcome.get("sp_dec"),
                result_position=outcome.get("position"), win=outcome.get("win"), frame=outcome.get("frame"),
                policy_decision="N/A (no policy layer for Main VELO -- persists directly)",
                stake_authorised=False, dashboard_visible=True,
                learning_class="MODEL_HIT" if outcome.get("win") else "MODEL_MISS",
                tie_status=_tie_status(vp_values),
                notes="Main VELO's own top-ranked pick.",
            )

            # No-RPR shadow top pick = highest sqpe_no_rpr_shadow_prob, with explicit tie check
            no_rpr_values = [p.get("sqpe_no_rpr_shadow_prob") or 0.0 for p in preds]
            ranked_nr = sorted(preds, key=lambda p: p.get("sqpe_no_rpr_shadow_prob") or 0.0, reverse=True)
            nr_top = ranked_nr[0]
            nr_tie = _tie_status(no_rpr_values)
            nr_outcome = _runner_lookup(result_race, nr_top.get("horse", ""))
            if nr_tie != "CLEAN":
                audit["ties_found"].append({"race_id": race_id, "field": "sqpe_no_rpr_shadow_prob", "tie_status": nr_tie})
            _add_row(
                race_id=race_id, course=course, off_time=off_time,
                model_name="SQPE_NO_RPR_SHADOW", lane_name="shadow",
                source_path="Supabase velo_verdicts.full_analysis.predictions[]",
                source_field="sqpe_no_rpr_shadow_prob", sort_direction="descending",
                rank=1, horse=nr_top.get("horse"), horse_id=nr_outcome.get("horse_id") or nr_top.get("horse_id"),
                score=nr_top.get("sqpe_no_rpr_shadow_prob"), sp_dec=nr_outcome.get("sp_dec"),
                result_position=nr_outcome.get("position"), win=nr_outcome.get("win"), frame=nr_outcome.get("frame"),
                policy_decision="N/A (no policy layer for this shadow field)",
                stake_authorised=False, dashboard_visible=True,
                learning_class="TIE_UNRESOLVED" if nr_tie != "CLEAN" else ("MODEL_HIT" if nr_outcome.get("win") else "MODEL_MISS"),
                tie_status=nr_tie,
                notes="Top pick is not a principled read if tie_status != CLEAN." if nr_tie != "CLEAN" else "",
            )

    # ── New Build Lane A / B / C (two_lane_readiness) ──────────────────────
    readiness_path = ROOT / "data" / "new_build" / "reports" / f"two_lane_readiness_{tag}.json"
    readiness = _load_json(readiness_path, {})
    feed_path = ROOT / "data" / "new_build" / "current_cards" / f"current_card_passport_feed_{tag}.jsonl"
    feed_rows = _read_jsonl(feed_path)
    feed_by_race_horse = {(str(r.get("race_id")), _norm(r.get("horse"))): r for r in feed_rows}

    if not readiness:
        audit["sources_missing"]["two_lane_readiness"] = str(readiness_path)
    else:
        audit["sources_found"]["two_lane_readiness"] = readiness_path.name

    for card in readiness.get("race_day_scorecards") or []:
        race_id = str(card.get("race_id") or "")
        result_race = results.get(race_id)
        course = (result_race or {}).get("course") or card.get("course")
        off_time = (result_race or {}).get("off") or card.get("off_time")

        for lane_key, model_name, dashboard_visible in [
            ("lane_a_top3", "NEW_BUILD_LANE_A_MODEL", True),
            ("lane_b_top3", "NEW_BUILD_LANE_B_MODEL", False),
            ("lane_c_top3", "NEW_BUILD_LANE_C_MODEL", False),
        ]:
            top3 = sorted(card.get(lane_key) or [], key=lambda x: x.get("rank", 99))
            for entry in top3:
                horse = entry.get("horse") or ""
                feed_row = feed_by_race_horse.get((race_id, _norm(horse)), {})
                outcome = _runner_lookup(result_race, horse)
                policy = entry.get("nb_decision_lane") if lane_key == "lane_a_top3" or lane_key == "lane_b_top3" else "N/A (Lane C not policy-anchored)"
                stake_ok = policy in ("WIN_TRUST", "FRAME_TRUST")
                _add_row(
                    race_id=race_id, course=course, off_time=off_time,
                    model_name=model_name, lane_name=lane_key.replace("_top3", ""),
                    source_path=str(readiness_path.relative_to(ROOT)),
                    source_field=f"race_day_scorecards[].{lane_key}.prob", sort_direction="descending",
                    rank=entry.get("rank"), horse=horse,
                    horse_id=outcome.get("horse_id") or feed_row.get("rp_uid"),
                    score=entry.get("prob"), sp_dec=outcome.get("sp_dec"),
                    result_position=outcome.get("position"), win=outcome.get("win"), frame=outcome.get("frame"),
                    policy_decision=policy, stake_authorised=stake_ok,
                    dashboard_visible=dashboard_visible,
                    learning_class=(
                        "MODEL_HIT_POLICY_BLOCKED" if outcome.get("win") and policy not in ("WIN_TRUST", "FRAME_TRUST")
                        else "MODEL_HIT_POLICY_CLEARED" if outcome.get("win")
                        else "MODEL_MISS"
                    ),
                    tie_status="N/A",
                    notes="Dashboard-visible via new_build_top3 (server reads lane_a_top3 only)." if dashboard_visible else "Not served by the live dashboard -- present only in this local readiness file.",
                )

        # passport_strength_score proxy row(s) -- explicitly labelled proxy, not a model
        race_feed = [r for (rid, _), r in feed_by_race_horse.items() if rid == race_id]
        if race_feed:
            ranked_proxy = sorted(race_feed, key=lambda r: r.get("passport_strength_score") if r.get("passport_strength_score") is not None else -999, reverse=True)
            for idx, r in enumerate(ranked_proxy[:3], start=1):
                horse = r.get("horse") or ""
                outcome = _runner_lookup(result_race, horse)
                _add_row(
                    race_id=race_id, course=course, off_time=off_time,
                    model_name="PASSPORT_STRENGTH_SCORE_PROXY", lane_name="proxy_not_a_model",
                    source_path=str(feed_path.relative_to(ROOT)) if feed_path.exists() else str(feed_path),
                    source_field="passport_strength_score", sort_direction="descending (imposed; field has no native sort semantics)",
                    rank=idx, horse=horse, horse_id=r.get("rp_uid"),
                    score=r.get("passport_strength_score"), sp_dec=outcome.get("sp_dec"),
                    result_position=outcome.get("position"), win=outcome.get("win"), frame=outcome.get("frame"),
                    policy_decision="N/A (feature input, not a model with a policy layer)",
                    stake_authorised=False, dashboard_visible=False,
                    learning_class="PROXY_NOT_A_MODEL_CLAIM",
                    tie_status="N/A",
                    notes="This is a feature-engineering input INTO Lane A/B/C, not their output. Never cite as New Build's result.",
                )

    # ── Old VELO WIN/PLACE/LONGSHOT (if snapshot-derived card exists) ───────
    old_velo_path = ROOT / "data" / "reports" / f"old_velo_three_option_card_{tag}.json"
    old_velo = _load_json(old_velo_path, {})
    if not old_velo:
        audit["sources_missing"]["old_velo_three_option_card"] = str(old_velo_path)
    else:
        audit["sources_found"]["old_velo_three_option_card"] = old_velo_path.name
        for race in old_velo.get("races") or []:
            race_id = str(race.get("race_id") or "")
            result_race = results.get(race_id)
            for pick in race.get("picks") or []:
                # The three-option card is deliberately frozen at pick-time (see
                # build_old_velo_three_option_card.py's refusal to rebuild post-results
                # -- "morning selections are frozen once made"). Its own pick["outcome"]
                # field is therefore permanently NO_RESULT/null. Look up the real result
                # independently instead, same as the New Build and Champion Intent blocks
                # above -- found 2026-07-16 via this builder itself reporting 0% wins for
                # all three Old VELO roles despite MAIN_VELO_PRIME (the identical WIN pick)
                # showing real wins.
                outcome = _runner_lookup(result_race, pick.get("horse"))
                _add_row(
                    race_id=race_id, course=race.get("course"), off_time=race.get("off_time"),
                    model_name=f"OLD_VELO_{pick.get('role')}_ROLE", lane_name=pick.get("role"),
                    source_path=str(old_velo_path.relative_to(ROOT)),
                    source_field=f"picks[].{'velo_prime_prob' if pick.get('role') == 'WIN' else 'place_prob' if pick.get('role') == 'PLACE' else 'longshot_role_score'} (role={pick.get('role')})",
                    sort_direction="descending", rank=1,
                    horse=pick.get("horse"), horse_id=outcome.get("horse_id") or pick.get("horse_id"),
                    score=pick.get("velo_prime_prob") if pick.get("role") == "WIN" else pick.get("place_prob") if pick.get("role") == "PLACE" else pick.get("longshot_role_score"),
                    sp_dec=outcome.get("sp_dec") or pick.get("sp_dec"),
                    result_position=outcome.get("position"), win=outcome.get("win"), frame=outcome.get("frame"),
                    policy_decision="N/A (Old VELO has no policy layer)",
                    stake_authorised=False, dashboard_visible=False,
                    learning_class="MODEL_HIT" if outcome.get("win") else "MODEL_MISS",
                    tie_status="N/A",
                    notes="WIN role is identical to Main VELO's own pick by construction.",
                )

    # ── Champion Intent Shadow (intent_shadow_scorecard CSV) ────────────────
    champion_path = ROOT / "data" / "reports" / f"intent_shadow_scorecard_{tag}.csv"
    if not champion_path.exists():
        audit["sources_missing"]["champion_intent_shadow"] = str(champion_path)
    else:
        audit["sources_found"]["champion_intent_shadow"] = champion_path.name
        with champion_path.open(encoding="utf-8") as f:
            champion_rows = list(csv.DictReader(f))
        for crow in champion_rows:
            race_id = str(crow.get("race_id") or "")
            result_race = results.get(race_id)
            horse = crow.get("horse") or ""
            outcome = _runner_lookup(result_race, horse)
            try:
                rank = int(crow.get("rank_in_race")) if crow.get("rank_in_race") not in (None, "") else None
            except ValueError:
                rank = None
            try:
                score = float(crow.get("champion_intent_shadow_prob")) if crow.get("champion_intent_shadow_prob") not in (None, "") else None
            except ValueError:
                score = None
            velo_scoring_allowed = str(crow.get("velo_scoring_allowed", "")).strip().lower() == "true"
            _add_row(
                race_id=race_id,
                course=(result_race or {}).get("course") or crow.get("course"),
                off_time=(result_race or {}).get("off") or crow.get("off_time"),
                model_name="CHAMPION_INTENT_SHADOW", lane_name="shadow_only",
                source_path=str(champion_path.relative_to(ROOT)),
                source_field="champion_intent_shadow_prob", sort_direction="descending",
                rank=rank, horse=horse, horse_id=outcome.get("horse_id") or crow.get("rp_uid"),
                score=score, sp_dec=outcome.get("sp_dec"),
                result_position=outcome.get("position"), win=outcome.get("win"), frame=outcome.get("frame"),
                policy_decision=crow.get("trust_policy") or "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                stake_authorised=(str(crow.get("stake_authorised", "")).strip().lower() == "true"),
                dashboard_visible=(str(crow.get("dashboard_visible", "")).strip().lower() == "true"),
                learning_class=crow.get("learning_class") or ("MODEL_HIT_POLICY_BLOCKED" if outcome.get("win") else "MODEL_MISS"),
                tie_status="N/A",
                notes=(
                    "SHADOW_ONLY -- velo_scoring_allowed=False, no live scoring authority. "
                    "Measurement only, not a promotable claim by this row alone."
                    if not velo_scoring_allowed else ""
                ),
            )

    # ── Mid-Price Specialist Shadow (midprice_shadow packet) ────────────────
    # Added 2026-07-30 (operator-approved). Until now this lane existed only in
    # data/model_comparison_ledger.csv, so it was absent from the canonical
    # spine ONE_TRUTH names as the operational truth source — the same
    # "generated but never persisted" shape as the Champion gap fixed on
    # 2026-07-16. Records the whole in-band field per race (rank 1..n), not
    # just the top pick, so rank-depth questions stay answerable.
    midprice_path = ROOT / "data" / "reports" / f"midprice_shadow_{tag}.json"
    if not midprice_path.exists():
        audit["sources_missing"]["midprice_specialist_shadow"] = str(midprice_path)
    else:
        audit["sources_found"]["midprice_specialist_shadow"] = midprice_path.name
        mp_packet = json.loads(midprice_path.read_text(encoding="utf-8"))
        # midprice_shadow_{date}.json carries only horse NAMES (horse,
        # midprice_prob, odds_decimal, in_band) -- no horse_id. Taking the id
        # solely from the results join meant every midprice row was written
        # with horse_id=NULL by the pre-race morning persist, and Postgres
        # treats NULLs as distinct in a UNIQUE constraint, so the post-results
        # persist could never update those rows -- it inserted a second full
        # copy instead (2026-07-30: 385 -> 770 rows, 397 NULL ids). That also
        # left the canonical table violating MODEL_RESULT_REPORTING_LAW, which
        # requires horse_id on every model claim. Resolve real ids from the
        # same-date racecard cache, which exists morning AND evening, so the
        # conflict key is stable across both persists. Verified 2026-07-30:
        # 385/385 midprice horses resolve to a real racecard horse_id.
        _mp_ids: dict[str, Any] = {}
        for _card in sorted((ROOT / "data" / "racecard_merged").glob(f"racecard_*_{date}.json")):
            try:
                _c = json.loads(_card.read_text(encoding="utf-8"))
            except Exception:
                continue
            _races = _c.get("races") or {}
            for _race in (_races.values() if isinstance(_races, dict) else _races):
                for _h in (_race.get("horses") or []):
                    _n = str(_h.get("horse_name") or "").strip().lower()
                    if _n and _h.get("horse_id") is not None:
                        _mp_ids.setdefault(_n, _h["horse_id"])
        audit["midprice_horse_id_lookup_size"] = len(_mp_ids)
        _mp_seen_races: set[str] = set()
        for mp_race in mp_packet.get("races", []):
            race_id = str(mp_race.get("race_id") or "")
            # The midprice packet can list the same race twice (2026-07-18: 65
            # race entries for 61 distinct ids). Emitting both copies produced
            # rows sharing a conflict key, and Postgres rejects the ENTIRE upsert
            # with 21000 "ON CONFLICT DO UPDATE command cannot affect row a
            # second time" -- so four duplicated races cost that whole date its
            # persist, leaving it at 0 wins in the canonical table while its CSV
            # held 271. Keep the first occurrence.
            if race_id in _mp_seen_races:
                audit.setdefault("midprice_duplicate_races_skipped", []).append(race_id)
                continue
            _mp_seen_races.add(race_id)
            result_race = results.get(race_id)
            band_runners = [r for r in (mp_race.get("all_scored") or []) if r.get("in_band")]
            for idx, mp_runner in enumerate(band_runners, start=1):
                horse = mp_runner.get("horse") or ""
                outcome = _runner_lookup(result_race, horse)
                prob = mp_runner.get("midprice_prob")
                _add_row(
                    race_id=race_id,
                    course=(result_race or {}).get("course") or mp_race.get("course"),
                    off_time=(result_race or {}).get("off") or mp_race.get("off"),
                    model_name="MIDPRICE_SPECIALIST_SHADOW", lane_name="shadow_only",
                    source_path=str(midprice_path.relative_to(ROOT)),
                    source_field="midprice_prob", sort_direction="descending",
                    rank=idx, horse=horse,
                    horse_id=outcome.get("horse_id") or _mp_ids.get(horse.strip().lower()),
                    score=prob, sp_dec=outcome.get("sp_dec") or mp_runner.get("odds_decimal"),
                    result_position=outcome.get("position"), win=outcome.get("win"),
                    frame=outcome.get("frame"),
                    policy_decision=mp_packet.get("trust_policy") or "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                    stake_authorised=False,
                    dashboard_visible=True,
                    learning_class=("MODEL_HIT_POLICY_BLOCKED" if outcome.get("win") else "MODEL_MISS"),
                    tie_status="N/A",
                    notes=(
                        f"SHADOW_ONLY -- LAB_EXPERIMENT specialist ({mp_packet.get('model_version')}), "
                        f"market-blind, band {mp_packet.get('mid_price_band')}. "
                        "velo_scoring_allowed=False. Watch-gate subset is midprice_prob>=0.30 "
                        "(needs n>=150 before any verdict). Not a promotable claim."
                    ),
                )

    audit["row_count"] = len(rows)
    return rows, audit


CSV_COLUMNS = [
    "date", "race_id", "course", "off_time", "model_name", "lane_name",
    "source_path", "source_field", "sort_direction", "rank", "horse",
    "horse_id", "score", "sp_dec", "result_position", "win", "frame",
    "policy_decision", "stake_authorised", "dashboard_visible",
    "learning_class", "tie_status", "notes",
]


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in CSV_COLUMNS})


def _write_summary(rows: list[dict], audit: dict, date: str, path: Path) -> None:
    lines = [
        f"# Canonical Model Scorecard — {date}",
        f"Generated: {audit['generated_at']}",
        "",
        f"Total rows: {audit['row_count']}",
        "",
        "## Sources found",
    ]
    for k, v in audit["sources_found"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Sources missing")
    for k, v in audit["sources_missing"].items():
        lines.append(f"- {k}: {v}")
    if audit["ties_found"]:
        lines += ["", "## Ties found (do not trust a single top-pick number for these races)"]
        for t in audit["ties_found"]:
            lines.append(f"- race {t['race_id']}: {t['field']} is {t['tie_status']}")
    lines += ["", "## Model hits with policy-blocked stake"]
    for r in rows:
        if r.get("learning_class") == "MODEL_HIT_POLICY_BLOCKED":
            lines.append(
                f"- {r['model_name']} rank {r['rank']}: {r['horse']} (SP {r['sp_dec']}) in race {r['race_id']} "
                f"— policy: {r['policy_decision']}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canonical model scorecard (read-only).")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    rows, audit = build_scorecard(args.date)
    tag = _date_tag(args.date)
    out_dir = ROOT / "data" / "reports"
    csv_path = out_dir / f"canonical_model_scorecard_{tag}.csv"
    summary_path = out_dir / f"canonical_model_scorecard_{tag}_summary.md"
    audit_path = out_dir / f"canonical_model_scorecard_{tag}_audit.json"

    _write_csv(rows, csv_path)
    _write_summary(rows, audit, args.date, summary_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    print(f"CANONICAL_SCORECARD_COMPLETE date={args.date} rows={len(rows)}")
    print(f"csv={csv_path}")
    print(f"summary={summary_path}")
    print(f"audit={audit_path}")


if __name__ == "__main__":
    main()
