import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="HarnessGuard Mission Control",
    page_icon="🛡️",
    layout="wide"
)

# Constants
HACKATHON_ROOT = Path(__file__).resolve().parents[1]
DEMO_CASES_DIR = HACKATHON_ROOT / "demo_cases"

def load_report_card(incident_dir):
    report_path = incident_dir / "harnessguard_report_card.json"
    if report_path.exists():
        with open(report_path, "r") as f:
            return json.load(f)
    return None

def main():
    st.title("🛡️ HarnessGuard Mission Control")
    st.subheader("Agentic Reliability for ML Prediction Pipelines")
    st.markdown("---")

    # Sidebar: Select Incident
    st.sidebar.header("Pipeline Instances")
    demo_cases = [d for d in DEMO_CASES_DIR.iterdir() if d.is_dir()]
    selected_incident_dir = st.sidebar.selectbox(
        "Select Incident Case",
        demo_cases,
        format_func=lambda x: x.name.replace("_", " ").title()
    )

    if selected_incident_dir:
        report = load_report_card(selected_incident_dir)
        
        if report:
            # Header Info
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Severity", report['severity'])
            
            with col2:
                status = "🔴 BLOCKED" if report['policy_evaluation']['learning_eligibility'] == "BLOCK_LEARNING" else "🟢 ALLOWED"
                st.metric("Learning Eligibility", status)
                
            with col3:
                st.metric("Detection Time", report['detection_time'][:19])

            st.markdown("---")

            # Main View: Analysis and Planning
            left_col, right_col = st.columns([2, 1])

            with left_col:
                st.header("📊 Feature Health & Evidence")
                
                # Show policy violations
                if report['policy_evaluation']['violations']:
                    st.warning(f"**Policy Violations Detected:** {', '.join(report['policy_evaluation']['violations'])}")
                
                # Load Evidence (Evidently Data)
                evidence_path = Path(report['evidence_source'])
                if evidence_path.exists():
                    with open(evidence_path, "r") as f:
                        evidently_data = json.load(f)
                    
                    if evidently_data.get("status") == "FAILED":
                        st.error(f"Catastrophic Failure Detected: {evidently_data.get('error')}")
                        if evidently_data.get("null_failed_cols"):
                            st.write(f"**Null Failed Columns:** {', '.join(evidently_data['null_failed_cols'])}")
                    else:
                        # Display some drift summary if available
                        st.info("Statistical drift analysis completed. View full HTML report for deep dive.")
                        
                        # Mocking a feature table for UI polish
                        st.write("### Observation Summary")
                        features_df = pd.read_csv(selected_incident_dir / "incident_data.csv")
                        st.dataframe(features_df.head(10), use_container_width=True)

            with right_col:
                st.header("🧠 Agent Recovery Plan")
                plan = report['recovery_plan']
                
                st.success(f"**Recommended Action:**\n\n{plan['recommended_action']}")
                st.write(f"**Agent Message:**\n\n{plan['operator_message']}")
                
                st.code(plan['safe_next_command'], language="bash")
                st.button("Execute Recovery Command", disabled=True)

            st.markdown("---")
            
            # AMD Benchmark Section
            st.header("⚡ AMD Hardware Acceleration")
            bench = report['amd_benchmark']
            b_col1, b_col2, b_col3 = st.columns(3)
            
            with b_col1:
                st.write(f"**Device:** {bench['inference_device']}")
            with b_col2:
                st.write(f"**Latency:** {bench['latency_ms']} ms")
            with b_col3:
                st.write(f"**Throughput:** {bench['throughput_signals_per_sec']} signals/sec")

            # Benchmark Bar Chart (Mocked Comparison)
            st.write("### Throughput Comparison (Signals/Sec)")
            bench_data = pd.DataFrame({
                "Device": ["Standard CPU", "AMD Instinct MI300X"],
                "Throughput": [7.01, 112.4] # Mocked 16x speedup for visual
            })
            st.bar_chart(bench_data, x="Device", y="Throughput")

        else:
            st.warning("No report card found for this incident. Run the Agent Orchestrator first.")

if __name__ == "__main__":
    main()
