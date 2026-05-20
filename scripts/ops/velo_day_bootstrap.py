#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Step 1 — Environment Preflight
def check_environment():
    status = {"status": "PASS", "missing": [], "errors": []}
    
    # 1. Check Python executable & venv
    in_venv = sys.prefix != sys.base_prefix
    
    # 2. Check imports
    required_imports = ['loguru', 'dotenv', 'supabase', 'pandas', 'requests']
    for req in required_imports:
        try:
            __import__(req)
        except ImportError:
            status["status"] = "FAIL"
            status["missing"].append(f"import {req}")
    
    # 3. Check .env
    env_path = Path('.env')
    if not env_path.exists():
        status["status"] = "FAIL"
        status["missing"].append(".env file")
    else:
        try:
            import dotenv
            dotenv.load_dotenv()
        except:
            pass
            
        if not os.getenv("SUPABASE_URL"):
            status["status"] = "FAIL"
            status["missing"].append("SUPABASE_URL")
        if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
            status["status"] = "FAIL"
            status["missing"].append("SUPABASE_SERVICE_ROLE_KEY")

    if status["status"] == "FAIL":
        print("============================================================")
        print("ENVIRONMENT PREFLIGHT: FAIL")
        print("Missing dependencies/config:")
        for m in status["missing"]:
            print(f" - {m}")
        print("\nPlease run the following exact commands to fix:")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
        print("============================================================")
        sys.exit(1)
        
    return status

