#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from src.velo.race_metadata_resolver import RaceMetadataResolver

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    
    date_str = args.date
    date_token = date_str.replace("-", "_")
    root = Path.cwd()
    data_dir = root / "data"
    
    # 1. Load verdicts
    vd_path1 = data_dir / f"velo_prime_verdicts_{date_token}.json"
    vd_path2 = data_dir / f"velo_prime_verdicts_{date_str}.json"
    vd_path = vd_path1 if vd_path1.exists() else (vd_path2 if vd_path2.exists() else None)
    
    if not vd_path:
        print(f"FAIL: No verdicts found for {date_str}")
        return

    with open(vd_path) as f:
        data = json.load(f)
        verdicts = data.get("verdicts", data) if isinstance(data, dict) else data

    print(f"Verdicts scanned: {len(verdicts)}")
    
    # 2. Resolve metadata
    resolver = RaceMetadataResolver(date=date_str)
    
    coverage = {
        "total": len(verdicts),
        "complete": 0,
        "missing_course": 0,
        "missing_time": 0,
        "missing_horse": 0,
        "source_stats": {}
    }
    
    unresolved = []
    
    for v in verdicts:
        rid = v.get("race_id")
        fa = v.get("full_analysis")
        meta = resolver.resolve(rid, fa)
        
        # Check horse name using resolver
        top = v.get("top") or {}
        if not top and fa:
            if isinstance(fa, dict):
                top = (fa.get("predictions") or [{}])[0]
            elif isinstance(fa, list) and fa:
                top = fa[0]
            
        raw_horse = top.get("horse") or top.get("horse_name") or "?"
        horse = meta.get_horse_name(raw_name=raw_horse)
        
        is_complete = True
        if not meta.course or meta.course == "?":
            coverage["missing_course"] += 1
            is_complete = False
        if not meta.off_time or meta.off_time == "?":
            coverage["missing_time"] += 1
            is_complete = False
        if not horse or horse == "?":
            coverage["missing_horse"] += 1
            is_complete = False
            
        if is_complete:
            coverage["complete"] += 1
            src = meta.source_used or "unknown"
            coverage["source_stats"][src] = coverage["source_stats"].get(src, 0) + 1
        else:
            unresolved.append({
                "race_id": rid,
                "course": meta.course,
                "time": meta.off_time,
                "horse": horse,
                "missing": meta.missing_fields + (["horse"] if not horse else [])
            })

    print(f"\nMETADATA COVERAGE AUDIT — {date_str}")
    print(f"========================================")
    print(f"Total Verdicts:   {coverage['total']}")
    print(f"Complete:         {coverage['complete']} ({(coverage['complete']/coverage['total']*100):.1f}%)")
    print(f"Missing Course:   {coverage['missing_course']}")
    print(f"Missing Time:     {coverage['missing_time']}")
    print(f"Missing Horse:    {coverage['missing_horse']}")
    
    print(f"\nSource Breakdown:")
    for src, count in coverage["source_stats"].items():
        print(f" - {src}: {count}")
        
    if unresolved:
        print(f"\nUnresolved Samples (top 5):")
        for u in unresolved[:5]:
            print(f" - {u['race_id']}: missing {u['missing']}")

if __name__ == "__main__":
    main()
