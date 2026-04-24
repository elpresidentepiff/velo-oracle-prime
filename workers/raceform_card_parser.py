#!/usr/bin/env python3.11
"""
VÉLØ F_0003 Raceform Card Parser
==================================
Parses the F_0003 Raceform Card PDF.

Row format (space-separated tokens):
  STALL FORM STYLE+NAME DAYS HEADGEAR? TRAINER% GOING1 GOING2 AGE WEIGHT HEADGEAR?
  DIST_STAT GOING_STAT OR FUTURE_OR TS_LATEST TS_MASTER RPR_LATEST RPR_MASTER+JOCKEY JOCKEY... ODDS

Key quirk: RPR_MASTER is concatenated directly onto the start of the jockey's first name
  e.g. "116Ciaran" = RPR_MASTER=116, jockey starts with "Ciaran"
  e.g. "117Harry" = RPR_MASTER=117, jockey starts with "Harry"
"""

import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required.")
    sys.exit(1)


RACE_TIME_SIMPLE_RE = re.compile(r"^(\d{1,2}\.\d{2})\s+\S")
SKIP_LINES = {"Raceform", "Number", "cards", "For ", "each ", "Penalty"}


def _parse_wr(wr_str: str) -> tuple[int, int]:
    if not wr_str:
        return 0, 0
    parts = wr_str.split("-")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 0, 0


def _parse_dist_stat(tok: str) -> tuple[int, int, int | None]:
    """Parse '2-3116' -> (wins=2, runs=3, best_or=116) or '0-00' -> (0,0,None)."""
    m = re.match(r"^(\d+)-(\d+?)(\d{2,3})?$", tok)
    if not m:
        return 0, 0, None
    wins = int(m.group(1))
    runs_raw = m.group(2)
    or_raw = m.group(3)
    # runs_raw could be "3" (runs=3) or "00" (runs=0, no wins)
    runs = int(runs_raw)
    best_or = int(or_raw) if or_raw else None
    return wins, runs, best_or


def _split_rpr_jockey(tok: str) -> tuple[int | None, str]:
    """Split '116Ciaran' into (116, 'Ciaran') or '117Harry' into (117, 'Harry')."""
    m = re.match(r"^(\d{2,3})([A-Z].*)$", tok)
    if m:
        return int(m.group(1)), m.group(2)
    # Could be just a number
    if re.match(r"^\d+$", tok):
        return int(tok), ""
    return None, tok


def parse_raceform_card_pdf(pdf_path) -> dict:
    """Parse F_0003 Raceform Card PDF. Returns dict: race_time -> {race_info, horses}."""
    if pdf_path is None:
        return {}
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {}

    result = {}
    current_race_time = None
    current_race_info = ""
    current_horses = []
    pending_line = None

    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    for raw_line in all_lines:
        line = raw_line.strip()
        if not line:
            continue

        # Skip header/meta lines
        if any(line.startswith(s) for s in SKIP_LINES):
            continue
        if line.startswith("racing") or line.startswith("cards"):
            continue

        # Race time line — must NOT start with a stall number
        m_time = RACE_TIME_SIMPLE_RE.match(line)
        if m_time and not re.match(r"^\d{1,2}\s+[0-9PFURpfur\-/]+", line):
            # Flush pending horse
            if pending_line:
                h = _parse_horse_row(pending_line)
                if h:
                    current_horses.append(h)
                pending_line = None
            # Save previous race
            if current_race_time and current_horses:
                result[current_race_time] = {
                    "race_info": current_race_info,
                    "horses": current_horses,
                }
            current_race_time = m_time.group(1)
            current_race_info = line[len(m_time.group(0)):].strip()
            current_horses = []
            continue

        # Horse row starts with stall number + form + style
        if re.match(r"^\d{1,2}\s+[0-9PFURpfur\-/]+\s+[HPLM]", line):
            if pending_line:
                # Flush pending
                h = _parse_horse_row(pending_line)
                if h:
                    current_horses.append(h)
                pending_line = None
            pending_line = line
            continue

        # Continuation line (trainer name split across lines)
        if pending_line:
            # Check if this continuation line itself contains a new race time
            m_inner = RACE_TIME_SIMPLE_RE.match(line)
            if m_inner and not re.match(r"^\d{1,2}\s+[0-9PFURpfur\-/]+", line):
                # Flush the pending horse first (incomplete but try)
                h = _parse_horse_row(pending_line)
                if h:
                    current_horses.append(h)
                pending_line = None
                # Start new race
                if current_race_time and current_horses:
                    result[current_race_time] = {
                        "race_info": current_race_info,
                        "horses": current_horses,
                    }
                current_race_time = m_inner.group(1)
                current_race_info = line[len(m_inner.group(0)):].strip()
                current_horses = []
                continue
            combined = pending_line + " " + line
            h = _parse_horse_row(combined)
            if h:
                current_horses.append(h)
                pending_line = None
            else:
                pending_line = combined
            continue

    # Flush last pending
    if pending_line:
        h = _parse_horse_row(pending_line)
        if h:
            current_horses.append(h)

    # Save last race
    if current_race_time and current_horses:
        result[current_race_time] = {
            "race_info": current_race_info,
            "horses": current_horses,
        }

    return result