def run_command(cmd, desc):
    print(f"\n[BOOTSTRAP] Running {desc}...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[BOOTSTRAP] ERROR running {desc}:")
        print(result.stderr)
        print(result.stdout)
        return False
    print(f"[BOOTSTRAP] SUCCESS: {desc}")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date
    date_compact = date_str.replace("-", "")
    date_under = date_str.replace("-", "_")
    
    print(f"============================================================")
    print(f"VÉLØ RACE-DAY BOOTSTRAP: {date_str}")
    print(f"============================================================")
    
    env_status = check_environment()
    print(f"ENV_STATUS = {env_status['status']}")
    
    root = Path.cwd()
    data_dir = root / "data"
    
    manifest = {
        "date": date_str,
        "run_at": datetime.now().isoformat(),
        "environment": "PASS",
        "racecards": {"found": False, "source": None, "races": 0, "runners": 0},
        "verdicts": {"found": False, "source": None, "count": 0},
        "results": {"found": False},
        "rp_files": {"status": "NOT_SUPPLIED", "pdfs": []},
        "merged_racecards": {"found": False, "files": [], "coverage": {}},
        "operator_cards": {},
        "missing_items": [],
        "overall_status": "PENDING",
        "next_command": ""
    }

    # Step 2 & 3 — Racecard Discovery & Fetch
    rc_std1 = data_dir / f"racecards_{date_under}_standard.json"
    rc_std2 = data_dir / f"racecards_{date_str}_standard.json"
    
    rc_path = None
    if rc_std1.exists(): rc_path = rc_std1
    elif rc_std2.exists(): rc_path = rc_std2
    
    if not rc_path:
        print("[BOOTSTRAP] Racecards missing. Fetching from Racing API...")
        cmd = [sys.executable, "scripts/run_prime_today.py", "--date", date_str, "--dry-run", "--no-notify"]
        success = run_command(cmd, "Racecard Fetch")
        if success:
            if rc_std1.exists(): rc_path = rc_std1
            elif rc_std2.exists(): rc_path = rc_std2
            
    if rc_path:
        manifest["racecards"]["found"] = True
        manifest["racecards"]["source"] = rc_path.name
        try:
            with open(rc_path, "r") as f:
                rc_data = json.load(f).get("racecards", [])
                manifest["racecards"]["races"] = len(rc_data)
                manifest["racecards"]["runners"] = sum(len(r.get("runners", [])) for r in rc_data)
        except Exception as e:
            manifest["missing_items"].append(f"Failed to read racecards: {e}")
    else:
        manifest["missing_items"].append("Standard Racecards")
        manifest["overall_status"] = "BLOCKED_NO_RACECARDS"
        manifest["next_command"] = f"python scripts/run_prime_today.py --date {date_str} --dry-run --no-notify"
        write_manifest(manifest, date_under)
        sys.exit(1)

    # Step 4 — Racing Post / PDF Ingestion Check
    pdf_dir = data_dir / "incoming_pdfs"
    pdfs = []
    if pdf_dir.exists():
        pdfs = [p for p in pdf_dir.glob("*.pdf") if date_compact in p.name]
    
    if pdfs:
        manifest["rp_files"]["status"] = "SUPPLIED"
        manifest["rp_files"]["pdfs"] = [p.name for p in pdfs]
        # Identify venues
        venues = set()
        for p in pdfs:
            parts = p.name.split("_")
            if len(parts) > 0 and len(parts[0]) == 3:
                venues.add(parts[0].upper())
        
        merged_dir = data_dir / "racecard_merged"
        merged_files = list(merged_dir.glob(f"racecard_*_{date_str}.json"))
        
        if not merged_files:
            print("[BOOTSTRAP] RP files supplied but not merged. Running PDF parser...")
            for v in venues:
                cmd = [sys.executable, "scripts/ingest_racecard_pdfs.py", "--dir", "data/incoming_pdfs/", "--venue", v, "--date", date_str]
                run_command(cmd, f"PDF Ingest ({v})")
            
            merged_files = list(merged_dir.glob(f"racecard_*_{date_str}.json"))
    else:
        manifest["rp_files"]["status"] = "NOT_SUPPLIED"
        print("[BOOTSTRAP] No RP PDFs found. CASHRUN will be BLOCKED.")

    # Step 5 — Merged Racecard Check
    merged_dir = data_dir / "racecard_merged"
    merged_files = list(merged_dir.glob(f"racecard_*_{date_str}.json"))
    if merged_files:
        manifest["merged_racecards"]["found"] = True
        manifest["merged_racecards"]["files"] = [m.name for m in merged_files]
        
        coverage = {"horses": 0, "horse_id": 0, "trainer_id": 0, "jockey_id": 0, "or": 0, "ts": 0, "rpr": 0, "spotlight": 0, "postdata": 0}
        for mf in merged_files:
            with open(mf, "r") as f:
                mc = json.load(f)
                for rt, rd in mc.get("races", {}).items():
                    for h in rd.get("horses", []):
                        coverage["horses"] += 1
                        if h.get("horse_id"): coverage["horse_id"] += 1
                        if h.get("trainer_id") or h.get("trainer"): coverage["trainer_id"] += 1
                        if h.get("jockey_id") or h.get("jockey"): coverage["jockey_id"] += 1
                        if h.get("current_or"): coverage["or"] += 1
                        if h.get("ts_master"): coverage["ts"] += 1
                        if h.get("rpr_master"): coverage["rpr"] += 1
                        if h.get("spotlight_comment"): coverage["spotlight"] += 1
                        if h.get("postdata_score") is not None: coverage["postdata"] += 1
        manifest["merged_racecards"]["coverage"] = coverage

    # Step 6 — Scoring Check
    vd_path1 = data_dir / f"velo_prime_verdicts_{date_under}.json"
    vd_path2 = data_dir / f"velo_prime_verdicts_{date_str}.json"
    vd_path = vd_path1 if vd_path1.exists() else (vd_path2 if vd_path2.exists() else None)
    
    if not vd_path:
        print("[BOOTSTRAP] Verdicts missing. Running scoring (dry-run)...")
        cmd = [sys.executable, "scripts/run_prime_today.py", "--date", date_str, "--dry-run", "--no-notify"]
        success = run_command(cmd, "Scoring")
        if success:
            vd_path = vd_path1 if vd_path1.exists() else (vd_path2 if vd_path2.exists() else None)

    if vd_path:
        manifest["verdicts"]["found"] = True
        manifest["verdicts"]["source"] = vd_path.name
        try:
            with open(vd_path, "r") as f:
                vd_data = json.load(f)
                if isinstance(vd_data, dict) and "verdicts" in vd_data:
                    manifest["verdicts"]["count"] = len(vd_data["verdicts"])
                elif isinstance(vd_data, list):
                    manifest["verdicts"]["count"] = len(vd_data)
        except: pass
    else:
        manifest["missing_items"].append("Verdicts")
        manifest["overall_status"] = "BLOCKED_NO_VERDICTS"
        manifest["next_command"] = f"python scripts/run_prime_today.py --date {date_str} --dry-run --no-notify"
        write_manifest(manifest, date_under)
        sys.exit(1)

    # Step 7 — Operator Card Generation
    print("[BOOTSTRAP] Verdicts exist. Generating operator cards...")
    
    # VP30
    cmd_vp30 = [sys.executable, "scripts/place_signal_operator_card.py", "--date", date_str]
    success_vp30 = run_command(cmd_vp30, "VP30 Operator Card")
    manifest["operator_cards"]["vp30"] = "PASS" if success_vp30 else "FAIL"

    # Racing API Enrichment
    cmd_api = [sys.executable, "scripts/racing_api_enrichment_operator_card.py", "--date", date_str]
    success_api = run_command(cmd_api, "Racing API Enrichment Card")
    manifest["operator_cards"]["racing_api_enrichment"] = "PASS" if success_api else "FAIL"
    
    # CASHRUN
    if manifest["rp_files"]["status"] == "SUPPLIED" and manifest["merged_racecards"]["found"]:
        cmd_cash = [sys.executable, "scripts/cashrun_detector.py", date_str]
        success_cash = run_command(cmd_cash, "CASHRUN Detector")
        manifest["operator_cards"]["cashrun"] = "PASS" if success_cash else "FAIL"
    else:
        manifest["operator_cards"]["cashrun"] = "BLOCKED_RP_FILES_MISSING"

    # Step 8 — Daily Readiness Status
    vp30_status = manifest["operator_cards"].get("vp30")
    api_status = manifest["operator_cards"].get("racing_api_enrichment")
    
    # Check for unresolved metadata (?) or signal values (MISSING) in MD files
    metadata_ok = True
    signal_values_ok = True
    
    for md_file in data_dir.glob(f"*card_{date_str}.md"):
        content = md_file.read_text()
        # Metadata check
        if "| ? |" in content or "/ ?" in content or "MISSING METADATA" in content and "(0 rows)" not in content and " 0 rows" not in content:
            metadata_ok = False
            
        # Signal value check
        if "VP=MISSING" in content or "MDS=MISSING" in content or "IMP=MISSING" in content or "PLACE=MISSING" in content:
            signal_values_ok = False
            
        # Check if Tier A/B/C exists but VP is MISSING
        if ("Tier A" in content or "Tier B" in content or "Tier C" in content) and "VP=MISSING" in content:
            signal_values_ok = False
    
    if vp30_status == "PASS" and api_status == "PASS" and metadata_ok and signal_values_ok:
        manifest["overall_status"] = "READY_FOR_RACE_DAY"
        manifest["next_command"] = "ALL CLEAR — System Ready"
    elif not metadata_ok:
        manifest["overall_status"] = "BLOCKED_OPERATOR_METADATA"
        manifest["next_command"] = f"python scripts/audit_race_metadata_coverage.py --date {date_str}"
    elif not signal_values_ok:
        manifest["overall_status"] = "BLOCKED_OPERATOR_SIGNAL_VALUES"
        manifest["next_command"] = f"Check source verdict file for missing keys: data/velo_prime_verdicts_{date_under}.json"
    else:
        manifest["overall_status"] = "PARTIAL_READY"
        manifest["next_command"] = "Check failed operator cards."

    write_manifest(manifest, date_under)
    print_status(manifest)

