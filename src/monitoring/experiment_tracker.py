"""
VÉLØ Oracle - Lightweight Experiment Tracking System

A simplified alternative to MLflow for tracking experiments, metrics, and models.
Compatible with MLflow API for easy migration when available.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd
import pickle


class ExperimentTracker:
    """
    Lightweight experiment tracking system.
    
    Tracks:
    - Experiments and runs
    - Parameters (hyperparameters)
    - Metrics (ROI, accuracy, Sharpe ratio, etc.)
    - Artifacts (models, plots, reports)
    """
    
    def __init__(self, tracking_uri: str = "/home/ubuntu/velo-oracle/mlruns"):
        """
        Initialize experiment tracker.
        
        Args:
            tracking_uri: Directory to store experiment data
        """
        self.tracking_uri = Path(tracking_uri)
        self.tracking_uri.mkdir(parents=True, exist_ok=True)
        
        self.current_experiment = None
        self.current_run = None
        self.current_run_data = {}
    
    def set_experiment(self, experiment_name: str) -> str:
        """
        Set the active experiment.
        
        Args:
            experiment_name: Name of the experiment
            
        Returns:
            Experiment ID
        """
        experiment_dir = self.tracking_uri / experiment_name
        experiment_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_experiment = experiment_name
        
        # Create or load experiment metadata
        metadata_file = experiment_dir / "experiment.json"
        if not metadata_file.exists():
            metadata = {
                'experiment_name': experiment_name,
                'experiment_id': experiment_name,
                'created_at': datetime.now().isoformat(),
                'runs': []
            }
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        return experiment_name
    
    def start_run(self, run_name: Optional[str] = None) -> str:
        """
        Start a new run within the current experiment.
        
        Args:
            run_name: Optional name for the run
            
        Returns:
            Run ID
        """
        if not self.current_experiment:
            raise ValueError("No active experiment. Call set_experiment() first.")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{timestamp}"
        
        if run_name:
            run_id = f"{run_name}_{timestamp}"
        
        self.current_run = run_id
        self.current_run_data = {
            'run_id': run_id,
            'run_name': run_name or run_id,
            'experiment_name': self.current_experiment,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'status': 'RUNNING',
            'params': {},
            'metrics': {},
            'tags': {},
            'artifacts': []
        }
        
        # Create run directory
        run_dir = self._get_run_dir()
        run_dir.mkdir(parents=True, exist_ok=True)
        
        return run_id
    
    def log_param(self, key: str, value: Any):
        """
        Log a parameter for the current run.
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        if not self.current_run:
            raise ValueError("No active run. Call start_run() first.")
        
        self.current_run_data['params'][key] = value
    
    def log_params(self, params: Dict[str, Any]):
        """
        Log multiple parameters.
        
        Args:
            params: Dictionary of parameters
        """
        for key, value in params.items():
            self.log_param(key, value)
    
    def log_metric(self, key: str, value: float, step: Optional[int] = None):
        """
        Log a metric for the current run.
        
        Args:
            key: Metric name
            value: Metric value
            step: Optional step number (for time-series metrics)
        """
        if not self.current_run:
            raise ValueError("No active run. Call start_run() first.")
        
        if key not in self.current_run_data['metrics']:
            self.current_run_data['metrics'][key] = []
        
        metric_entry = {
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'step': step
        }
        
        self.current_run_data['metrics'][key].append(metric_entry)
    
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """
        Log multiple metrics.
        
        Args:
            metrics: Dictionary of metrics
            step: Optional step number
        """
        for key, value in metrics.items():
            self.log_metric(key, value, step)
    
    def set_tag(self, key: str, value: str):
        """
        Set a tag for the current run.
        
        Args:
            key: Tag name
            value: Tag value
        """
        if not self.current_run:
            raise ValueError("No active run. Call start_run() first.")
        
        self.current_run_data['tags'][key] = value
    
    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """
        Log an artifact (file) for the current run.
        
        Args:
            local_path: Path to the local file
            artifact_path: Optional subdirectory within artifacts
        """
        if not self.current_run:
            raise ValueError("No active run. Call start_run() first.")
        
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Artifact not found: {local_path}")
        
        # Create artifacts directory
        artifacts_dir = self._get_run_dir() / "artifacts"
        if artifact_path:
            artifacts_dir = artifacts_dir / artifact_path
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy artifact
        import shutil
        dest_path = artifacts_dir / local_path.name
        shutil.copy2(local_path, dest_path)
        
        # Record artifact
        self.current_run_data['artifacts'].append({
            'path': str(dest_path.relative_to(self._get_run_dir())),
            'size_bytes': local_path.stat().st_size,
            'logged_at': datetime.now().isoformat()
        })
    
    def log_model(self, model: Any, model_name: str):
        """
        Log a model (using pickle).
        
        Args:
            model: Model object to save
            model_name: Name for the model
        """
        if not self.current_run:
            raise ValueError("No active run. Call start_run() first.")
        
        # Create models directory
        models_dir = self._get_run_dir() / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = models_dir / f"{model_name}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # Record model
        self.current_run_data['artifacts'].append({
            'path': str(model_path.relative_to(self._get_run_dir())),
            'type': 'model',
            'model_name': model_name,
            'logged_at': datetime.now().isoformat()
        })
    
    def end_run(self, status: str = "FINISHED"):
        """
        End the current run.
        
        Args:
            status: Run status (FINISHED, FAILED, KILLED)
        """
        if not self.current_run:
            raise ValueError("No active run to end.")
        
        self.current_run_data['end_time'] = datetime.now().isoformat()
        self.current_run_data['status'] = status
        
        # Save run data
        run_file = self._get_run_dir() / "run.json"
        with open(run_file, 'w') as f:
            json.dump(self.current_run_data, f, indent=2)
        
        # Update experiment metadata
        self._update_experiment_metadata()
        
        self.current_run = None
        self.current_run_data = {}
    
    def _get_run_dir(self) -> Path:
        """Get the directory for the current run."""
        return self.tracking_uri / self.current_experiment / self.current_run
    
    def _update_experiment_metadata(self):
        """Update experiment metadata with run information."""
        experiment_dir = self.tracking_uri / self.current_experiment
        metadata_file = experiment_dir / "experiment.json"
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Add run to experiment
        run_summary = {
            'run_id': self.current_run_data['run_id'],
            'run_name': self.current_run_data['run_name'],
            'status': self.current_run_data['status'],
            'start_time': self.current_run_data['start_time'],
            'end_time': self.current_run_data['end_time']
        }
        
        metadata['runs'].append(run_summary)
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def search_runs(self, experiment_name: Optional[str] = None) -> pd.DataFrame:
        """
        Search for runs in an experiment.
        
        Args:
            experiment_name: Name of experiment (uses current if None)
            
        Returns:
            DataFrame with run information
        """
        if experiment_name is None:
            experiment_name = self.current_experiment
        
        if not experiment_name:
            raise ValueError("No experiment specified")
        
        experiment_dir = self.tracking_uri / experiment_name
        if not experiment_dir.exists():
            return pd.DataFrame()
        
        runs = []
        for run_dir in experiment_dir.iterdir():
            if run_dir.is_dir() and run_dir.name.startswith('run_'):
                run_file = run_dir / "run.json"
                if run_file.exists():
                    with open(run_file, 'r') as f:
                        run_data = json.load(f)
                    
                    # Flatten metrics (get latest value)
                    metrics_flat = {}
                    for metric_name, metric_values in run_data.get('metrics', {}).items():
                        if metric_values:
                            metrics_flat[f'metrics.{metric_name}'] = metric_values[-1]['value']
                    
                    # Flatten params
                    params_flat = {f'params.{k}': v for k, v in run_data.get('params', {}).items()}
                    
                    run_summary = {
                        'run_id': run_data['run_id'],
                        'run_name': run_data['run_name'],
                        'status': run_data['status'],
                        'start_time': run_data['start_time'],
                        'end_time': run_data['end_time'],
                        **params_flat,
                        **metrics_flat
                    }
                    
                    runs.append(run_summary)
        
        return pd.DataFrame(runs)


