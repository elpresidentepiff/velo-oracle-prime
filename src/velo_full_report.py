#!/usr/bin/env python3
"""
VÉLØ PRIME Full Report Generator
Lingfield-style output with tactics blocks, suppression enforcement, quarantine gates
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict
from layer_x_suppression import LayerXSuppression
from meeting_integrity import parse_race_time, meeting_integrity_gate, MeetingIntegrityResult

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"

class VELOFullReport:
    """Generate complete Lingfield-style VELO reports."""
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.suppression = LayerXSuppression()
    
    def check_persistence_gates(self) -> Dict:
        """Verify all persistence gates before running."""
        gates = {
            'git_remote': False,
            'git_clean': False,
            'db_exists': False,
            'db_backed_up': False,
            'all_pass': False
        }
        
        import subprocess
        
        # Check git remote
        try:
            result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=str(PRIME_DIR),
                capture_output=True,
                text=True
            )
            gates['git_remote'] = 'origin' in result.stdout
        except:
            pass
        
        # Check git clean
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=str(PRIME_DIR),
                capture_output=True,
                text=True
            )
            gates['git_clean'] = len(result.stdout.strip()) == 0
        except:
            pass
        
        # Check DB exists
        gates['db_exists'] = DB_PATH.exists()
        
        # Check DB backed up
        backups_dir = PRIME_DIR / 'backups'
        gates['db_backed_up'] = backups_dir.exists() and len(list(backups_dir.glob('*.tar.gz'))) > 0
        
        gates['all_pass'] = all([
            gates['git_remote'],
            gates['git_clean'],
            gates['db_exists'],
            gates['db_backed_up']
        ])
        
        return gates
    
    def generate_full_report(self, venue: str, date: str) -> str:
        """Generate complete Lingfield-style report."""
        
        # Check persistence gates
        gates = self.check_persistence_gates()
        
        report = f"# VÉLØ {venue.upper()} RACE DAY REPORT - {date}\n\n"
        
        if not gates['all_pass']:
            report += "## ⚠️ PERSISTENCE GATES FAILED\n\n"
            report += "Cannot proceed without:\n"
            if not gates['git_remote']:
                report += "- ❌ Git remote not configured\n"
            if not gates['git_clean']:
                report += "- ❌ Uncommitted changes in git\n"
            if not gates['db_exists']:
                report += "- ❌ Database not found\n"
            if not gates['db_backed_up']:
                report += "- ❌ Database not backed up\n"
            report += "\n**Status**: QUARANTINED - Cannot issue verdicts\n"
            return report
        
        report += "**Status**: ✅ Persistence gates passed\n\n"
        
        # Get all races and sort by proper datetime
        cursor = self.conn.cursor()
        races_raw = cursor.execute("SELECT * FROM races").fetchall()
        
        # Sort by parsed datetime (handles 1.10 = 13:10 PM correctly)
        races = sorted(races_raw, key=lambda r: parse_race_time(r['race_time']))
        
        if not races:
            report += "No races found in database.\n"
            return report
        
        report += f"**Total Races**: {len(races)}\n\n"
        report += "---\n\n"
        
        # Per-race analysis
        for idx, race in enumerate(races, 1):
            report += self._generate_race_section(race, idx)
        
        return report
    
    def _generate_race_section(self, race, race_num: int) -> str:
        """Generate one race section with full tactics."""
        cursor = self.conn.cursor()
        
        # Get runners
        runners = cursor.execute(
            "SELECT * FROM runners WHERE race_id = ? ORDER BY CAST(number AS INTEGER)",
            (race['id'],)
        ).fetchall()
        
        runners_dict = [dict(r) for r in runners]
        
        # Get verdict
        episode = cursor.execute(
            "SELECT * FROM episodes WHERE race_id = ?",
            (race['id'],)
        ).fetchone()
        
        # Analyze suppression
        runner_suppressions = []
        for runner in runners_dict:
            supp = self.suppression.detect_runner_suppression(runner)
            runner_suppressions.append(supp)
        
        # Check quarantine
        quarantine = self.suppression.decide_race_quarantine(dict(race), runners_dict)
        
        section = f"### Race {race_num} ({race['race_time']}) - {race['race_name']}\n"
        section += f"**Distance**: {race['distance']} | **Going**: {race['going']} | **Runners**: {len(runners)}\n\n"
        
        # Verdict line
        if quarantine.quarantined:
            section += f"**🚫 QUARANTINED**: {', '.join(quarantine.quarantine_reasons)}\n\n"
            section += "**Status**: CONTAINMENT ONLY - No STRIKE\n\n"
        else:
            if episode and episode['verdict_layer_x']:
                section += f"**🏇 STRIKE**: {episode['verdict_layer_x']} ({episode['verdict_confidence']:.0%})\n\n"
            section += f"**Status**: STRIKE ALLOWED\n\n"
        
        # Suppression alerts
        if runner_suppressions:
            suppressed = [s for s in runner_suppressions if s.suppressed_perf]
            if suppressed:
                section += "**⚠️ SUPPRESSED_PERF**:\n"
                for supp in suppressed:
                    section += f"- {supp.name}: {supp.suppressed_severity} ({', '.join(supp.suppressed_reasons)})\n"
                section += "\n"
        
        # Tactics block
        section += self._generate_tactics_block(race, runners_dict, runner_suppressions, quarantine, episode)
        
        section += "\n---\n\n"
        return section
    
    def _generate_tactics_block(self, race, runners, suppressions, quarantine, episode) -> str:
        """Generate tactics narrative block."""
        block = "**Tactics Analysis**:\n\n"
        
        if quarantine.quarantined:
            block += f"**Quarantine**: {', '.join(quarantine.quarantine_reasons)}\n\n"
            block += "Containment-only verdict issued. No STRIKE allowed.\n\n"
            
            suppressed = [s for s in suppressions if s.suppressed_perf]
            if suppressed:
                block += "**Suppressed Runners**:\n"
                for supp in suppressed:
                    block += f"- {supp.name}: {supp.suppressed_severity} ({', '.join(supp.suppressed_reasons)})\n"
                block += "\n"
            return block
        
        # Intent analysis
        intent_notes = []
        
        # Check for reactivation riders
        reactivation = [s for s in suppressions if 'S1_REACTIVATION_RIDER' in s.suppressed_reasons]
        if reactivation:
            intent_notes.append(f"Reactivation riders detected: {', '.join([s.name for s in reactivation])}")
        
        # Check for mark compression
        compression = [s for s in suppressions if 'S2_MARK_COMPRESSION' in s.suppressed_reasons]
        if compression:
            intent_notes.append(f"Mark compression (protected marks): {', '.join([s.name for s in compression])}")
        
        # Check for setup returns
        setup = [s for s in suppressions if 'S3_SETUP_RETURN' in s.suppressed_reasons]
        if setup:
            intent_notes.append(f"Setup returns (best trip/surface): {', '.join([s.name for s in setup])}")
        
        # Check for education runs
        education = [s for s in suppressions if 'S4_NOT_ASKED_PATTERN' in s.suppressed_reasons]
        if education:
            intent_notes.append(f"Education runs (not asked): {', '.join([s.name for s in education])}")
        
        # Check for trap-lead
        trap = [s for s in suppressions if 'S7_TRAP_LEAD_SIGNATURE' in s.suppressed_reasons]
        if trap:
            intent_notes.append(f"Trap-lead signatures (deliberate tactics): {', '.join([s.name for s in trap])}")
        
        if intent_notes:
            for note in intent_notes:
                block += f"- {note}\n"
        else:
            block += "- No major intent/suppression signals detected\n"
        
        # Force-gating check
        suppressed_in_top4 = [s for s in suppressions if s.suppressed_perf]
        if suppressed_in_top4:
            block += f"\n**Force-gating**: {len(suppressed_in_top4)} suppressed runners forced into containment chassis\n"
        
        # STRIKE decision
        if episode:
            block += f"\n**STRIKE Decision**: {episode['verdict_layer_x']} allowed (confidence: {episode['verdict_confidence']:.0%})\n"
        
        return block
    
    def close(self):
        self.conn.close()
        self.suppression.close()

if __name__ == "__main__":
    report_gen = VELOFullReport()
    report = report_gen.generate_full_report("GOWRAN PARK", "2026-01-22")
    print(report)
    
    # Save report
    report_path = PRIME_DIR / "GOWRAN_VELO_FULL_REPORT_20260122.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report saved: {report_path}")
    report_gen.close()
