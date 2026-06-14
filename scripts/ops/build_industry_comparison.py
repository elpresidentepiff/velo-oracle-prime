"""
build_industry_comparison.py
Merges industry tipster selections (from F_0010 PDFs) with VELO picks (from
sigma_audits) and actual race results.  Appends one row per race to:
    data/industry_comparison.csv

Usage:
    python scripts/build_industry_comparison.py --date 2026-05-06
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
DATA_DIR = Path(__file__).parent.parent.parent / "data"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── Tipster canonical names ───────────────────────────────────────────────────
# Ordered by prestige/coverage for display
TIPSTER_ORDER = [
    "SPOTLIGHT",
    "RP RATINGS (Paul Curtis)",
    "RP RATINGS (Ainsley Scorah)",
    "TOPSPEED",
    "POSTDATA",
    "THE TIMES (Rob Wright)",
    "TELEGRAPH (Marlborough)",
    "THE GUARDIAN",
    "DAILY MAIL (Robin Goodfellow)",
    "DAILY MIRROR (Newsboy)",
    "D EXPRESS (Melissa Jones)",
    "THE SUN (Templegate)",
    "THE STAR (Jason Heavey)",
    "DAILY RECORD (Garry Owen)",
    "LAMBOURN (Liam Headd)",
    "NEWMARKET (David Milnes)",
    "WEST COUNTRY (Liam Watson)",
    "THE NORTH (Colin Russell)",
    "THE IRISH SUN",
]

TIPSTER_SHORT = {
    "SPOTLIGHT":                         "SPOT",
    "RP RATINGS (Paul Curtis)":          "RP_PC",
    "RP RATINGS (Ainsley Scorah)":       "RP_AS",
    "TOPSPEED":                          "TOPSPD",
    "POSTDATA":                          "POSTD",
    "THE TIMES (Rob Wright)":            "TIMES",
    "TELEGRAPH (Marlborough)":           "TELE",
    "THE GUARDIAN":                      "GUARD",
    "DAILY MAIL (Robin Goodfellow)":     "MAIL",
    "DAILY MIRROR (Newsboy)":            "MIRROR",
    "D EXPRESS (Melissa Jones)":         "EXPR",
    "THE SUN (Templegate)":              "SUN",
    "THE STAR (Jason Heavey)":           "STAR",
    "DAILY RECORD (Garry Owen)":         "RECORD",
    "LAMBOURN (Liam Headd)":             "LAMB",
    "NEWMARKET (David Milnes)":          "NMKT",
    "WEST COUNTRY (Liam Watson)":        "WEST",
    "THE NORTH (Colin Russell)":         "NORTH",
    "THE IRISH SUN":                     "IRSUN",
}

DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", ""}


def normalize_name(name: str) -> str:
    """Strip country suffix, possessives, and normalise for comparison."""
    s = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", str(name or ""))
    s = s.strip().upper()
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_time(value: str) -> str:
    """Normalise all time formats to H:MM (12h, no leading zero, BST).

    Handles:
      "1:42"  (12h colon, PDF selections)
      "1.42"  (12h dot, SL scraper output)
      "01:42" (leading-zero 12h)
      "13:25" (24h BST, Racing API / PDF results)
    """
    text = str(value or "").strip()
    if not text:
        return ""
    # Normalise dot separator to colon
    text = text.replace(".", ":")
    # Trim to HH:MM or H:MM
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text[:5])
    if not m:
        return text[:5]
    h, mins = int(m.group(1)), m.group(2)
    # Convert 24h → 12h (13→1, 14→2, …, 23→11; 12 stays 12)
    if h > 12:
        h -= 12
    # Strip leading zero: 1:42, not 01:42
    return f"{h}:{mins}"


def _lookup_tipster_bucket(tipsters_data: dict, tipster: str) -> dict:
    exact = tipsters_data.get(tipster)
    if isinstance(exact, dict):
        return exact

    if tipster.startswith("RP RATINGS"):
        for key, bucket in tipsters_data.items():
            if key.upper().startswith("RP RATINGS") and isinstance(bucket, dict):
                return bucket

    return {}


def _lookup_pick_info(tipsters_data: dict, tipster: str, time_key: str) -> dict:
    bucket = _lookup_tipster_bucket(tipsters_data, tipster)
    if not bucket:
        return {}
    alt = time_key[1:] if time_key.startswith("0") else time_key
    return bucket.get(time_key) or bucket.get(alt) or {}


def get_position(horse_name: str, runners: list) -> str | None:
    """Return the finishing position string for a horse in the result set."""
    norm = normalize_name(horse_name)
    for r in runners:
        if normalize_name(r.get("horse", "")) == norm:
            return str(r.get("position", "")).strip().upper()
    return None


def result_code(position: str | None, is_nr: bool = False) -> str:
    """Translate position into W/P/M/NR."""
    if is_nr:
        return "NR"
    if position is None:
        return "M"
    if position in DNF_POSITIONS:
        return "NR"
    try:
        p = int(position)
        if p == 1:
            return "W"
        if p <= 3:
            return "P"
        return "M"
    except ValueError:
        return "NR"


# Normalise API course names to match PDF selection box names
COURSE_ALIASES = {
    "Southwell (AW)": "Southwell (AW)",  # keep as-is (PDF now also uses this)
    "Kempton (AW)":   "Kempton (AW)",
    "Chelmsford City (AW)": "Chelmsford (AW)",
    "Chelmsford (AW)":      "Chelmsford (AW)",
    "Lingfield (AW)":       "Lingfield",
    # PDF filename short codes → full venue names
    "Ain": "Aintree",   "AIN": "Aintree",
    "HAM": "Hamilton",
    "NBY": "Newbury",
    "YOR": "York",
    "CLO": "Clonmel",
    "FON": "Fontwell",
    "PER": "Perth",
    "SAL": "Salisbury",
    "KLB": "Kilbeggan",
    "LEO": "Leopardstown",
    "NMK": "Newmarket",
    "ASC": "Ascot",     "AYR": "Ayr",       "BAT": "Bath",
    "BEV": "Beverley",  "CAT": "Catterick",  "CHL": "Cheltenham",
    "CHP": "Chepstow",  "CHS": "Chester",    "COR": "Cork",
    "CUR": "Curragh",   "DON": "Doncaster",  "EPS": "Epsom",
    "FAI": "Fairyhouse","GOO": "Goodwood",   "GOW": "Gowran Park",
    "HAY": "Haydock",   "KEL": "Kelso",      "KEM": "Kempton (AW)",
    "LEI": "Leicester", "LIM": "Limerick",   "LIN": "Lingfield",
    "LUD": "Ludlow",    "NAA": "Naas",       "NAB": "Newton Abbot",
    "NAV": "Navan",     "NCS": "Newcastle",  "PON": "Pontefract",
    "PUN": "Punchestown","SAN": "Sandown",   "SLI": "Sligo",
    "STH": "Southwell (AW)", "TAU": "Taunton", "WAR": "Warwick",
    "WEX": "Wexford",   "WOL": "Wolverhampton", "YAR": "Yarmouth",
    "RED": "Redcar",    "HUN": "Huntingdon", "MUS": "Musselburgh",
    "CHE": "Chelmsford (AW)", "NOT": "Nottingham", "BRI": "Brighton",
    "EXE": "Exeter",    "WOR": "Worcester",  "PLU": "Plumpton",
    "UTT": "Uttoxeter", "STR": "Stratford",  "BAN": "Bangor-On-Dee",
    "MKT": "Market Rasen", "DRO": "Down Royal", "DUN": "Dundalk",
    "FAK": "Fakenham",  "HER": "Hereford",   "WIN": "Windsor",
    "WDR": "Windsor",   "CHT": "Chepstow",
    # Common AW variants from sigma (lowercase storage)
    "southwell (aw)": "Southwell (AW)", "kempton (aw)": "Kempton (AW)",
    "chelmsford (aw)": "Chelmsford (AW)", "lingfield (aw)": "Lingfield",
    "wolverhampton (aw)": "Wolverhampton",
}

# Case-insensitive fallback lookup (built once at import)
_COURSE_ALIASES_LOWER = {k.lower(): v for k, v in COURSE_ALIASES.items()}


def _norm_course(name: str) -> str:
    course = str(name or "").strip()
    course = re.sub(r"\s*\((IRE|GB|FR)\)\s*$", "", course, flags=re.I)
    # Exact match
    if course in COURSE_ALIASES:
        return COURSE_ALIASES[course]
    # Case-insensitive match (handles sigma_audits lowercase track storage)
    lower = course.lower()
    if lower in _COURSE_ALIASES_LOWER:
        return _COURSE_ALIASES_LOWER[lower]
    # Fallback: title-case normalisation so 'carlisle' → 'Carlisle' matches selections
    return course.title()


def load_results(date_str: str) -> dict:
    """Load results JSON → {(course, off_time): race_dict}."""
    date_tag  = date_str.replace("-", "_")
    path = DATA_DIR / f"results_{date_tag}.json"
    if not path.exists():
        print(f"[WARN] Results file not found: {path}")
        return {}
    raw = json.loads(path.read_text())
    races = raw.get("results", raw) if isinstance(raw, dict) else raw
    index = {}
    for r in races:
        course = _norm_course(r["course"])
        key = (course, normalize_time(r.get("off", "")))
        index[key] = r
    return index


def _parse_horse_from_notes(notes_raw) -> str:
    """Extract predicted horse name from sigma_audits notes field."""
    if not notes_raw:
        return ""
    if isinstance(notes_raw, dict):
        s = notes_raw.get("summary", "")
    else:
        s = str(notes_raw)
    m = re.search(r"pred=([^|]+)", s)
    if m:
        return m.group(1).strip()
    return ""


# Reverse map: full course name → venue code (for selections that store codes)
_COURSE_TO_CODE = {v: k for k, v in {
    "CLO": "Clonmel", "FON": "Fontwell", "PER": "Perth",
    "SAL": "Salisbury", "YOR": "York", "ASC": "Ascot",
    "AYR": "Ayr", "BAT": "Bath", "BEV": "Beverley",
    "CAT": "Catterick", "CHL": "Cheltenham", "CHP": "Chepstow",
    "CHS": "Chester", "COR": "Cork", "CUR": "Curragh",
    "DON": "Doncaster", "DRO": "Down Royal", "DUN": "Dundalk",
    "EPS": "Epsom", "FAI": "Fairyhouse", "FAK": "Fakenham",
    "GOO": "Goodwood", "GOW": "Gowran Park", "HAY": "Haydock",
    "HER": "Hereford", "KEL": "Kelso", "KEM": "Kempton (AW)",
    "LEI": "Leicester", "LEO": "Leopardstown", "LIM": "Limerick",
    "LIN": "Lingfield", "LUD": "Ludlow", "NAA": "Naas",
    "NAB": "Newton Abbot", "NAV": "Navan", "NCS": "Newcastle",
    "NMK": "Newmarket", "PON": "Pontefract", "PUN": "Punchestown",
    "SAN": "Sandown", "SLI": "Sligo", "STH": "Southwell (AW)",
    "TAU": "Taunton", "WAR": "Warwick", "WDR": "Windsor",
    "WIN": "Windsor", "WEX": "Wexford", "WOL": "Wolverhampton",
    "YAR": "Yarmouth", "RED": "Redcar", "HUN": "Huntingdon",
    "MUS": "Musselburgh", "CHE": "Chelmsford (AW)", "NOT": "Nottingham",
    "BRI": "Brighton", "CHT": "Chepstow", "EXE": "Exeter",
    "WOR": "Worcester", "PLU": "Plumpton", "UTT": "Uttoxeter",
    "STR": "Stratford", "BAN": "Bangor-On-Dee", "MKT": "Market Rasen",
}.items()}


def _load_velo_picks_from_local_json(date_str: str) -> dict:
    """
    Fallback: load VELO top picks from velo_prime_verdicts_YYYY_MM_DD.json.
    Stores both full-name and venue-code keys to handle inconsistent selections storage.
    Returns: {(course, off_time): {horse, outcome, tier}}
    """
    date_tag = date_str.replace("-", "_")
    path = DATA_DIR / f"velo_prime_verdicts_{date_tag}.json"
    if not path.exists():
        return {}
    try:
        races = json.loads(path.read_text())
    except Exception:
        return {}
    index = {}
    for race in races:
        top = race.get("top") or {}
        horse = top.get("horse", "")
        if not horse:
            continue
        t = normalize_time(race.get("off_time", ""))
        course = _norm_course(race.get("course", ""))
        vp = top.get("velo_prime_prob")
        try:
            vp_str = f"{float(vp):.2f}" if vp is not None else ""
        except (TypeError, ValueError):
            vp_str = ""
        entry = {
            "horse":   f"{horse}({vp_str})" if vp_str else horse,
            "outcome": "?",
            "tier":    race.get("tier", ""),
        }
        index[(course, t)] = entry
        # Also store under venue code in case selections use code (e.g. "YOR" not "York")
        code = _COURSE_TO_CODE.get(course)
        if code:
            index[(code, t)] = entry
    print(f"  [INFO] VELO picks loaded from local verdicts JSON: {len(races)} races")
    return index


def load_velo_picks(date_str: str) -> dict:
    """
    Load VELO top picks from sigma_audits for date_str.
    Falls back to velo_prime_verdicts_YYYY_MM_DD.json when sigma_audits is empty.
    Returns: {(course, off_time): {horse, outcome, tier}}
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("[WARN] Supabase not configured — falling back to local verdicts JSON")
        return _load_velo_picks_from_local_json(date_str)

    sb = create_client(url, key)
    rows = (
        sb.table("sigma_audits")
        .select("race_id, track, off_time, outcome, decision_tier, notes, miss_reason")
        .eq("date", date_str)
        .execute()
        .data
    )

    if not rows:
        print(f"  [INFO] sigma_audits empty for {date_str} — falling back to local verdicts JSON")
        return _load_velo_picks_from_local_json(date_str)

    index = {}
    for row in rows:
        t = normalize_time(row.get("off_time") or "")
        course = _norm_course(row.get("track", ""))
        horse  = _parse_horse_from_notes(row.get("notes"))
        out_raw = row.get("outcome", "")

        # Normalise outcome to W/P/M/NR
        o = (out_raw or "").strip().upper()
        if o == "WIN":
            code = "W"
        elif o in ("PLACED", "FRAME"):
            code = "P"
        elif "NR" in o or "NON" in o:
            code = "NR"
        elif o == "MISS":
            code = "M"
        else:
            code = "?"

        key = (course, t)
        index[key] = {
            "horse":   horse,
            "outcome": code,
            "tier":    row.get("decision_tier", ""),
        }
    return index


