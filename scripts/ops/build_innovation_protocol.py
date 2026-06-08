"""
build_innovation_protocol.py
=============================
Builds and maintains the deduplicated Innovation Protocol dataset.

Modes:
  python scripts/build_innovation_protocol.py
      Default: append any new verdict dates not already in the CSV.

  python scripts/build_innovation_protocol.py --rebuild
      Full rebuild from all verdict + result files on disk.

  python scripts/build_innovation_protocol.py --date 2026-04-29
      Append a specific race date only.

Output:
  data/velo_innovation_protocol_1k_deduped.csv

Deduplication key:
  race_id + normalized horse name (lowercase, alpha only)
  Duplicate policy: keep first occurrence (verdicts ordered oldest→newest).
  Near-identical rows (same race+horse, <0.001 VP diff): keep first.

Safety:
  - No model changes
  - No live betting
  - No Telegram calls
  - Data files only
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build_protocol")

import pandas as pd  # noqa: E402

from src.velo.product_router import ProductRouter  # noqa: E402


class ModelManager:
    @staticmethod
    def _parse_class(class_str) -> float:
        import re as _re
        s = str(class_str or "").strip().upper()
        m = _re.search(r"CLASS\s*(\d)", s)
        if m:
            return float(m.group(1))
        if "GROUP 1" in s or "GRADE 1" in s:
            return 1.0
        if "GROUP 2" in s or "GRADE 2" in s:
            return 2.0
        if "LISTED" in s:
            return 2.5
        return 4.0

DEDUPED_PATH = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
VERDICTS_GLOB = "velo_prime_verdicts_*.json"
RESULTS_GLOB = "results_*.json"
CANONICAL_RESULTS_GLOB = "rp_results_*.json"

PLACED_POSITIONS = {1, 2, 3}

SCHEMA_COLS = [
    "race_id", "date", "course", "race_time", "race_type", "class", "class_num",
    "distance", "going", "field_size", "tier", "horse", "horse_id",
    "model_probability", "sp_decimal", "implied_probability", "edge",
    "result_position", "won", "placed", "confidence", "archetype", "macro_chaos",
    "assigned_product", "legacy_execution_allowed", "router_reasons",
    "execution_blockers",
    "candidate_execution_allowed", "candidate_execution_reason", "candidate_execution_lane",
    "candidate_stake", "candidate_return", "candidate_pl",
    "router_v1_shadow_pass", "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist", "router_shadow_lane", "router_shadow_reason",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def _dedup_key(race_id: str, horse: str) -> str:
    return f"{race_id}||{_norm(horse)}"


def _verdict_date(filename: str) -> str:
    """Extract YYYY-MM-DD from velo_prime_verdicts_YYYY_MM_DD.json"""
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _result_date(filename: str) -> str:
    """Extract YYYY-MM-DD from results_YYYY_MM_DD.json"""
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _norm_course(c: str) -> str:
    """Normalise course name: lowercase, strip AW/IRE suffixes, alpha only."""
    c = re.sub(r"\s*\(.*?\)", "", str(c))  # remove (AW), (IRE) etc
    return re.sub(r"[^a-z]", "", c.lower())


def _norm_time(t: str) -> str:
    """Normalise race time to HH:MM 24h string."""
    t = str(t).strip().replace(".", ":")
    parts = t.split(":")
    if len(parts) == 2:
        h, m = int(parts[0]), int(parts[1])
        # If hour looks like 12h (≤12 and we suspect PM from context) leave it
        return f"{h:02d}:{m:02d}"
    return t


# ── Results loader ────────────────────────────────────────────────────────────

def load_results(dates: set[str] | None = None) -> dict:
    """
    Returns nested dict:
      result_lookup[date][norm_course][norm_time][norm_horse] = {
          position, sp_dec, going, race_type, class_, distance
      }
    If dates is provided, only load files for those dates.
    """
    lookup: dict = {}
    canonical_results = sorted((ROOT / "data" / "results").glob(CANONICAL_RESULTS_GLOB))
    legacy_results = sorted((ROOT / "data").glob(RESULTS_GLOB))
    for rf in canonical_results + legacy_results:
        file_date = _result_date(rf.name)
        if dates and file_date not in dates:
            continue
        try:
            raw = json.loads(rf.read_text())
            entries = raw.get("results", raw) if isinstance(raw, dict) else raw
            for race in entries:
                d = race.get("date", file_date)
                nc = _norm_course(race.get("course", ""))
                nt = _norm_time(race.get("off", ""))
                race_type = race.get("type", "")
                going = race.get("going", "")
                class_ = race.get("class", "")
                distance = race.get("dist_f", race.get("dist", ""))
                if d not in lookup:
                    lookup[d] = {}
                if nc not in lookup[d]:
                    lookup[d][nc] = {}
                if nt not in lookup[d][nc]:
                    lookup[d][nc][nt] = {}
                for runner in race.get("runners", []):
                    nh = _norm(runner.get("horse", ""))
                    if nh:
                        lookup[d][nc][nt][nh] = {
                            "position": runner.get("position"),
                            "sp_dec": runner.get("sp_dec"),
                            "going": going,
                            "race_type": race_type,
                            "class_": class_,
                            "distance": distance,
                        }
        except Exception as e:
            log.warning(f"  Results load skip {rf.name}: {e}")
    return lookup


def _lookup_result(result_lookup, date, course, race_time, horse):
    """Try progressively looser matches. Returns dict or {}."""
    d = str(date)
    nc = _norm_course(course)
    nt = _norm_time(race_time)
    nh = _norm(horse)

    date_block = result_lookup.get(d, {})
    course_block = date_block.get(nc, {})

    # Exact time match
    time_block = course_block.get(nt, {})
    if nh in time_block:
        return time_block[nh]

    # Try 12h/24h conversion
    parts = nt.split(":")
    if len(parts) == 2:
        h = int(parts[0])
        for alt_h in [h + 12, h - 12]:
            if 0 <= alt_h <= 23:
                alt_nt = f"{alt_h:02d}:{parts[1]}"
                time_block2 = course_block.get(alt_nt, {})
                if nh in time_block2:
                    return time_block2[nh]

    # Fuzzy time: scan ±1 minute across all time slots for this course
    for t_slot, horses in course_block.items():
        if nh in horses:
            return horses[nh]

    # Fuzzy course: try prefix match
    for nc2, c_block in date_block.items():
        if nc in nc2 or nc2 in nc:
            for t_slot, horses in c_block.items():
                if nh in horses:
                    return horses[nh]

    return {}


# ── Verdict loader ────────────────────────────────────────────────────────────

def load_verdict_rows(verdict_files: list[Path], result_lookup: dict) -> list[dict]:
    router = ProductRouter()
    rows = []

    for vf in verdict_files:
        file_date = _verdict_date(vf.name)
        try:
            verdicts = json.loads(vf.read_text())
        except Exception as e:
            log.warning(f"  Skip {vf.name}: {e}")
            continue

        for v in verdicts:
            race_id = v.get("race_id", "")
            course = v.get("course", "")
            race_time = v.get("off_time", "")
            top = v.get("top", {})
            horse = top.get("horse", "")
            if not horse:
                continue

            vp = float(top.get("velo_prime_prob") or 0)
            tier = v.get("tier", top.get("tier", "X"))
            archetype = top.get("race_archetype", "") or ""
            macro_chaos = bool(top.get("macro_chaos_mode") or False)
            field_size = int(v.get("scored") or v.get("field_size") or 0)
            confidence = top.get("confidence_level", "")
            horse_id = top.get("horse_id", "")

            # Results match
            res = _lookup_result(result_lookup, file_date, course, race_time, horse)
            sp_decimal = float(res.get("sp_dec") or top.get("sp_dec") or 0)
            going = res.get("going") or ""
            race_type = res.get("race_type") or ""
            class_str = res.get("class_") or ""
            distance = res.get("distance") or ""
            pos = res.get("position")
            try:
                pos_int = int(pos) if pos else None
            except Exception:
                pos_int = None
            won = 1 if pos_int == 1 else 0
            placed = 1 if pos_int is not None and pos_int in PLACED_POSITIONS else 0

            class_num = ModelManager._parse_class(class_str)
            implied = 1.0 / sp_decimal if sp_decimal > 0 else 0.0
            edge = vp - implied

            # Legacy route
            lg = router.route_verdict({
                "decision_tier": tier,
                "confidence_level": confidence or "low",
                "actual_winner_sp": 0,
                "prob_gap": float(top.get("prob_gap") or 0),
                "market_deception_score": float(top.get("market_deception_score") or 0),
                "track": course,
                "top_horse_draw": top.get("draw"),
                "field_size": field_size,
                "race_type": race_type,
                "going": going,
                "is_handicap": bool(top.get("is_handicap") or v.get("is_handicap")),
                "fav_sp": float(top.get("fav_sp") or 0),
                "velo_prime_prob": vp,
                "archetype": archetype,
            })

            # Candidate route
            cr = router.candidate_route({
                "velo_prime_prob": vp,
                "field_size": field_size,
                "archetype": archetype,
                "going": going,
                "macro_chaos_mode": macro_chaos,
                "class_num": class_num,
                "sp_decimal": sp_decimal,
                "archetype_suppression": bool(top.get("archetype_suppression") or False),
            })

            # Shadow lane flags
            m_struct = archetype == "Structure"
            m_sp_all = 2.0 <= sp_decimal <= 4.0
            m_sp_34 = 3.0 <= sp_decimal <= 4.0
            m_vp30 = vp >= 0.30
            m_vp35 = vp >= 0.35
            m_fs12 = field_size <= 12
            m_noheavy = "heavy" not in going.lower()
            m_nochaos = archetype != "Chaos"
            m_cl34 = class_num in (3, 4)
            m_cl4 = class_num == 4

            v1 = bool(m_cl34 and m_struct and m_sp_all and m_vp30 and m_fs12 and m_noheavy and m_nochaos)
            v2 = bool(m_cl4 and m_struct and m_sp_all and m_vp30 and m_fs12 and m_noheavy and m_nochaos)
            v6 = bool(m_cl4 and m_struct and m_sp_34 and m_vp35 and m_fs12 and m_noheavy and m_nochaos)

            if v6:
                shadow_lane = "V6_GOLD_SEAM_WATCHLIST"
            elif v2:
                shadow_lane = "V2_CLASS4_SHADOW"
            elif v1:
                shadow_lane = "V1_BASE_SHADOW"
            else:
                shadow_lane = "NO_LANE"

            shadow_reason = (
                f"CL{class_num or '?'}_VP{vp:.3f}_SP{sp_decimal:.1f}_FS{field_size}"
                if v1 else ""
            )

            cand_allowed = cr["candidate_execution_allowed"]
            cand_pl = (sp_decimal - 1.0 if won else -1.0) if cand_allowed else 0.0
            cand_stake = 1.0 if cand_allowed else 0.0
            cand_return = cand_pl + cand_stake if cand_allowed else 0.0

            rows.append({
                "race_id": race_id,
                "date": file_date,
                "course": course,
                "race_time": race_time,
                "race_type": race_type,
                "class": class_str,
                "class_num": class_num,
                "distance": distance,
                "going": going,
                "field_size": field_size,
                "tier": tier,
                "horse": horse,
                "horse_id": horse_id,
                "model_probability": vp,
                "sp_decimal": sp_decimal,
                "implied_probability": implied,
                "edge": edge,
                "result_position": pos,
                "won": won if pos_int is not None else None,
                "placed": placed if pos_int is not None else None,
                "confidence": confidence,
                "archetype": archetype,
                "macro_chaos": macro_chaos,
                "assigned_product": lg.get("assigned_product"),
                "legacy_execution_allowed": lg.get("execution_allowed", False),
                "router_reasons": "|".join(lg.get("router_reasons", [])),
                "execution_blockers": "",
                "candidate_execution_allowed": cand_allowed,
                "candidate_execution_reason": "|".join(cr["candidate_execution_reason"]),
                "candidate_execution_lane": cr["candidate_execution_lane"],
                "candidate_stake": cand_stake,
                "candidate_return": cand_return,
                "candidate_pl": cand_pl,
                "router_v1_shadow_pass": v1,
                "router_v2_class4_shadow_pass": v2,
                "router_v6_gold_seam_watchlist": v6,
                "router_shadow_lane": shadow_lane,
                "router_shadow_reason": shadow_reason,
            })

    return rows


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    df["_dk"] = df.apply(lambda r: _dedup_key(str(r["race_id"]), str(r["horse"])), axis=1)
    # Newly rebuilt rows are appended after the existing dataset and must
    # supersede stale pre-result copies of the same verdict.
    df = df.drop_duplicates(subset="_dk", keep="last").drop(columns=["_dk"])
    return df, before - len(df)


# ── Re-score router on existing rows ─────────────────────────────────────────

def rescore_router(df: pd.DataFrame) -> pd.DataFrame:
    router = ProductRouter()
    v1_list, v2_list, v6_list, lane_list, reason_list = [], [], [], [], []
    cand_a, cand_r, cand_l, cand_pl_list = [], [], [], []

    for _, row in df.iterrows():
        vp = float(row.get("model_probability") or 0)
        fs = int(row.get("field_size") or 0)
        arch = str(row.get("archetype") or "")
        going = str(row.get("going") or "")
        macro = bool(row.get("macro_chaos") or False)
        cn = row.get("class_num")
        cn = int(cn) if cn == cn else 0
        sp = float(row.get("sp_decimal") or 0)
        arch_sup = False

        cr = router.candidate_route({
            "velo_prime_prob": vp, "field_size": fs, "archetype": arch,
            "going": going, "macro_chaos_mode": macro, "class_num": cn,
            "sp_decimal": sp, "archetype_suppression": arch_sup,
        })

        m_struct = arch == "Structure"
        m_sp_all = 2.0 <= sp <= 4.0
        m_sp_34  = 3.0 <= sp <= 4.0
        m_vp30   = vp >= 0.30
        m_vp35   = vp >= 0.35
        m_fs12   = fs <= 12
        m_noheavy = "heavy" not in going.lower()
        m_nochaos = arch != "Chaos"
        m_cl34 = cn in (3, 4)
        m_cl4  = cn == 4

        v1 = bool(m_cl34 and m_struct and m_sp_all and m_vp30 and m_fs12 and m_noheavy and m_nochaos)
        v2 = bool(m_cl4  and m_struct and m_sp_all and m_vp30 and m_fs12 and m_noheavy and m_nochaos)
        v6 = bool(m_cl4  and m_struct and m_sp_34  and m_vp35 and m_fs12 and m_noheavy and m_nochaos)

        lane = "V6_GOLD_SEAM_WATCHLIST" if v6 else "V2_CLASS4_SHADOW" if v2 else "V1_BASE_SHADOW" if v1 else "NO_LANE"
        sreason = f"CL{cn}_VP{vp:.3f}_SP{sp:.1f}_FS{fs}" if v1 else ""

        cand = cr["candidate_execution_allowed"]
        won_val = row.get("won")
        won_flag = int(won_val) if won_val == won_val and won_val is not None else None
        cand_pl = (sp - 1.0 if won_flag == 1 else -1.0) if cand and won_flag is not None else 0.0

        v1_list.append(v1); v2_list.append(v2); v6_list.append(v6)
        lane_list.append(lane); reason_list.append(sreason)
        cand_a.append(cand)
        cand_r.append("|".join(cr["candidate_execution_reason"]))
        cand_l.append(cr["candidate_execution_lane"])
        cand_pl_list.append(cand_pl)

    df = df.copy()
    df["candidate_execution_allowed"]   = cand_a
    df["candidate_execution_reason"]    = cand_r
    df["candidate_execution_lane"]      = cand_l
    df["candidate_pl"]                  = cand_pl_list
    df["candidate_stake"]               = [1.0 if x else 0.0 for x in cand_a]
    df["candidate_return"]              = [pl + st for pl, st in zip(cand_pl_list, [1.0 if x else 0.0 for x in cand_a])]
    df["router_v1_shadow_pass"]         = v1_list
    df["router_v2_class4_shadow_pass"]  = v2_list
    df["router_v6_gold_seam_watchlist"] = v6_list
    df["router_shadow_lane"]            = lane_list
    df["router_shadow_reason"]          = reason_list
    return df


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build deduplicated Innovation Protocol dataset")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from scratch ignoring existing CSV")
    parser.add_argument("--date", help="Append specific date YYYY-MM-DD only")
    parser.add_argument("--rescore-only", action="store_true", help="Re-run router scoring on existing CSV without adding new rows")
    args = parser.parse_args()

    # ── Rescore only ──────────────────────────────────────────────────────────
    if args.rescore_only:
        log.info("Mode: RESCORE ONLY")
        df = pd.read_csv(DEDUPED_PATH, low_memory=False)
        log.info(f"  Loaded {len(df)} rows from {DEDUPED_PATH.name}")
        df = rescore_router(df)
        df.to_csv(DEDUPED_PATH, index=False)
        log.info(f"  Saved {len(df)} rows → {DEDUPED_PATH.name}")
        return

    # ── Load existing base ────────────────────────────────────────────────────
    if DEDUPED_PATH.exists() and not args.rebuild:
        base_df = pd.read_csv(DEDUPED_PATH, low_memory=False)
        existing_dates = set(base_df["date"].dropna().astype(str).unique())
        log.info(f"Existing dataset: {len(base_df)} rows across {len(existing_dates)} dates")
    else:
        base_df = pd.DataFrame(columns=SCHEMA_COLS)
        existing_dates = set()
        log.info("Starting fresh rebuild")

    # ── Identify verdict files to process ────────────────────────────────────
    all_verdict_files = sorted((ROOT / "data").glob(VERDICTS_GLOB))
    if args.date:
        date_tag = args.date.replace("-", "_")
        verdict_files = [f for f in all_verdict_files if date_tag in f.name]
        new_dates = {args.date}
    elif args.rebuild:
        verdict_files = all_verdict_files
        new_dates = {_verdict_date(f.name) for f in verdict_files}
    else:
        verdict_files = [f for f in all_verdict_files if _verdict_date(f.name) not in existing_dates]
        new_dates = {_verdict_date(f.name) for f in verdict_files}

    log.info(f"Verdict files to process: {len(verdict_files)} ({sorted(new_dates)})")

    if not verdict_files and not args.rebuild:
        log.info("No new verdict files. Re-running router scoring on existing rows.")
        df = rescore_router(base_df)
        df, removed = deduplicate(df)
        df.to_csv(DEDUPED_PATH, index=False)
        log.info(f"  Saved {len(df)} rows (dedupe removed {removed})")
        return

    # ── Load results for relevant dates ──────────────────────────────────────
    result_dates = new_dates if not args.rebuild else None
    log.info(f"Loading results for dates: {result_dates or 'ALL'}")
    result_lookup = load_results(result_dates)
    log.info(f"  Result lookup: {sum(len(v) for v in result_lookup.values())} courses across {len(result_lookup)} dates")

    # ── Build new rows ────────────────────────────────────────────────────────
    new_rows = load_verdict_rows(verdict_files, result_lookup)
    log.info(f"New verdict rows built: {len(new_rows)}")

    new_df = pd.DataFrame(new_rows)

    # ── Merge + deduplicate ───────────────────────────────────────────────────
    if args.rebuild:
        combined = new_df
    else:
        combined = pd.concat([base_df, new_df], ignore_index=True)

    original_count = len(combined)

    # Re-run router on all rows (ensures new rules apply everywhere)
    combined = rescore_router(combined)

    combined, removed = deduplicate(combined)
    deduped_count = len(combined)

    log.info(f"\n{'='*50}")
    log.info(f"DEDUPLICATION REPORT")
    log.info(f"{'='*50}")
    log.info(f"  A. Original rows combined:  {original_count}")
    log.info(f"  B. Deduped rows:            {deduped_count}")
    log.info(f"  C. Duplicate rows removed:  {removed}")
    log.info(f"  D. New rows added:          {len(new_rows)}")
    log.info(f"  E. Dates in dataset:        {combined['date'].nunique()}")
    if len(new_rows) > 0:
        new_df2 = pd.DataFrame(new_rows)
        new_df2["_dk"] = new_df2.apply(lambda r: _dedup_key(str(r["race_id"]), str(r["horse"])), axis=1)
        new_df2_deduped = new_df2.drop_duplicates(subset="_dk")
        log.info(f"  F. New deduped rows (this run): {len(new_df2_deduped)}")

    # ── Save ─────────────────────────────────────────────────────────────────
    combined.to_csv(DEDUPED_PATH, index=False)
    log.info(f"\nSaved: {DEDUPED_PATH}")
    log.info(f"Total rows in dataset: {deduped_count}")

    # ── Quick router summary ──────────────────────────────────────────────────
    has_res = combined["result_position"].notna() & (combined["sp_decimal"] > 0)
    log.info(f"\nRouter summary (rows with results: {has_res.sum()}):")
    for lane in ["V1_BASE_SHADOW", "V2_CLASS4_SHADOW", "V6_GOLD_SEAM_WATCHLIST"]:
        mask = (combined["router_shadow_lane"] == lane) & has_res
        sub = combined[mask]
        if len(sub):
            wins = sub["won"].sum()
            pl = float((sub["won"] * (sub["sp_decimal"] - 1) + (1 - sub["won"]) * -1).sum())
            roi = pl / len(sub) * 100
            log.info(f"  {lane}: n={len(sub)}, wins={wins:.0f}, ROI={roi:.1f}%")
        else:
            log.info(f"  {lane}: n=0")


if __name__ == "__main__":
    main()