def _parse_horse_row(line: str) -> dict | None:
    """Parse a single F_0003 horse row into a structured dict."""
    line = line.strip()
    tokens = line.split()

    try:
        # ── Token 0: stall ───────────────────────────────────────────────────
        stall = int(tokens[0])

        # ── Token 1: form string ─────────────────────────────────────────────
        form_string = tokens[1]

        # ── Token 2: STYLE+NAME (no space) ───────────────────────────────────
        style_name = tokens[2]
        running_style = style_name[0]  # H, P, L, M
        name_part1 = style_name[1:]    # rest of first name word

        # ── Tokens 3..N: rest of name, then DAYS+headgear, then trainer... ──
        # Find where days (integer) appears — that ends the name
        # Name tokens: name_part1 + more words until we hit "NNhg" or "NN " pattern
        name_tokens = [name_part1]
        idx = 3
        days_since = None
        headgear = ""

        while idx < len(tokens):
            tok = tokens[idx]
            # Days token: digits optionally followed by headgear letters (D, BF, etc.)
            m_days = re.match(r"^(\d+)([A-Za-z]*)$", tok)
            if m_days and not tok[0].isalpha():
                days_since = int(m_days.group(1))
                headgear = m_days.group(2).replace("D", "").replace("BF", "").strip()
                idx += 1
                break
            name_tokens.append(tok)
            idx += 1

        horse_name = " ".join(name_tokens).strip()

        # ── Trainer name + win% ───────────────────────────────────────────────
        # Trainer tokens run until we hit "NN%" token
        trainer_tokens = []
        trainer_win_pct = None

        while idx < len(tokens):
            tok = tokens[idx]
            # Check if this token ends with % (trainer win%)
            m_pct = re.match(r"^(.+?)(\d+)%$", tok)
            if m_pct:
                trainer_tokens.append(m_pct.group(1)) if m_pct.group(1) else None
                trainer_win_pct = int(m_pct.group(2))
                idx += 1
                break
            trainer_tokens.append(tok)
            idx += 1

        trainer_name = " ".join(t for t in trainer_tokens if t).strip()

        # ── Going stats: W-R W-R (or W-R W-R W-R) ────────────────────────────
        going_stats = []
        while idx < len(tokens) and re.match(r"^\d+-\d+$", tokens[idx]):
            going_stats.append(tokens[idx])
            idx += 1

        trainer_gf_hd = going_stats[0] if len(going_stats) > 0 else "0-0"
        trainer_good = going_stats[1] if len(going_stats) > 1 else "0-0"
        trainer_gs_hvy = going_stats[2] if len(going_stats) > 2 else None

        # ── Age ───────────────────────────────────────────────────────────────
        age = int(tokens[idx]) if idx < len(tokens) and tokens[idx].isdigit() else None
        idx += 1

        # ── Weight (e.g. "12-0") ─────────────────────────────────────────────
        weight = None
        if idx < len(tokens) and re.match(r"^\d+-\d+$", tokens[idx]):
            weight = tokens[idx]
            idx += 1

        # ── Optional extra headgear after weight (t, h, p, b, v, w, ht, etc.) ─
        if idx < len(tokens) and re.match(r"^[a-z]{1,3}$", tokens[idx]) and not tokens[idx].isdigit():
            headgear = (headgear + " " + tokens[idx]).strip()
            idx += 1
        # Also handle "t1" (tongue tie + 1lb claim notation)
        if idx < len(tokens) and re.match(r"^[a-z]{1,2}\d$", tokens[idx]):
            headgear = (headgear + " " + tokens[idx]).strip()
            idx += 1

        # ── 4 combined stat columns (GF-Hd, Good, GS-Hvy, Distance) ─────────
        # Each is like "2-3116" (wins-runs+best_or) or "0-00" (no wins)
        # We consume all tokens that match the combined stat pattern
        combined_stats = []
        while idx < len(tokens) and re.match(r"^\d+-\d+", tokens[idx]):
            combined_stats.append(tokens[idx])
            idx += 1

        # The last combined stat is the Distance stat (most useful)
        # The one before last is GS-Hvy going stat
        dist_stat_tok = combined_stats[-1] if combined_stats else None
        going_stat_tok = combined_stats[-2] if len(combined_stats) >= 2 else None
        dist_wins, dist_runs, dist_best_or = _parse_dist_stat(dist_stat_tok) if dist_stat_tok else (0, 0, None)
        going_wins, going_runs, going_best_or = _parse_dist_stat(going_stat_tok) if going_stat_tok else (0, 0, None)

        # ── Remaining numeric stats: OR, future_OR, TS_latest, TS_master, RPR_latest+jockey ──
        # Collect remaining tokens
        remaining = tokens[idx:]

        # Find the token that has RPR_master concatenated with jockey name
        # Pattern: "116Ciaran" or "117Harry" — digits followed by uppercase letter
        rpr_jockey_idx = None
        for j, tok in enumerate(remaining):
            if re.match(r"^\d{2,3}[A-Z]", tok):
                rpr_jockey_idx = j
                break

        current_or = None
        future_or = None
        ts_latest = None
        ts_master = None
        rpr_latest = None
        rpr_master = None
        jockey = ""
        sp_odds = ""
        non_runner = False

        if rpr_jockey_idx is not None:
            # Numeric stats before the rpr_latest+jockey token
            # Layout: OR future_OR TS_latest TS_master [RPR_latest+jockey]
            # The concatenated token IS RPR_latest (not RPR_master)
            # Actual column order per header: OR | future | TS_latest | TS_master | RPR_latest | RPR_master
            # But RPR_latest is concatenated with jockey, so:
            # remaining[0]=OR, [1]=future_OR, [2]=TS_latest, [3]=TS_master, [rpr_jockey_idx]=RPR_latest+jockey
            num_toks = remaining[:rpr_jockey_idx]
            after_rpr = remaining[rpr_jockey_idx:]

            # Parse the rpr_latest+jockey token
            rpr_latest_val, jockey_first = _split_rpr_jockey(after_rpr[0])
            rpr_latest = rpr_latest_val

            # Remaining jockey tokens + odds
            jockey_rest = after_rpr[1:]
            if jockey_rest and (re.match(r"^\d+[-\/]\d+$", jockey_rest[-1]) or jockey_rest[-1] == "EVS"):
                sp_odds = jockey_rest[-1]
                jockey_rest = jockey_rest[:-1]
            elif jockey_rest and jockey_rest[-1] == "NON-RUNNER":
                non_runner = True
                jockey_rest = jockey_rest[:-1]

            jockey = (jockey_first + " " + " ".join(jockey_rest)).strip()

            # Parse numeric stats: OR, future_OR, TS_latest, TS_master
            nums = []
            for t in num_toks:
                try:
                    nums.append(int(t))
                except ValueError:
                    nums.append(None)

            if len(nums) >= 1: current_or = nums[0]
            if len(nums) >= 2: future_or = nums[1]
            if len(nums) >= 3: ts_latest = nums[2]
            if len(nums) >= 4: ts_master = nums[3]
            if len(nums) >= 5: rpr_master = nums[4]
            # rpr_latest already set from the concatenated token

        else:
            # No rpr+jockey concatenation found — try to parse what we have
            # Last token might be odds
            if remaining and re.match(r"^\d+[-\/]\d+$|^EVS$", remaining[-1]):
                sp_odds = remaining[-1]
                remaining = remaining[:-1]
            elif remaining and remaining[-1] == "NON-RUNNER":
                non_runner = True
                remaining = remaining[:-1]

            # Find where jockey name starts (first uppercase non-digit token near end)
            jockey_start = len(remaining)
            for j in range(len(remaining) - 1, -1, -1):
                if remaining[j] and remaining[j][0].isupper() and not remaining[j][0].isdigit():
                    jockey_start = j
                else:
                    break
            jockey = " ".join(remaining[jockey_start:]).strip()
            num_toks = remaining[:jockey_start]
            nums = []
            for t in num_toks:
                try:
                    nums.append(int(t))
                except ValueError:
                    nums.append(None)
            if len(nums) >= 1: current_or = nums[0]
            if len(nums) >= 2: future_or = nums[1]
            if len(nums) >= 3: ts_latest = nums[2]
            if len(nums) >= 4: ts_master = nums[3]
            if len(nums) >= 5: rpr_latest = nums[4]
            if len(nums) >= 6: rpr_master = nums[5]

        # Trainer going stats
        tr_gf_w, tr_gf_r = _parse_wr(trainer_gf_hd)
        tr_g_w, tr_g_r = _parse_wr(trainer_good)
        tr_gs_w, tr_gs_r = _parse_wr(trainer_gs_hvy) if trainer_gs_hvy else (0, 0)

        return {
            "horse_name": horse_name,
            "stall": stall,
            "form_string": form_string,
            "running_style": running_style,
            "days_since_last_run": days_since,
            "headgear": headgear,
            "trainer": trainer_name,
            "trainer_win_pct_14d": trainer_win_pct,
            "trainer_gf_hd_w": tr_gf_w,
            "trainer_gf_hd_r": tr_gf_r,
            "trainer_good_w": tr_g_w,
            "trainer_good_r": tr_g_r,
            "trainer_gs_hvy_w": tr_gs_w,
            "trainer_gs_hvy_r": tr_gs_r,
            "age": age,
            "weight": weight,
            "dist_wins": dist_wins,
            "dist_runs": dist_runs,
            "dist_best_or": dist_best_or,
            "going_wins": going_wins,
            "going_runs": going_runs,
            "going_best_or": going_best_or,
            "current_or": current_or,
            "future_or": future_or,
            "ts_latest_rc": ts_latest,
            "ts_master_rc": ts_master,
            "rpr_latest_rc": rpr_latest,
            "rpr_master_rc": rpr_master,
            "jockey": jockey,
            "sp_forecast": sp_odds,
            "non_runner": non_runner,
        }

    except Exception:
        return None


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not pdf_path:
        print("Usage: python raceform_card_parser.py <pdf_path>")
        sys.exit(1)

    data = parse_raceform_card_pdf(pdf_path)
    total = 0
    for race_time, race in sorted(data.items()):
        print(f"\n{race_time} — {race['race_info'][:70]}")
        print(f"  Horses: {len(race['horses'])}")
        for h in race["horses"]:
            nr = " [NR]" if h.get("non_runner") else ""
            print(f"    {h['horse_name']:<28} OR={h['current_or']} TS={h['ts_latest_rc']} RPR={h['rpr_latest_rc']} "
                  f"RPR_M={h['rpr_master_rc']} J={str(h['jockey']):<22} T={str(h['trainer'])[:20]} "
                  f"{h['trainer_win_pct_14d']}% style={h['running_style']} SP={h['sp_forecast']}{nr}")
        total += len(race["horses"])
    print(f"\nTOTAL: {total} horses")
