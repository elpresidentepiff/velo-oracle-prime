import logging
from pathlib import Path
import joblib
import pandas as pd

try:
    import shap
    import matplotlib.pyplot as plt
except ImportError:
    shap = None
    logging.warning("SHAP and Matplotlib not installed. Explainer will not be available. Install with: pip install shap matplotlib")

# VÉLØ Core Imports
from src.registry.model_registry import default_model_registry, ModelRecord
from src.intelligence.sqpe import SQPEEngine

logger = logging.getLogger(__name__)

class VeloExplainer:
    """
    The VÉLØ Insight Engine.
    Uses SHAP to explain predictions from models in the Model Registry.
    """
    def __init__(self, model_name: str, model_version: str):
        if shap is None:
            raise ImportError("SHAP is required for the VeloExplainer. Please run 'pip install shap matplotlib'.")
        
        self.model_name = model_name
        self.model_version = model_version
        logger.info(f"Initializing explainer for {model_name} v{model_version}...")
        self.model, self.model_record = self._load_model()
        self.explainer = self._create_explainer()

    def _load_model(self):
        records = default_model_registry._load_registry()
        record = next((r for r in records if r.name == self.model_name and r.version == self.model_version), None)
        if not record:
            raise ValueError(f"Model '{self.model_name}' v'{self.model_version}' not found in registry.")

        # Construct path to the model's directory
        model_dir = default_model_registry.models_base_dir / record.name / record.version
        if not model_dir.exists():
             raise FileNotFoundError(f"Model artifact directory not found at: {model_dir}")

        # Load SQPE model
        model_instance = SQPEEngine.load(model_dir)
        return model_instance, record

    def _create_explainer(self):
        logger.info("Creating SHAP TreeExplainer...")
        # TreeExplainer is highly optimized for tree-based models like Gradient Boosting.
        return shap.TreeExplainer(self.model.model)

    def explain_global_importance(self, X_background: pd.DataFrame, output_path: Path):
        logger.info(f"Calculating global SHAP values for {len(X_background)} samples...")
        shap_values = self.explainer.shap_values(X_background)

        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, X_background, show=False, plot_type="bar", max_display=20)
        plt.title(f"Global Feature Importance | {self.model_name} v{self.model_version}", fontsize=16)
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()
        logger.info(f"Global importance plot saved to {output_path}")

    def explain_single_prediction(self, x_instance: pd.Series, output_path: Path):
        logger.info("Calculating SHAP values for single instance...")
        # Ensure the instance is a DataFrame for the explainer
        shap_values = self.explainer.shap_values(x_instance.to_frame().T)[0]

        plt.figure()
        shap.force_plot(
            self.explainer.expected_value,
            shap_values,
            x_instance,
            matplotlib=True,
            show=False,
            text_rotation=15
        )
        plt.title(f"Local Force Plot | {self.model_name} v{self.model_version}", y=0.9)
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches='tight')
        plt.close()
        logger.info(f"Single prediction force plot saved to {output_path}")