def write_manifest(manifest, date_under):
    data_dir = Path.cwd() / "data"
    data_dir.mkdir(exist_ok=True)
    json_path = data_dir / f"velo_day_bootstrap_{date_under}.json"
    md_path = data_dir / f"velo_day_bootstrap_{date_under}.md"
    
    with open(json_path, "w") as f:
        json.dump(manifest, f, indent=2)
        
    with open(md_path, "w") as f:
        f.write(f"# VÉLØ Day Bootstrap Manifest — {manifest['date']}\n\n")
        f.write(f"**Status:** {manifest['overall_status']}\n")
        f.write(f"**Run at:** {manifest['run_at']}\n\n")
        
        f.write("## 1. Environment\n")
        f.write(f"- {manifest['environment']}\n\n")
        
        f.write("## 2. Racecards\n")
        f.write(f"- Found: {manifest['racecards']['found']}\n")
        f.write(f"- Source: {manifest['racecards']['source']}\n")
        f.write(f"- Races: {manifest['racecards']['races']}\n")
        f.write(f"- Runners: {manifest['racecards']['runners']}\n\n")
        
        f.write("## 3. Racing Post Files\n")
        f.write(f"- Status: {manifest['rp_files']['status']}\n")
        f.write(f"- PDFs count: {len(manifest['rp_files']['pdfs'])}\n\n")
        
        f.write("## 4. Merged Racecards\n")
        f.write(f"- Found: {manifest['merged_racecards']['found']}\n")
        if manifest['merged_racecards']['found']:
            cov = manifest['merged_racecards']['coverage']
            f.write(f"- Coverage: {cov}\n\n")
            
        f.write("## 5. Verdicts\n")
        f.write(f"- Found: {manifest['verdicts']['found']}\n")
        f.write(f"- Source: {manifest['verdicts']['source']}\n")
        f.write(f"- Count: {manifest['verdicts']['count']}\n\n")
        
        f.write("## 6-8. Operator Cards\n")
        f.write(f"- VP30: {manifest['operator_cards'].get('vp30', 'NOT_RUN')}\n")
        f.write(f"- Racing API: {manifest['operator_cards'].get('racing_api_enrichment', 'NOT_RUN')}\n")
        f.write(f"- CASHRUN: {manifest['operator_cards'].get('cashrun', 'NOT_RUN')}\n\n")
        
        f.write("## 9. Missing Items\n")
        for m in manifest['missing_items']:
            f.write(f"- {m}\n")
        f.write("\n## 10. Next Command\n")
        f.write(f"`{manifest['next_command']}`\n")