def build_comparison(date_str: str, selections_path: Path):
    """Build one day's comparison rows."""
    sel_data = json.loads(selections_path.read_text())
    results  = load_results(date_str)
    velo     = load_velo_picks(date_str)

    rows = []

    for venue in sel_data["venues"]:
        course = _norm_course(venue["course"])
        tipsters_data = venue["tipsters"]
        race_times = [normalize_time(t) for t in venue["race_times"]]

        for t in race_times:
            key = (course, t)
            race_res = results.get(key)
            if race_res is None:
                # try alternative key with leading zero
                alt = normalize_time(t)
                race_res = results.get((course, alt))

            runners    = race_res.get("runners", []) if race_res else []
            race_name  = race_res.get("race_name", "") if race_res else ""
            field_size = len([r for r in runners if str(r.get("position","")).strip() not in DNF_POSITIONS])

            winner = next(
                (r["horse"] for r in runners if str(r.get("position","")).strip() == "1"),
                "?"
            )
            top3   = {normalize_name(r["horse"]) for r in runners
                      if str(r.get("position","")).strip() in ("1","2","3")}

            # VELO pick
            vp        = velo.get(key, {})
            velo_pick = vp.get("horse", "")
            velo_code = vp.get("outcome", "?")

            row = {
                "date":       date_str,
                "course":     course,
                "time":       t,
                "race_name":  race_name,
                "winner":     winner,
                "field_size": field_size,
                "velo_pick":  velo_pick,
                "velo_result":velo_code,
            }

            # Industry tipsters
            for tipster in TIPSTER_ORDER:
                short = TIPSTER_SHORT.get(tipster, tipster[:6])
                pick_info = _lookup_pick_info(tipsters_data, tipster, t)
                horse = pick_info.get("horse", "")
                is_nap = pick_info.get("is_nap", False)

                if horse and runners:
                    pos = get_position(horse, runners)
                    code = result_code(pos)
                else:
                    code = ""

                row[f"{short}_pick"]    = f"{horse}{'★' if is_nap else ''}"
                row[f"{short}_result"]  = code

            rows.append(row)

    return rows


