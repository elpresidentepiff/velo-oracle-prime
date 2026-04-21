#!/usr/bin/env python3.11
"""Debug: check what time keys each parser produces."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ingest_racecard_pdfs import parse_or_pdf, parse_ts_pdf, parse_spotlight_pdf
from workers.postdata_parser import parse_postdata_pdf
from workers.form_detailed_parser import parse_form_detailed_pdf

d = ROOT / "data" / "incoming_pdfs"

or_data = parse_or_pdf(d / "PON_20260421_00_00_F_0015_OR_Pontefract.pdf")
ts_data = parse_ts_pdf(d / "PON_20260421_00_00_F_0032_TS_Pontefract.pdf")
spot_data = parse_spotlight_pdf(d / "PON_20260421_00_00_F_0016_XX_Pontefract.pdf")
pd_data = parse_postdata_pdf(d / "PON_20260421_00_00_F_0011_XX_Pontefract.pdf")
form_data = parse_form_detailed_pdf(d / "PON_20260421_13_42_O_0006_XX_Pontefract.pdf")

print("OR keys:      ", sorted(or_data.keys()))
print("TS keys:      ", sorted(ts_data.keys()))
print("Spot keys:    ", sorted(spot_data.keys()))
print("PD keys:      ", sorted(pd_data.keys()))
print("Form race_time:", form_data.get("race_time", "?"))
print()

# Show horse counts per source per time
all_times = sorted(set(
    list(or_data.keys()) + list(ts_data.keys()) +
    list(spot_data.keys()) + list(pd_data.keys())
))
print(f"{'Time':<12s} {'OR':>4s} {'TS':>4s} {'Spot':>4s} {'PD':>4s}")
print("-" * 36)
for t in all_times:
    or_c = len(or_data.get(t, {}).get("horses", []))
    ts_c = len(ts_data.get(t, {}).get("horses", []))
    sp_c = len(spot_data.get(t, {}).get("horses", []))
    pd_c = len(pd_data.get(t, {}).get("horses", []))
    print(f"{t:<12s} {or_c:>4d} {ts_c:>4d} {sp_c:>4d} {pd_c:>4d}")
