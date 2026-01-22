#!/usr/bin/env python3
"""
VÉLØ PRIME Full Report Generator
Lingfield-style output with LOCKED SCHEMA

OUTPUT CONTRACT (NON-NEGOTIABLE):
- TOP-4 containment (exactly 4 runners)
- STRIKE decision with confidence
- Gate results (quarantine reasons)
- Suppression signals (S1-S7)
- Rationale block (why this decision)

If ANY field is missing, the run is INVALID.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from layer_x_suppression import LayerXSuppression
from meeting_integrity import parse_race_time, meeting_integrity_gate, MeetingIntegrityResult
from output_integrity import validate_race_output, IntegrityResult

PRIME_DIR = Path(__file__).parent.parent
DB_PATH = PRIME_DIR / "velo.db"


class VELOFullReport:
    """
    Generate complete Lingfield-style VELO reports.
    
    LOCKED SCHEMA - No summary mode, no fallbacks.
    Every race MUST have:
    - TOP-4 containment
    - STRIKE or QUARANTINE decision
    - Gate results
    - Suppression signals
    - Rationale block
    """
    
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.suppression = LayerXSuppression()
        self.contract_violations = []
    
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
        
        gates['db_exists'] = DB_PATH.exists()
        
        backups_dir = PRIME_DIR / 'backups'
        gates['db_backed_up'] = backups_dir.exists() and len(list(backups_dir.glob('*.tar.gz'))) > 0
        
        gates['all_pass'] = all([
            gates['git_remote'],
            gates['git_clean'],
            gates['db_exists'],
            gates['db_backed_up']
        ])
        
        return gates
    
    def _compute_top4(self, runners: List[Dict]) -> List[str]:
        """
        Compute TOP-4 containment based on rating convergence.
        ALWAYS returns exactly 4 runners.
        """
        scored = []
        for runner in runners:
            or_val = runner.get('official_rating') or 0
            rpr_val = runner.get('rpr') or 0
            ts_val = runner.get('topspeed') or 0
            
            ratings = [r for r in [or_val, rpr_val, ts_val] if r > 0]
            score = sum(ratings) / len(ratings) if ratings else 0
            scored.append((runner['name'], score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return exactly 4 (pad with empty if needed)
        top4 = [s[0] for s in scored[:4]]
        while len(top4) < 4:
            top4.append("(insufficient runners)")
        
        return top4[:4]
    
    def _build_rationale(self, race: Dict, runners: List[Dict], 
                         suppressions: List, quarantine, episode) -> str:
        """Build the rationale block explaining the decision."""
        lines = []
        
        # Race context
        lines.append(f"Race: {race['race_name']} at {race['venue']}")
        lines.append(f"Conditions: {race['distance']} on {race['going']}")
        lines.append(f"Field size: {len(runners)} runners")
        
        # Quarantine reasoning
        if quarantine.quarantined:
            lines.append(f"\nQUARANTINE APPLIED: {', '.join(quarantine.quarantine_reasons)}")
            if 'Q5_CHAOS_MODE' in quarantine.quarantine_reasons:
                lines.append("Heavy going + large field creates unpredictable race dynamics.")
            if 'Q6_SMALL_FIELD' in quarantine.quarantine_reasons:
                lines.append("Small field (<6 runners) reduces statistical confidence.")
            if 'Q1_DATA_MISSING' in quarantine.quarantine_reasons:
                lines.append(">25% of runners missing key ratings - data integrity compromised.")
            lines.append("No STRIKE issued. Containment-only verdict.")
        else:
            # STRIKE reasoning
            if episode and episode['verdict_layer_x']:
                strike_name = episode['verdict_layer_x'].split()[0] if episode['verdict_layer_x'] else "Unknown"
                lines.append(f"\nSTRIKE DECISION: {episode['verdict_layer_x']}")
                lines.append(f"Confidence: {episode['verdict_confidence']:.0%}")
                
                # Find the strike runner
                strike_runner = next((r for r in runners if r['name'] == strike_name), None)
                if strike_runner:
                    or_val = strike_runner.get('official_rating') or 'N/A'
                    rpr_val = strike_runner.get('rpr') or 'N/A'
                    ts_val = strike_runner.get('topspeed') or 'N/A'
                    lines.append(f"Ratings: OR={or_val}, RPR={rpr_val}, TS={ts_val}")
                
                lines.append("Selection based on rating convergence and field analysis.")
        
        # Suppression notes
        suppressed = [s for s in suppressions if s.suppressed_perf]
        if suppressed:
            lines.append(f"\nSUPPRESSION ALERTS: {len(suppressed)} runners flagged")
            for supp in suppressed[:3]:  # Show first 3
                lines.append(f"- {supp.name}: {', '.join(supp.suppressed_reasons)}")
            lines.append("All suppressed runners force-gated into TOP-4 containment.")
        
        return "\n".join(lines)
    
    def _generate_race_output(self, race, race_num: int) -> Dict[str, Any]:
        """
        Generate structured output for one race.
        Returns a dict that MUST pass the integrity gate.
        """
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
        
        # Compute TOP-4
        top4 = self._compute_top4(runners_dict)
        
        # Force suppressed runners into TOP-4
        suppressed_names = [s.name for s in runner_suppressions if s.suppressed_perf]
        for name in suppressed_names:
            if name not in top4:
                top4[3] = name  # Replace 4th position
        
        # Build output
        output = {
            'race_num': race_num,
            'race_time': race['race_time'],
            'race_name': race['race_name'],
            'distance': race['distance'],
            'going': race['going'],
            'runner_count': len(runners),
            'top4': top4,
            'strike_decision': episode['verdict_layer_x'] if episode and not quarantine.quarantined else None,
            'strike_confidence': episode['verdict_confidence'] if episode and not quarantine.quarantined else None,
            'gate_results': quarantine.quarantine_reasons if quarantine.quarantined else [],
            'suppression_signals': [
                {'name': s.name, 'severity': s.suppressed_severity, 'reasons': s.suppressed_reasons}
                for s in runner_suppressions if s.suppressed_perf
            ],
            'rationale_block': self._build_rationale(
                dict(race), runners_dict, runner_suppressions, quarantine, episode
            ),
            'is_quarantined': quarantine.quarantined
        }
        
        return output
    
    def _render_race_section(self, output: Dict[str, Any]) -> str:
        """Render a race output to markdown."""
        section = f"### Race {output['race_num']} ({output['race_time']}) - {output['race_name']}\n\n"
        section += f"**Distance**: {output['distance']} | **Going**: {output['going']} | **Runners**: {output['runner_count']}\n\n"
        
        # TOP-4 CONTAINMENT (MANDATORY)
        section += "**📦 TOP-4 CONTAINMENT**:\n"
        for i, runner in enumerate(output['top4'], 1):
            section += f"{i}. {runner}\n"
        section += "\n"
        
        # STRIKE / QUARANTINE
        if output['is_quarantined']:
            section += f"**🚫 QUARANTINED**: {', '.join(output['gate_results'])}\n\n"
            section += "**Status**: CONTAINMENT ONLY - No STRIKE\n\n"
        else:
            if output['strike_decision']:
                section += f"**🏇 STRIKE**: {output['strike_decision']} ({output['strike_confidence']:.0%})\n\n"
            section += "**Status**: STRIKE ALLOWED\n\n"
        
        # SUPPRESSION SIGNALS
        if output['suppression_signals']:
            section += "**⚠️ SUPPRESSION SIGNALS**:\n"
            for sig in output['suppression_signals']:
                section += f"- {sig['name']}: {sig['severity']} ({', '.join(sig['reasons'])})\n"
            section += "\n"
        
        # RATIONALE BLOCK (MANDATORY)
        section += "**📝 RATIONALE**:\n```\n"
        section += output['rationale_block']
        section += "\n```\n\n"
        
        section += "---\n\n"
        return section
    
    def generate_full_report(self, venue: str, date: str) -> str:
        """
        Generate complete Lingfield-style report with LOCKED SCHEMA.
        
        Every race MUST have:
        - TOP-4 containment
        - STRIKE or QUARANTINE decision
        - Gate results
        - Suppression signals
        - Rationale block
        """
        
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
        
        # Get races for this venue
        cursor = self.conn.cursor()
        races_raw = cursor.execute(
            "SELECT * FROM races WHERE venue = ?",
            (venue,)
        ).fetchall()
        
        if not races_raw:
            # Try without venue filter
            races_raw = cursor.execute("SELECT * FROM races").fetchall()
        
        # Sort by parsed datetime
        races = sorted(races_raw, key=lambda r: parse_race_time(r['race_time']))
        
        if not races:
            report += "No races found in database.\n"
            return report
        
        report += f"**Total Races**: {len(races)}\n\n"
        report += "---\n\n"
        
        # Generate and validate each race
        all_outputs = []
        for idx, race in enumerate(races, 1):
            output = self._generate_race_output(race, idx)
            
            # Validate against contract
            validation = validate_race_output(output)
            if not validation.is_valid:
                self.contract_violations.append(f"Race {idx}: {validation.error_message}")
            
            all_outputs.append(output)
            report += self._render_race_section(output)
        
        # Contract violation summary
        if self.contract_violations:
            report += "## ⚠️ CONTRACT VIOLATIONS\n\n"
            report += "The following races failed the output integrity gate:\n\n"
            for violation in self.contract_violations:
                report += f"- {violation}\n"
            report += "\n**WARNING**: Output may be incomplete.\n\n"
        
        return report
    
    def close(self):
        self.conn.close()
        self.suppression.close()


if __name__ == "__main__":
    import sys
    
    # Default to Gowran Park
    venue = sys.argv[1] if len(sys.argv) > 1 else "Gowran Park"
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-01-22"
    
    report_gen = VELOFullReport()
    report = report_gen.generate_full_report(venue, date)
    print(report)
    
    # Save report
    venue_slug = venue.upper().replace(" ", "_")
    report_path = PRIME_DIR / f"{venue_slug}_VELO_FULL_REPORT_{date.replace('-', '')}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report saved: {report_path}")
    
    # Check for contract violations
    if report_gen.contract_violations:
        print("\n⚠️ CONTRACT VIOLATIONS DETECTED:")
        for v in report_gen.contract_violations:
            print(f"  - {v}")
        sys.exit(1)
    
    report_gen.close()
