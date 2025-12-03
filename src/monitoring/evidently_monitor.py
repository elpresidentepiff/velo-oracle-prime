"""
VÉLØ Oracle - Evidently AI Monitoring Integration
Model drift detection and data quality monitoring
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import json

from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import (
    DataDriftPreset,
    DataQualityPreset,
    TargetDriftPreset,
    RegressionPreset,
    ClassificationPreset
)
from evidently.test_suite import TestSuite
from evidently.tests import (
    TestNumberOfDriftedColumns,
    TestShareOfDriftedColumns,
    TestColumnDrift,
    TestNumberOfMissingValues,
    TestNumberOfColumnsWithMissingValues
)


class VeloModelMonitor:
    """
    Production model monitoring using Evidently AI.
    
    Monitors:
    - Data drift (feature distribution changes)
    - Target drift (label distribution changes)
    - Data quality (missing values, outliers)
    - Model performance (accuracy, precision, recall)
    """
    
    def __init__(self, reports_dir: Optional[str] = None):
        """
        Initialize model monitor.
        
        Args:
            reports_dir: Directory to save reports (default: reports/)
        """
        if reports_dir is None:
            reports_dir = Path(__file__).parent.parent.parent / "reports" / "evidently"
        
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Define column mapping for VÉLØ features
        self.column_mapping = ColumnMapping(
            target='win',  # Binary target: did horse win?
            prediction='predicted_win_prob',  # Model prediction
            numerical_features=[
                'trainer_sr_14d', 'trainer_sr_30d', 'trainer_sr_90d',
                'jockey_sr_14d', 'jockey_sr_30d', 'jockey_sr_90d',
                'tj_combo_uplift',
                'form_ewma', 'form_slope', 'form_var',
                'layoff_days', 'layoff_penalty',
                'course_going_iv', 'draw_iv',
                'odds'
            ],
            categorical_features=[
                'freshness_flag', 'class_drop', 'classdrop_flag',
                'bias_persist_flag'
            ]
        )
        
        print(f"✓ Evidently Model Monitor initialized")
        print(f"  Reports directory: {self.reports_dir}")
    
    def generate_data_drift_report(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        save_html: bool = True
    ) -> Dict:
        """
        Generate data drift report.
        
        Compares current data against reference (training) data.
        
        Args:
            reference_data: Reference dataset (e.g., training data)
            current_data: Current dataset (e.g., production data)
            save_html: Whether to save HTML report
        
        Returns:
            Drift metrics dictionary
        """
        print("Generating data drift report...")
        
        report = Report(metrics=[
            DataDriftPreset()
        ])
        
        report.run(
            reference_data=reference_data,
            current_data=current_data,
            column_mapping=self.column_mapping
        )
        
        if save_html:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = self.reports_dir / f"data_drift_{timestamp}.html"
            report.save_html(str(report_path))
            print(f"✓ Data drift report saved: {report_path}")
        
        # Extract metrics
        metrics = report.as_dict()
        
        return metrics
    
    def generate_data_quality_report(
        self,
        data: pd.DataFrame,
        save_html: bool = True
    ) -> Dict:
        """
        Generate data quality report.
        
        Checks for missing values, outliers, and data quality issues.
        
        Args:
            data: Dataset to analyze
            save_html: Whether to save HTML report
        
        Returns:
            Quality metrics dictionary
        """
        print("Generating data quality report...")
        
        report = Report(metrics=[
            DataQualityPreset()
        ])
        
        report.run(
            reference_data=None,
            current_data=data,
            column_mapping=self.column_mapping
        )
        
        if save_html:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = self.reports_dir / f"data_quality_{timestamp}.html"
            report.save_html(str(report_path))
            print(f"✓ Data quality report saved: {report_path}")
        
        metrics = report.as_dict()
        
        return metrics
    
    def generate_model_performance_report(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        save_html: bool = True
    ) -> Dict:
        """
        Generate model performance report.
        
        Compares model performance on reference vs current data.
        
        Args:
            reference_data: Reference dataset with predictions
            current_data: Current dataset with predictions
            save_html: Whether to save HTML report
        
        Returns:
            Performance metrics dictionary
        """
        print("Generating model performance report...")
        
        report = Report(metrics=[
            ClassificationPreset()
        ])
        
        report.run(
            reference_data=reference_data,
            current_data=current_data,
            column_mapping=self.column_mapping
        )
        
        if save_html:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = self.reports_dir / f"model_performance_{timestamp}.html"
            report.save_html(str(report_path))
            print(f"✓ Model performance report saved: {report_path}")
        
        metrics = report.as_dict()
        
        return metrics
    
    def run_drift_tests(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame
    ) -> Dict:
        """
        Run automated drift tests.
        
        Returns pass/fail results for drift detection.
        
        Args:
            reference_data: Reference dataset
            current_data: Current dataset
        
        Returns:
            Test results dictionary
        """
        print("Running drift tests...")
        
        test_suite = TestSuite(tests=[
            TestNumberOfDriftedColumns(),
            TestShareOfDriftedColumns(lt=0.3),  # Less than 30% drifted
            TestColumnDrift(column_name='odds'),
            TestColumnDrift(column_name='trainer_sr_14d'),
            TestColumnDrift(column_name='jockey_sr_14d'),
            TestNumberOfMissingValues(),
            TestNumberOfColumnsWithMissingValues()
        ])
        
        test_suite.run(
            reference_data=reference_data,
            current_data=current_data,
            column_mapping=self.column_mapping
        )
        
        # Save test results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_path = self.reports_dir / f"drift_tests_{timestamp}.html"
        test_suite.save_html(str(results_path))
        
        # Extract results
        results = test_suite.as_dict()
        
        # Check if tests passed
        all_passed = all(
            test['status'] == 'SUCCESS' 
            for test in results['tests']
        )
        
        print(f"✓ Drift tests complete: {'PASSED' if all_passed else 'FAILED'}")
        print(f"  Results saved: {results_path}")
        
        return {
            'all_passed': all_passed,
            'tests': results['tests'],
            'timestamp': timestamp
        }
    
    def check_for_drift(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        drift_threshold: float = 0.3
    ) -> Dict:
        """
        Quick drift check without generating full report.
        
        Args:
            reference_data: Reference dataset
            current_data: Current dataset
            drift_threshold: Threshold for drift detection (0-1)
        
        Returns:
            Drift status dictionary
        """
        report = Report(metrics=[DataDriftPreset()])
        report.run(
            reference_data=reference_data,
            current_data=current_data,
            column_mapping=self.column_mapping
        )
        
        metrics = report.as_dict()
        
        # Extract drift metrics
        drift_share = metrics['metrics'][0]['result']['drift_share']
        drifted_columns = metrics['metrics'][0]['result']['number_of_drifted_columns']
        total_columns = metrics['metrics'][0]['result']['number_of_columns']
        
        drift_detected = drift_share > drift_threshold
        
        return {
            'drift_detected': drift_detected,
            'drift_share': drift_share,
            'drifted_columns': drifted_columns,
            'total_columns': total_columns,
            'threshold': drift_threshold,
            'timestamp': datetime.now().isoformat()
        }
    
    def monitor_weekly(
        self,
        reference_data: pd.DataFrame,
        production_data: pd.DataFrame
    ) -> Dict:
        """
        Run weekly monitoring suite.
        
        Generates all reports and runs tests.
        
        Args:
            reference_data: Training/reference data
            production_data: Last week's production data
        
        Returns:
            Complete monitoring results
        """
        print("="*60)
        print("VÉLØ Oracle - Weekly Monitoring Report")
        print("="*60)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'reference_samples': len(reference_data),
            'production_samples': len(production_data)
        }
        
        # 1. Data drift
        drift_metrics = self.generate_data_drift_report(
            reference_data=reference_data,
            current_data=production_data
        )
        results['data_drift'] = drift_metrics
        
        # 2. Data quality
        quality_metrics = self.generate_data_quality_report(
            data=production_data
        )
        results['data_quality'] = quality_metrics
        
        # 3. Model performance (if predictions available)
        if 'predicted_win_prob' in production_data.columns:
            performance_metrics = self.generate_model_performance_report(
                reference_data=reference_data,
                current_data=production_data
            )
            results['model_performance'] = performance_metrics
        
        # 4. Drift tests
        test_results = self.run_drift_tests(
            reference_data=reference_data,
            current_data=production_data
        )
        results['drift_tests'] = test_results
        
        # Save summary
        summary_path = self.reports_dir / f"weekly_summary_{test_results['timestamp']}.json"
        with open(summary_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Weekly monitoring complete")
        print(f"  Summary saved: {summary_path}")
        
        return results
    
    def should_retrain(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame
    ) -> bool:
        """
        Determine if model should be retrained based on drift.
        
        Args:
            reference_data: Training data
            current_data: Recent production data
        
        Returns:
            True if retraining recommended
        """
        drift_status = self.check_for_drift(
            reference_data=reference_data,
            current_data=current_data,
            drift_threshold=0.3
        )
        
        if drift_status['drift_detected']:
            print(f"⚠ DRIFT DETECTED: {drift_status['drift_share']*100:.1f}% of features drifted")
            print(f"  Drifted columns: {drift_status['drifted_columns']}/{drift_status['total_columns']}")
            print(f"  Recommendation: RETRAIN MODEL")
            return True
        else:
            print(f"✓ No significant drift detected ({drift_status['drift_share']*100:.1f}%)")
            print(f"  Recommendation: Continue monitoring")
            return False


if __name__ == "__main__":
    # Test the monitor
    print("=== VÉLØ Oracle - Evidently Monitor Test ===\n")
    
    # Initialize monitor
    monitor = VeloModelMonitor()
    
    # Create sample data
    import numpy as np
    
    # Reference data (training)
    np.random.seed(42)
    reference_df = pd.DataFrame({
        'trainer_sr_14d': np.random.normal(0.25, 0.05, 1000),
        'jockey_sr_14d': np.random.normal(0.28, 0.05, 1000),
        'form_ewma': np.random.normal(0.6, 0.1, 1000),
        'odds': np.random.lognormal(2, 0.5, 1000),
        'win': np.random.binomial(1, 0.25, 1000)
    })
    
    # Current data (production) - with slight drift
    current_df = pd.DataFrame({
        'trainer_sr_14d': np.random.normal(0.27, 0.05, 500),  # Slight drift
        'jockey_sr_14d': np.random.normal(0.28, 0.05, 500),
        'form_ewma': np.random.normal(0.6, 0.1, 500),
        'odds': np.random.lognormal(2, 0.5, 500),
        'win': np.random.binomial(1, 0.25, 500)
    })
    
    # Check for drift
    print("\nChecking for drift...")
    should_retrain = monitor.should_retrain(
        reference_data=reference_df,
        current_data=current_df
    )
    
    # Generate reports
    print("\nGenerating reports...")
    monitor.generate_data_drift_report(reference_df, current_df)
    monitor.generate_data_quality_report(current_df)
    
    print("\n✓ Evidently Monitor operational!")
