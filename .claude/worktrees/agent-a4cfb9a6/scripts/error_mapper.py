"""
VÉLØ Oracle - Error Mapping & Module Drift Analysis

Tracks false positives, false negatives, and module drift patterns.
Builds training data for NDS refinement and orchestrator calibration.

Key Features:
- Per-module error ledger (SQPE, TIE, NDS)
- Narrative trap tagging (hype favorites, false form)
- Module drift detection (optimism vs conservatism)
- Auto-generated training notes for NDS

Author: VÉLØ Oracle Team
Version: 1.0.0
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
from dataclasses import dataclass, asdict
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.log import get_logger
from core.settings import get_settings
from models.benter import BenterModel
from intelligence.sqpe import SQPE
from intelligence.tie import TIE
from intelligence.nds import NDS

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ErrorRecord:
    """Single error record"""
    race_id: str
    runner_id: str
    horse_name: str
    
    # Prediction
    module: str  # 'sqpe', 'tie', 'nds'
    predicted_win: bool
    actual_win: bool
    confidence: float
    
    # Context
    odds: float
    or_rating: float
    form: str
    trainer: str
    jockey: str
    
    # Error type
    error_type: str  # 'false_positive', 'false_negative', 'true_positive', 'true_negative'
    
    # Narrative tags (for NDS training)
    narrative_tags: List[str]
    
    timestamp: str


@dataclass
class ModuleDriftReport:
    """Module drift analysis"""
    module: str
    
    total_predictions: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    
    precision: float
    recall: float
    f1_score: float
    
    # Drift metrics
    optimism_bias: float  # Tendency to over-predict wins
    conservatism_bias: float  # Tendency to under-predict wins
    
    # Common error patterns
    common_fp_patterns: List[str]
    common_fn_patterns: List[str]


class ErrorMapper:
    """
    Tracks and analyzes prediction errors for intelligence modules
    """
    
    def __init__(self, output_dir: str = '/tmp/error_maps'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize modules
        self.sqpe = SQPE()
        self.tie = TIE()
        self.nds = NDS()
        self.benter = BenterModel(alpha=1.0, beta=1.0)
        
        # Error storage
        self.errors: List[ErrorRecord] = []
        
        logger.info(f"Initialized error mapper, output: {output_dir}")
    
    def analyze_race(self, race_data: Dict) -> List[ErrorRecord]:
        """
        Analyze a single race and record errors
        
        Args:
            race_data: Race data dict with runners
            
        Returns:
            List of ErrorRecords
        """
        race_errors = []
        
        for runner in race_data['runners']:
            # Get module predictions
            sqpe_result = self.sqpe.analyze(runner, race_data)
            tie_result = self.tie.analyze(runner, race_data)
            nds_result = self.nds.analyze(runner, race_data)
            
            actual_win = runner.get('won', False)
            
            # Analyze SQPE
            if sqpe_result['triggered']:
                error = self._create_error_record(
                    race_data, runner, 'sqpe',
                    predicted_win=True,
                    actual_win=actual_win,
                    confidence=sqpe_result['confidence']
                )
                race_errors.append(error)
            
            # Analyze TIE
            if tie_result['triggered']:
                error = self._create_error_record(
                    race_data, runner, 'tie',
                    predicted_win=True,
                    actual_win=actual_win,
                    confidence=tie_result['confidence']
                )
                race_errors.append(error)
            
            # Analyze NDS
            if nds_result['triggered']:
                error = self._create_error_record(
                    race_data, runner, 'nds',
                    predicted_win=True,
                    actual_win=actual_win,
                    confidence=nds_result['confidence']
                )
                race_errors.append(error)
        
        self.errors.extend(race_errors)
        return race_errors
    
    def _create_error_record(
        self,
        race_data: Dict,
        runner: Dict,
        module: str,
        predicted_win: bool,
        actual_win: bool,
        confidence: float
    ) -> ErrorRecord:
        """Create an error record"""
        
        # Determine error type
        if predicted_win and actual_win:
            error_type = 'true_positive'
        elif predicted_win and not actual_win:
            error_type = 'false_positive'
        elif not predicted_win and actual_win:
            error_type = 'false_negative'
        else:
            error_type = 'true_negative'
        
        # Tag narratives for false positives
        narrative_tags = []
        if error_type == 'false_positive':
            narrative_tags = self._tag_narrative(runner, race_data)
        
        return ErrorRecord(
            race_id=race_data.get('race_id', 'unknown'),
            runner_id=runner.get('runner_id', 'unknown'),
            horse_name=runner.get('horse_name', 'unknown'),
            module=module,
            predicted_win=predicted_win,
            actual_win=actual_win,
            confidence=confidence,
            odds=runner.get('win_odds', 999.0),
            or_rating=runner.get('or_rating', 0),
            form=runner.get('form', ''),
            trainer=runner.get('trainer', ''),
            jockey=runner.get('jockey', ''),
            error_type=error_type,
            narrative_tags=narrative_tags,
            timestamp=datetime.now().isoformat()
        )
    
    def _tag_narrative(self, runner: Dict, race_data: Dict) -> List[str]:
        """
        Tag narrative patterns for false positives
        
        Args:
            runner: Runner data
            race_data: Race data
            
        Returns:
            List of narrative tags
        """
        tags = []
        
        # Hype favorite (short odds, didn't win)
        if runner.get('win_odds', 999) < 3.0:
            tags.append('hype_favorite')
        
        # False form (good recent form, didn't win)
        form = runner.get('form', '')
        if form and len(form) >= 3:
            recent = form[:3]
            if recent.count('1') >= 2:
                tags.append('false_form')
        
        # Class drop (high rating, didn't win)
        if runner.get('or_rating', 0) > 100:
            tags.append('class_drop')
        
        # Trainer/jockey hype (star names, didn't win)
        trainer = runner.get('trainer', '').lower()
        jockey = runner.get('jockey', '').lower()
        
        # Common star trainers (simplified)
        star_trainers = ['gosden', 'appleby', 'haggas', 'varian', 'stoute']
        if any(name in trainer for name in star_trainers):
            tags.append('trainer_hype')
        
        # Common star jockeys (simplified)
        star_jockeys = ['dettori', 'buick', 'moore', 'doyle', 'oisin']
        if any(name in jockey for name in star_jockeys):
            tags.append('jockey_hype')
        
        # Long layoff (>60 days, didn't win)
        if runner.get('days_since_last', 0) > 60:
            tags.append('long_layoff')
        
        return tags
    
    def generate_drift_report(self, module: str) -> ModuleDriftReport:
        """
        Generate drift report for a module
        
        Args:
            module: Module name ('sqpe', 'tie', 'nds')
            
        Returns:
            ModuleDriftReport
        """
        module_errors = [e for e in self.errors if e.module == module]
        
        if not module_errors:
            return ModuleDriftReport(
                module=module,
                total_predictions=0,
                true_positives=0,
                false_positives=0,
                true_negatives=0,
                false_negatives=0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                optimism_bias=0.0,
                conservatism_bias=0.0,
                common_fp_patterns=[],
                common_fn_patterns=[]
            )
        
        # Count error types
        tp = sum(1 for e in module_errors if e.error_type == 'true_positive')
        fp = sum(1 for e in module_errors if e.error_type == 'false_positive')
        tn = sum(1 for e in module_errors if e.error_type == 'true_negative')
        fn = sum(1 for e in module_errors if e.error_type == 'false_negative')
        
        total = len(module_errors)
        
        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Drift metrics
        total_positive_predictions = tp + fp
        total_actual_positives = tp + fn
        
        optimism_bias = (total_positive_predictions - total_actual_positives) / total if total > 0 else 0.0
        conservatism_bias = -optimism_bias
        
        # Common patterns
        fp_errors = [e for e in module_errors if e.error_type == 'false_positive']
        fn_errors = [e for e in module_errors if e.error_type == 'false_negative']
        
        # Count narrative tags for FP
        fp_tag_counts = defaultdict(int)
        for e in fp_errors:
            for tag in e.narrative_tags:
                fp_tag_counts[tag] += 1
        
        common_fp = sorted(fp_tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        common_fp_patterns = [f"{tag} ({count})" for tag, count in common_fp]
        
        # FN patterns (simplified)
        common_fn_patterns = [
            f"High odds winners: {sum(1 for e in fn_errors if e.odds > 10)}",
            f"Low rating winners: {sum(1 for e in fn_errors if e.or_rating < 80)}"
        ]
        
        return ModuleDriftReport(
            module=module,
            total_predictions=total,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            optimism_bias=optimism_bias,
            conservatism_bias=conservatism_bias,
            common_fp_patterns=common_fp_patterns,
            common_fn_patterns=common_fn_patterns
        )
    
    def save_error_map(self, output_path: str):
        """
        Save error map to JSON
        
        Args:
            output_path: Path to save error map
        """
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_errors': len(self.errors),
            'errors': [asdict(e) for e in self.errors]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Error map saved to {output_path}")
    
    def generate_nds_training_notes(self, output_path: str):
        """
        Generate training notes for NDS refinement
        
        Args:
            output_path: Path to save training notes
        """
        # Get all false positives with narrative tags
        fp_errors = [e for e in self.errors if e.error_type == 'false_positive']
        
        # Count tags
        tag_counts = defaultdict(int)
        tag_examples = defaultdict(list)
        
        for e in fp_errors:
            for tag in e.narrative_tags:
                tag_counts[tag] += 1
                if len(tag_examples[tag]) < 5:  # Keep top 5 examples
                    tag_examples[tag].append({
                        'horse': e.horse_name,
                        'odds': e.odds,
                        'rating': e.or_rating,
                        'form': e.form,
                        'trainer': e.trainer,
                        'jockey': e.jockey
                    })
        
        lines = [
            "# NDS Training Notes - Narrative Trap Patterns",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total False Positives:** {len(fp_errors)}",
            "",
            "## Narrative Patterns Detected",
            ""
        ]
        
        for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"### {tag.replace('_', ' ').title()} ({count} occurrences)")
            lines.append("")
            lines.append("**Examples:**")
            lines.append("")
            
            for ex in tag_examples[tag]:
                lines.append(f"- **{ex['horse']}** @ {ex['odds']:.1f} (OR: {ex['or_rating']}, Form: {ex['form']})")
                lines.append(f"  - Trainer: {ex['trainer']}, Jockey: {ex['jockey']}")
            
            lines.append("")
            
            # Add refinement suggestions
            lines.append("**NDS Refinement Suggestions:**")
            lines.append("")
            
            if tag == 'hype_favorite':
                lines.append("- Increase overround penalty for short-priced favorites")
                lines.append("- Add market pressure detection (rapid shortening)")
            elif tag == 'false_form':
                lines.append("- Weight form quality over form recency")
                lines.append("- Check class of recent wins")
            elif tag == 'trainer_hype':
                lines.append("- Discount trainer reputation in certain conditions")
                lines.append("- Check trainer strike rate at specific courses")
            elif tag == 'jockey_hype':
                lines.append("- Discount jockey reputation for first-time partnerships")
                lines.append("- Check jockey course/distance record")
            elif tag == 'long_layoff':
                lines.append("- Increase penalty for layoffs >90 days")
                lines.append("- Check if prep race was run")
            
            lines.append("")
        
        lines.append("## Recommended NDS Threshold Adjustments")
        lines.append("")
        lines.append("Based on error patterns, consider:")
        lines.append("")
        
        # Calculate recommended adjustments
        hype_count = tag_counts.get('hype_favorite', 0) + tag_counts.get('trainer_hype', 0) + tag_counts.get('jockey_hype', 0)
        
        if hype_count > len(fp_errors) * 0.3:
            lines.append("- **Increase hype detection sensitivity** (current threshold may be too low)")
        
        if tag_counts.get('false_form', 0) > len(fp_errors) * 0.2:
            lines.append("- **Strengthen form quality checks** (recent form may be misleading)")
        
        if tag_counts.get('long_layoff', 0) > len(fp_errors) * 0.15:
            lines.append("- **Increase layoff penalty** (returning horses may need more prep)")
        
        lines.append("")
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"NDS training notes saved to {output_path}")
    
    def generate_comprehensive_report(self, output_path: str):
        """
        Generate comprehensive error analysis report
        
        Args:
            output_path: Path to save report
        """
        lines = [
            "# VÉLØ Oracle - Error Map & Module Drift Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Predictions Analyzed:** {len(self.errors)}",
            "",
            "## Module Performance Summary",
            ""
        ]
        
        # Generate drift reports for each module
        modules = ['sqpe', 'tie', 'nds']
        drift_reports = {m: self.generate_drift_report(m) for m in modules}
        
        lines.append("| Module | Predictions | Precision | Recall | F1 | Optimism Bias |")
        lines.append("|--------|-------------|-----------|--------|----|--------------:|")
        
        for module in modules:
            dr = drift_reports[module]
            lines.append(
                f"| {module.upper()} | {dr.total_predictions} | "
                f"{dr.precision:.1%} | {dr.recall:.1%} | "
                f"{dr.f1_score:.2f} | {dr.optimism_bias:+.1%} |"
            )
        
        lines.append("")
        
        # Detailed module analysis
        for module in modules:
            dr = drift_reports[module]
            
            lines.append(f"## {module.upper()} Detailed Analysis")
            lines.append("")
            lines.append(f"**Total Predictions:** {dr.total_predictions}")
            lines.append(f"**True Positives:** {dr.true_positives}")
            lines.append(f"**False Positives:** {dr.false_positives}")
            lines.append(f"**True Negatives:** {dr.true_negatives}")
            lines.append(f"**False Negatives:** {dr.false_negatives}")
            lines.append("")
            lines.append(f"**Precision:** {dr.precision:.1%}")
            lines.append(f"**Recall:** {dr.recall:.1%}")
            lines.append(f"**F1 Score:** {dr.f1_score:.2f}")
            lines.append("")
            lines.append(f"**Optimism Bias:** {dr.optimism_bias:+.1%}")
            lines.append(f"**Conservatism Bias:** {dr.conservatism_bias:+.1%}")
            lines.append("")
            
            if dr.common_fp_patterns:
                lines.append("### Common False Positive Patterns")
                lines.append("")
                for pattern in dr.common_fp_patterns:
                    lines.append(f"- {pattern}")
                lines.append("")
            
            if dr.common_fn_patterns:
                lines.append("### Common False Negative Patterns")
                lines.append("")
                for pattern in dr.common_fn_patterns:
                    lines.append(f"- {pattern}")
                lines.append("")
        
        lines.append("## Recommendations")
        lines.append("")
        lines.append("*[To be filled after analysis review]*")
        lines.append("")
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Comprehensive report saved to {output_path}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="VÉLØ Error Mapper")
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to raceform CSV with results'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='/tmp/error_maps',
        help='Output directory for error maps'
    )
    parser.add_argument(
        '--year',
        type=int,
        help='Filter by year (optional)'
    )
    
    args = parser.parse_args()
    
    # Create error mapper
    mapper = ErrorMapper(output_dir=args.output_dir)
    
    # Load data
    logger.info(f"Loading data from {args.data}")
    df = pd.read_csv(args.data)
    
    if args.year:
        df['race_date'] = pd.to_datetime(df['race_date'], errors='coerce')
        df = df[df['race_date'].dt.year == args.year]
    
    logger.info(f"Loaded {len(df)} rows")
    
    # Process races
    total_races = 0
    for race_id, race_df in df.groupby('race_id'):
        total_races += 1
        
        if total_races % 100 == 0:
            logger.info(f"Processed {total_races} races...")
        
        # Prepare race data
        runners = []
        for _, row in race_df.iterrows():
            runner = {
                'runner_id': str(row.get('runner_id', row.get('horse_name', 'unknown'))),
                'horse_name': str(row.get('horse_name', 'unknown')),
                'or_rating': float(row.get('OR', 0)),
                'rpr_rating': float(row.get('RPR', 0)),
                'ts_rating': float(row.get('TS', 0)),
                'win_odds': float(row.get('win_odds', 999.0)),
                'form': str(row.get('form', '')),
                'trainer': str(row.get('trainer', '')),
                'jockey': str(row.get('jockey', '')),
                'days_since_last': int(row.get('days_since_last', 999)),
                'course_win_pct': float(row.get('course_win_pct', 0.0)),
                'distance_win_pct': float(row.get('distance_win_pct', 0.0)),
                'won': bool(row.get('won', False))
            }
            runners.append(runner)
        
        race_data = {
            'race_id': str(race_id),
            'runners': runners
        }
        
        mapper.analyze_race(race_data)
    
    logger.info(f"Processed {total_races} races, {len(mapper.errors)} predictions")
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(args.output_dir)
    
    mapper.save_error_map(
        str(output_dir / f'ERROR_MAP_V1_{timestamp}.json')
    )
    
    mapper.generate_nds_training_notes(
        str(output_dir / f'NDS_TRAINING_NOTES_{timestamp}.md')
    )
    
    mapper.generate_comprehensive_report(
        str(output_dir / f'MODULE_DRIFT_REPORT_{timestamp}.md')
    )
    
    logger.info("Error mapping complete!")


if __name__ == '__main__':
    main()

