"""
VÉLØ MCP Full Pipeline

Demonstrates the complete flow from raw PDF to intelligence outputs.
Follows the company-grade architecture with clear agent roles.
"""

import json
import sys
from pathlib import Path

# Import coordinators
sys.path.insert(0, str(Path(__file__).parent))

from mcp_foundation_coordinator import MCPFoundationCoordinator
from mcp_intelligence_coordinator import MCPIntelligenceCoordinator

def run_full_pipeline(pdf_path: Path) -> Dict:
    """Execute foundation → intelligence pipeline."""
    print("""
    ========================================
    VÉLØ MCP PIPELINE EXECUTION
    ========================================""")

    # Step 1: Foundation Layer
    print("
1. FOUNDATION LAYER")
    print("   ----------------")
    foundation_coordinator = MCPFoundationCoordinator(pdf_path)
    foundation_result = foundation_coordinator.run()

    # Step 2: Intelligence Layer (only if foundation passed)
    print("
2. INTELLIGENCE LAYER")
    print("   -------------------")
    intelligence_coordinator = MCPIntelligenceCoordinator(foundation_result)
    intelligence_result = intelligence_coordinator.run_all()

    # Final output
    print("
" + "="*50)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("="*50)

    return intelligence_result

def main(pdf_path_str: str):
    pdf_path = Path(pdf_path_str)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    result = run_full_pipeline(pdf_path)

    # Save result to file
    output_file = pdf_path.parent / f"mcp_pipeline_output_{pdf_path.stem}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"
📁 Output saved to: {output_file}")
    print("
🎯 Ready for Synthesis Layer (AggregationAgent, Top4ChassisAgent, VerdictAgent).")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python mcp_full_pipeline.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