def print_status(manifest):
    print("\n============================================================")
    print(f"VELO_DAY_STATUS — {manifest['date']}")
    print("============================================================")
    print(f"Environment:       {manifest['environment']}")
    print(f"Racecards:         {'FOUND' if manifest['racecards']['found'] else 'MISSING'} ({manifest['racecards']['races']} races, {manifest['racecards']['runners']} runners)")
    print(f"RP Files:          {manifest['rp_files']['status']}")
    print(f"Merged Racecards:  {'FOUND' if manifest['merged_racecards']['found'] else 'MISSING'}")
    print(f"Verdicts:          {'FOUND' if manifest['verdicts']['found'] else 'MISSING'} ({manifest['verdicts']['count']} verdicts)")
    print(f"VP30 Card:         {manifest['operator_cards'].get('vp30', 'NOT_RUN')}")
    print(f"Racing API Card:   {manifest['operator_cards'].get('racing_api_enrichment', 'NOT_RUN')}")
    print(f"CASHRUN:           {manifest['operator_cards'].get('cashrun', 'NOT_RUN')}")
    print("\nMissing Items:")
    for m in manifest['missing_items']:
        print(f" - {m}")
        
    print("\n------------------------------------------------------------")
    print(f"OVERALL STATUS: {manifest['overall_status']}")
    print(f"NEXT COMMAND:   {manifest['next_command']}")
    print("============================================================\n")
    print("Note: If RP/CASHRUN fields are missing for a runner, it is often due to")
    print("debutantes (2yo starting their career) rather than a file error.")

if __name__ == "__main__":
    main()