def append_to_csv(rows: list, csv_path: Path):
    """Append rows to the cumulative comparison CSV, skipping duplicates."""
    fieldnames = list(rows[0].keys()) if rows else []

    existing_keys = set()
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_keys.add((r["date"], r["course"], r["time"]))

    new_rows = [r for r in rows
                if (r["date"], r["course"], r["time"]) not in existing_keys]

    if not new_rows:
        print("No new rows to append (all already exist in CSV).")
        return 0

    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)

    return len(new_rows)


def print_table(rows: list, date_str: str):
    """Print a compact comparison table to console."""
    tipster_shorts = [TIPSTER_SHORT[t] for t in TIPSTER_ORDER if t in TIPSTER_SHORT]

    print(f"\n{'='*120}")
    print(f"INDUSTRY vs VELO — {date_str}")
    print(f"{'='*120}")

    # Header
    hdr = f"{'COURSE':18s} {'TIME':5s} {'WINNER':25s} {'VELO':18s} "
    hdr += " ".join(f"{s:8s}" for s in ["SPOT","RP_PC","RP_AS","TOPSPD","POSTD",
                                          "TIMES","TELE","GUARD","MAIL","MIRROR","SUN"])
    print(hdr)
    print("-" * 120)

    venue_stats = {}  # course → {wins, picks}
    tipster_stats = {s: {"W":0,"P":0,"M":0,"NR":0,"total":0} for s in tipster_shorts}
    velo_stats = {"W":0,"P":0,"M":0,"NR":0,"total":0}

    for row in rows:
        course   = row["course"]
        t        = row["time"]
        winner   = row["winner"][:24]
        velo_p   = (row["velo_pick"] or "—")[:17]
        velo_r   = row["velo_result"]

        velo_flag = {"W": "✓", "P": "~", "M": "✗", "NR": "NR", "?": "?"}.get(velo_r, "?")

        if velo_r and velo_r != "?":
            velo_stats["total"] += 1
            velo_stats[velo_r] = velo_stats.get(velo_r, 0) + 1

        line = f"{course:18s} {t:5s} {winner:25s} {velo_p:17s}{velo_flag} "

        for short in ["SPOT","RP_PC","RP_AS","TOPSPD","POSTD","TIMES","TELE","GUARD","MAIL","MIRROR","SUN"]:
            pick = row.get(f"{short}_pick", "")
            res  = row.get(f"{short}_result", "")
            flag = {"W": "✓", "P": "~", "M": "✗", "NR": "NR"}.get(res, "·")
            cell = pick[:7] if pick else "—"
            line += f"{cell:7s}{flag} "

            if res and short in tipster_stats:
                tipster_stats[short]["total"] += 1
                tipster_stats[short][res] = tipster_stats[short].get(res, 0) + 1

        print(line)

    print("-" * 120)

    # Summary row
    def sr(stats):
        t = stats.get("total", 0) or 1
        w = stats.get("W", 0)
        p = stats.get("P", 0)
        return f"SR={w}/{t}={100*w//t}% FR={(w+p)}/{t}={100*(w+p)//t}%"

    print(f"\nVELO         : {sr(velo_stats)}")
    for short in ["SPOT","RP_PC","RP_AS","TOPSPD","POSTD","TIMES","TELE","GUARD","MAIL","MIRROR","SUN"]:
        st = tipster_stats.get(short, {})
        if st.get("total", 0) > 0:
            print(f"{short:12s} : {sr(st)}")

    print()


