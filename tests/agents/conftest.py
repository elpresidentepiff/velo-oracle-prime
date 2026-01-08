"""
Pytest configuration for agent tests
"""
import sys
from pathlib import Path

# Add repository root to Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))