# Context manager for automatic run management
class run:
    """Context manager for MLflow-style run management."""
    
    def __init__(self, tracker: ExperimentTracker, run_name: Optional[str] = None):
        self.tracker = tracker
        self.run_name = run_name
    
    def __enter__(self):
        self.tracker.start_run(self.run_name)
        return self.tracker
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.tracker.end_run(status="FAILED")
        else:
            self.tracker.end_run(status="FINISHED")
        return False


# Global tracker instance (MLflow-style API)
_global_tracker = ExperimentTracker()


def set_experiment(experiment_name: str) -> str:
    """Set the active experiment (global API)."""
    return _global_tracker.set_experiment(experiment_name)


def start_run(run_name: Optional[str] = None) -> str:
    """Start a new run (global API)."""
    return _global_tracker.start_run(run_name)


def log_param(key: str, value: Any):
    """Log a parameter (global API)."""
    _global_tracker.log_param(key, value)


def log_params(params: Dict[str, Any]):
    """Log multiple parameters (global API)."""
    _global_tracker.log_params(params)


def log_metric(key: str, value: float, step: Optional[int] = None):
    """Log a metric (global API)."""
    _global_tracker.log_metric(key, value, step)


def log_metrics(metrics: Dict[str, float], step: Optional[int] = None):
    """Log multiple metrics (global API)."""
    _global_tracker.log_metrics(metrics, step)


def end_run(status: str = "FINISHED"):
    """End the current run (global API)."""
    _global_tracker.end_run(status)


def search_runs(experiment_name: Optional[str] = None) -> pd.DataFrame:
    """Search for runs (global API)."""
    return _global_tracker.search_runs(experiment_name)

