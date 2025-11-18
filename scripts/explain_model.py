import argparse
from pathlib import Path
import sys
import pandas as pd
import logging

# Ensure src is in path
sys.path.append(str(Path(__file__).parent.parent))
from src.analysis.explainer import VeloExplainer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Insight Engine - Model Explainer")
    parser.add_argument("--model-name", required=True, help="Name of the model to explain (e.g., 'sqpe').")
    parser.add_argument("--model-version", required=True, help="Version of the model to explain.")
    parser.add_argument("--data-file", required=True, type=Path, help="Path to a sample of data for background/instance explanation.")
    parser.add_argument("--output-dir", type=Path, default="out/explanations", help="Directory to save the explanation plots.")
    parser.add_argument("--n-samples", type=int, default=100, help="Number of samples for global background explanation.")
    args = parser.parse_args()

    print("--- Running VÉLØ Insight Engine ---")

    # Load data
    print(f"Loading data from {args.data_file}...")
    df = pd.read_csv(args.data_file)
    # Placeholder for your real feature building logic. For now, we assume data is ready.
    X = df.select_dtypes(include=['number']).head(args.n_samples) # Simple placeholder
    if X.empty:
        raise ValueError("No numeric features found in data file for explanation.")

    # Initialize explainer
    print(f"Initializing explainer for model '{args.model_name}' version '{args.model_version}'...")
    explainer = VeloExplainer(model_name=args.model_name, model_version=args.model_version)

    # Create output directory
    output_dir = args.output_dir / f"{args.model_name}_{args.model_version}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate and save global explanation
    global_plot_path = output_dir / "global_feature_importance.png"
    explainer.explain_global_importance(X, global_plot_path)

    # Generate and save local explanation for the first instance
    local_plot_path = output_dir / "local_prediction_explanation.png"
    instance_to_explain = X.iloc[0]
    explainer.explain_single_prediction(instance_to_explain, local_plot_path)

    print("\n--- Explanation Complete ---")
    print(f"Plots saved in: {output_dir}")

if __name__ == "__main__":
    main()

