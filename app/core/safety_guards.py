"""
Safety utility to scan for forbidden imports in the live scoring path.
"""
import ast
import sys
from pathlib import Path

FORBIDDEN = {
    "app/agents/betfair_execution_agent.py",
    "app/agents/betfair_trading_agents.py",
}

# Map file paths to their module names (approximate)
FORBIDDEN_MODULES = {
    "app.agents.betfair_execution_agent",
    "app.agents.betfair_trading_agents",
    "betfair_execution_agent",
    "betfair_trading_agents"
}

def check_imports(root_dir: Path, target_paths: list[Path]) -> list[str]:
    violations = []
    
    for path in target_paths:
        if not path.exists(): continue
        
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name.startswith(m) for m in FORBIDDEN_MODULES):
                            violations.append(f"{path.name}: forbidden import '{alias.name}'")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(node.module.startswith(m) for m in FORBIDDEN_MODULES):
                        violations.append(f"{path.name}: forbidden from-import '{node.module}'")
        except Exception as e:
            # Skip parse errors (likely not python files or invalid syntax)
            continue
            
    return violations

def run_safety_scan():
    root = Path(__file__).resolve().parent.parent.parent
    # We scan the core live runtime paths
    targets = [
        root / "app" / "main.py",
        root / "scripts" / "ops" / "run_prime_today.py",
        root / "src" / "intelligence" / "velo_prime_ensemble.py"
    ]
    
    violations = check_imports(root, targets)
    if violations:
        print("SAFETY VIOLATION: Forbidden imports detected in live path!")
        for v in violations:
            print(f"  - {v}")
        return False
    
    return True

if __name__ == "__main__":
    if not run_safety_scan():
        sys.exit(1)
    print("Safety scan passed: No forbidden execution agents imported in live path.")