def run(date_str: str):
    date_tag = date_str.replace("-", "")
    sel_path = DATA_DIR / f"industry_selections_{date_tag}.json"
    csv_path = DATA_DIR / "industry_comparison.csv"

    if not sel_path.exists():
        print(f"Selections file not found: {sel_path}")
        print(f"Run:  python scripts/parse_industry_selections.py {date_str}")
        sys.exit(1)

    print(f"Building comparison for {date_str}...")
    rows = build_comparison(date_str, sel_path)
    print(f"  Races: {len(rows)}")

    print_table(rows, date_str)

    n = append_to_csv(rows, csv_path)
    print(f"Appended {n} new rows → {csv_path}")



def show_leaderboard(csv_path: Path = None):
    """Print cumulative leaderboard from the comparison CSV."""
    if csv_path is None:
        csv_path = DATA_DIR / "industry_comparison.csv"
    if not csv_path.exists():
        print("No comparison CSV found yet. Run build first.")
        return

    tipster_shorts = [TIPSTER_SHORT[t] for t in TIPSTER_ORDER if t in TIPSTER_SHORT]
    stats = {}  # short → {W, P, M, NR, total}
    velo_stats = {"W": 0, "P": 0, "M": 0, "NR": 0, "total": 0}

    dates_seen = set()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates_seen.add(row["date"])

            vr = row.get("velo_result", "")
            if vr and vr != "?":
                velo_stats["total"] += 1
                velo_stats[vr] = velo_stats.get(vr, 0) + 1

            for short in tipster_shorts:
                res = row.get(f"{short}_result", "")
                if not res:
                    continue
                if short not in stats:
                    stats[short] = {"W": 0, "P": 0, "M": 0, "NR": 0, "total": 0}
                stats[short]["total"] += 1
                stats[short][res] = stats[short].get(res, 0) + 1

    n_dates = len(dates_seen)
    dates_sorted = sorted(dates_seen)
    date_range = f"{dates_sorted[0]} → {dates_sorted[-1]}" if dates_sorted else "—"

    print(f"\n{'='*72}")
    print(f"VELO vs INDUSTRY LEADERBOARD")
    print(f"Dates: {date_range}  ({n_dates} day{'s' if n_dates!=1 else ''})")
    print(f"{'='*72}")
    print(f"{'TIPSTER':14s}  {'n':>5s}  {'W':>5s}  {'SR%':>5s}  {'W+P':>5s}  {'FR%':>5s}  {'RANK':>5s}")
    print("-" * 72)

    # Build ranking list
    entries = []

    vt = velo_stats
    if vt["total"] > 0:
        sr = 100 * vt["W"] / vt["total"]
        fr = 100 * (vt["W"] + vt["P"]) / vt["total"]
        entries.append(("VELO★", vt["total"], vt["W"], sr, vt["W"]+vt["P"], fr))

    for short in tipster_shorts:
        st = stats.get(short, {})
        n = st.get("total", 0)
        if n == 0:
            continue
        w = st.get("W", 0)
        p = st.get("P", 0)
        sr = 100 * w / n
        fr = 100 * (w + p) / n
        entries.append((short, n, w, sr, w + p, fr))

    # Sort by SR desc
    entries.sort(key=lambda e: (-e[3], -e[5]))

    for rank, (name, n, w, sr, wp, fr) in enumerate(entries, 1):
        velo_flag = " ←" if name == "VELO★" else ""
        print(f"{name:14s}  {n:5d}  {w:5d}  {sr:5.1f}%  {wp:5d}  {fr:5.1f}%  #{rank}{velo_flag}")

    print("-" * 72)
    print(f"SR% = strike rate (wins only) | FR% = frame rate (top 3)")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-05-06")
    ap.add_argument("--leaderboard", action="store_true", help="Show cumulative leaderboard")
    args = ap.parse_args()

    if args.leaderboard:
        show_leaderboard()
    else:
        run(args.date)
