
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "incoming_pdfs"
DATE = "2026-05-03"

VENUES = {
    "NMK": "Newmarket",
    "SLI": "Sligo",
    "COR": "Cork",
    "SAL": "Salisbury",
    "HAM": "Hamilton"
}

def run_ingest():
    for code, name in VENUES.items():
        print(f"\nProcessing {name} ({code})...")
        
        # Match files
        or_pdf = list(PDF_DIR.glob(f"{code}_{DATE.replace('-', '')}*_OR_*.pdf"))
        ts_pdf = list(PDF_DIR.glob(f"{code}_{DATE.replace('-', '')}*_TS_*.pdf"))
        xx_pdfs = sorted(list(PDF_DIR.glob(f"{code}_{DATE.replace('-', '')}*_XX_*.pdf")))
        
        if not or_pdf:
            print(f"  [SKIP] OR PDF not found for {code}")
            continue
            
        cmd = [
            str(ROOT / "venv" / "bin" / "python3"),
            str(ROOT / "scripts" / "ingest_racecard_pdfs.py"),
            "--date", DATE,
            "--venue", code,
            "--or", str(or_pdf[0]),
            "--ts", str(ts_pdf[0]) if ts_pdf else "",
        ]
        
        # XX files often contain Spotlight (11) and Postdata (12/16)
        # The script help says --spotlight and --postdata
        # Based on naming: 0011 is usually Spotlight, 0012 is Postdata
        for xx in xx_pdfs:
            if "_0011_" in xx.name:
                cmd.extend(["--spotlight", str(xx)])
            elif "_0012_" in xx.name:
                cmd.extend(["--postdata", str(xx)])
        
        print(f"  Command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

if __name__ == "__main__":
    run_ingest()
