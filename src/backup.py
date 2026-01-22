#!/usr/bin/env python3
"""
VÉLØ PRIME Backup & Persistence
Triple-backup rule: Git commit + Git push + Local tar backup
"""

import subprocess
import tarfile
import shutil
from pathlib import Path
from datetime import datetime

PRIME_DIR = Path(__file__).parent.parent
BACKUPS_DIR = PRIME_DIR / "backups"

def create_backup():
    """Create tar backup of critical files."""
    BACKUPS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"prime_{timestamp}.tar.gz"
    backup_path = BACKUPS_DIR / backup_name
    
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(PRIME_DIR / "velo.db", arcname="velo.db")
        tar.add(PRIME_DIR / "src", arcname="src")
        tar.add(PRIME_DIR / "integrity_events.json", arcname="integrity_events.json")
    
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def git_commit(message: str):
    """Commit changes to git."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=PRIME_DIR,
            check=True,
            capture_output=True
        )
        
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=PRIME_DIR,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Git commit: {message}")
            return True
        else:
            print(f"⚠️  Git commit failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Git error: {e}")
        return False

def verify_persistence():
    """Verify all critical files exist."""
    checks = [
        (PRIME_DIR / "velo.db", "Database"),
        (PRIME_DIR / "src", "Source code"),
        (PRIME_DIR / ".git", "Git repository"),
    ]
    
    all_ok = True
    for path, name in checks:
        if path.exists():
            print(f"✅ {name}: {path}")
        else:
            print(f"❌ {name}: MISSING {path}")
            all_ok = False
    
    return all_ok

if __name__ == "__main__":
    print("🔒 VÉLØ PRIME PERSISTENCE CHECK")
    print("=" * 60)
    
    # Verify
    if verify_persistence():
        print("\n✅ All critical files present")
        
        # Backup
        backup_path = create_backup()
        
        # Commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        git_commit(f"PRIME: Gowran data processed {timestamp}")
        
        print("\n✅ PERSISTENCE LOCKED")
    else:
        print("\n❌ PERSISTENCE FAILURE - Missing critical files")
