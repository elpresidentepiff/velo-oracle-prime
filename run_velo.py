#!/usr/bin/env python3
"""
VÉLØ PRIME - SINGLE ENTRYPOINT

THIS IS THE ONLY WAY TO GET OUTPUT.

Usage:
    python3 run_velo.py <venue> <date>

Example:
    python3 run_velo.py "Gowran Park" "2026-01-22"
    python3 run_velo.py "Southwell" "2026-01-22"

OUTPUT CONTRACT (NON-NEGOTIABLE):
- TOP-4 containment (exactly 4 runners)
- STRIKE decision with confidence
- Gate results (quarantine reasons)
- Suppression signals (S1-S7)
- Rationale block (why this decision)

If ANY field is missing, the run FAILS. No output. No exceptions.
"""

import sys
import os
from pathlib import Path

# Add src to path
PRIME_DIR = Path(__file__).parent
sys.path.insert(0, str(PRIME_DIR / "src"))

def main():
    # Parse arguments
    if len(sys.argv) < 3:
        print("Usage: python3 run_velo.py <venue> <date>")
        print("Example: python3 run_velo.py 'Gowran Park' '2026-01-22'")
        sys.exit(1)
    
    venue = sys.argv[1]
    date = sys.argv[2]
    
    # PRE-RENDER VALIDATION
    print("=" * 70)
    print("VÉLØ PRIME - OUTPUT CONTRACT ENFORCEMENT")
    print("=" * 70)
    print()
    print(f"Venue: {venue}")
    print(f"Date: {date}")
    print()
    
    # Check persistence gates BEFORE anything else
    import subprocess
    
    print("STEP 1: Persistence Gates")
    print("-" * 40)
    
    # Git remote
    result = subprocess.run(
        ['git', 'remote', '-v'],
        cwd=str(PRIME_DIR),
        capture_output=True,
        text=True
    )
    if 'origin' not in result.stdout:
        print("❌ FATAL: No git remote configured")
        print("   Run: git remote add origin <url> && git push")
        sys.exit(1)
    print("✅ Git remote configured")
    
    # Git clean
    result = subprocess.run(
        ['git', 'status', '--porcelain'],
        cwd=str(PRIME_DIR),
        capture_output=True,
        text=True
    )
    if result.stdout.strip():
        print("❌ FATAL: Uncommitted changes in git")
        print("   Run: git add . && git commit -m 'message' && git push")
        sys.exit(1)
    print("✅ Git working tree clean")
    
    # Database exists
    db_path = PRIME_DIR / "velo.db"
    if not db_path.exists():
        print("❌ FATAL: Database not found")
        print(f"   Expected: {db_path}")
        sys.exit(1)
    print("✅ Database exists")
    
    # Backups exist
    backups_dir = PRIME_DIR / "backups"
    if not backups_dir.exists() or len(list(backups_dir.glob('*.tar.gz'))) == 0:
        print("❌ FATAL: No backups found")
        print("   Run: ./backup.sh")
        sys.exit(1)
    print("✅ Backups exist")
    
    print()
    print("STEP 2: Generate Full Report")
    print("-" * 40)
    
    # Import and run the ONLY allowed renderer
    from velo_full_report import VELOFullReport
    
    report_gen = VELOFullReport()
    report = report_gen.generate_full_report(venue, date)
    
    # Check for contract violations
    if report_gen.contract_violations:
        print()
        print("❌ FATAL: OUTPUT CONTRACT BREACH")
        print("=" * 70)
        for v in report_gen.contract_violations:
            print(f"  - {v}")
        print()
        print("NO OUTPUT GENERATED. Fix the data and try again.")
        report_gen.close()
        sys.exit(1)
    
    # Output the report
    print(report)
    
    # Save report
    venue_slug = venue.upper().replace(" ", "_")
    report_path = PRIME_DIR / f"{venue_slug}_VELO_FULL_REPORT_{date.replace('-', '')}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print()
    print("=" * 70)
    print(f"✅ Report saved: {report_path}")
    print("=" * 70)
    
    report_gen.close()


if __name__ == "__main__":
    main()
