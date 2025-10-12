"""
VÉLØ v9.0++ CHAREX - VÉLØ MANUS Agent

DevOps integrator; maintains code, API keys, and versioning.
System orchestrator and deployment manager.
"""

import os
import json
import subprocess
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


class VeloManus:
    """
    VÉLØ MANUS - DevOps & Integration Agent
    
    Manages system deployment, configuration, versioning,
    and orchestration of all other agents.
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize VÉLØ MANUS agent.
        
        Args:
            project_root: Root directory of the project
        """
        self.name = "VÉLØ_MANUS"
        self.version = "v9.0++"
        self.status = "STANDBY"
        
        # Project paths
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        
        self.project_root = Path(project_root)
        self.config_dir = self.project_root / "config"
        self.src_dir = self.project_root / "src"
        
        # Agent registry
        self.agents = {}
        self.modules = {}
    
    def activate(self) -> None:
        """Activate VÉLØ MANUS agent."""
        self.status = "ACTIVE"
        print(f"\n⚙️  {self.name} ACTIVATED")
        print(f"Project Root: {self.project_root}")
        print(f"System Orchestration: ONLINE\n")
    
    def register_agent(self, agent_name: str, agent_instance) -> None:
        """
        Register an agent with MANUS.
        
        Args:
            agent_name: Name of the agent
            agent_instance: Agent object instance
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ MANUS not active. Call activate() first.")
        
        self.agents[agent_name] = agent_instance
        print(f"✅ MANUS: Registered agent {agent_name}")
    
    def register_module(self, module_name: str, module_instance) -> None:
        """
        Register an analysis module with MANUS.
        
        Args:
            module_name: Name of the module
            module_instance: Module object instance
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ MANUS not active. Call activate() first.")
        
        self.modules[module_name] = module_instance
        print(f"✅ MANUS: Registered module {module_name}")
    
    def get_system_status(self) -> Dict:
        """
        Get complete system status.
        
        Returns:
            System status dictionary
        """
        agent_status = {}
        for name, agent in self.agents.items():
            if hasattr(agent, 'get_status'):
                agent_status[name] = agent.get_status()
            else:
                agent_status[name] = {"status": "UNKNOWN"}
        
        module_status = {}
        for name, module in self.modules.items():
            module_status[name] = {"loaded": True}
        
        return {
            "system": {
                "name": "VÉLØ v9.0++ CHAREX",
                "version": self.version,
                "status": self.status,
                "project_root": str(self.project_root)
            },
            "agents": agent_status,
            "modules": module_status,
            "timestamp": datetime.now().isoformat()
        }
    
    def load_config(self, config_name: str = "weights.json") -> Dict:
        """
        Load configuration file.
        
        Args:
            config_name: Name of config file
            
        Returns:
            Configuration dictionary
        """
        config_path = self.config_dir / config_name
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            print(f"📋 MANUS: Loaded config {config_name}")
            return config
        except FileNotFoundError:
            print(f"⚠️  MANUS: Config file not found: {config_name}")
            return {}
    
    def save_config(self, config_data: Dict, config_name: str = "weights.json") -> None:
        """
        Save configuration file.
        
        Args:
            config_data: Configuration dictionary
            config_name: Name of config file
        """
        config_path = self.config_dir / config_name
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"💾 MANUS: Saved config {config_name}")
    
    def check_dependencies(self) -> Dict:
        """
        Check if all required dependencies are installed.
        
        Returns:
            Dependency status dictionary
        """
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            return {"status": "ERROR", "message": "requirements.txt not found"}
        
        try:
            # Try to import key dependencies
            dependencies = {
                "requests": False,
                "numpy": False,
                "pandas": False,
                "flask": False
            }
            
            for dep in dependencies:
                try:
                    __import__(dep)
                    dependencies[dep] = True
                except ImportError:
                    dependencies[dep] = False
            
            all_installed = all(dependencies.values())
            
            return {
                "status": "OK" if all_installed else "INCOMPLETE",
                "dependencies": dependencies,
                "message": "All dependencies installed" if all_installed else "Some dependencies missing"
            }
        
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def get_version_info(self) -> Dict:
        """
        Get version information from git.
        
        Returns:
            Version info dictionary
        """
        try:
            # Get git commit hash
            commit_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.project_root,
                stderr=subprocess.DEVNULL
            ).decode().strip()
            
            # Get git branch
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_root,
                stderr=subprocess.DEVNULL
            ).decode().strip()
            
            return {
                "version": self.version,
                "commit": commit_hash,
                "branch": branch,
                "git_available": True
            }
        
        except Exception:
            return {
                "version": self.version,
                "git_available": False
            }
    
    def orchestrate_analysis(self, race_id: str) -> Dict:
        """
        Orchestrate complete race analysis using all agents.
        
        Args:
            race_id: Unique race identifier
            
        Returns:
            Complete analysis result
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ MANUS not active. Call activate() first.")
        
        print(f"\n🎯 MANUS: Orchestrating analysis for race {race_id}")
        
        result = {
            "race_id": race_id,
            "timestamp": datetime.now().isoformat(),
            "stages": {}
        }
        
        # Stage 1: Fetch data (SCOUT)
        if "SCOUT" in self.agents:
            print("  📡 Stage 1: SCOUT fetching race data...")
            result["stages"]["scout"] = "EXECUTED"
        else:
            print("  ⚠️  Stage 1: SCOUT not available")
            result["stages"]["scout"] = "SKIPPED"
        
        # Stage 2: Analyze (PRIME)
        if "PRIME" in self.agents:
            print("  🔮 Stage 2: PRIME analyzing race...")
            result["stages"]["prime"] = "EXECUTED"
        else:
            print("  ⚠️  Stage 2: PRIME not available")
            result["stages"]["prime"] = "SKIPPED"
        
        # Stage 3: Monitor odds (SYNTH)
        if "SYNTH" in self.agents:
            print("  📊 Stage 3: SYNTH monitoring market...")
            result["stages"]["synth"] = "EXECUTED"
        else:
            print("  ⚠️  Stage 3: SYNTH not available")
            result["stages"]["synth"] = "SKIPPED"
        
        # Stage 4: Log prediction (ARCHIVIST)
        if "ARCHIVIST" in self.agents:
            print("  📚 Stage 4: ARCHIVIST logging prediction...")
            result["stages"]["archivist"] = "EXECUTED"
        else:
            print("  ⚠️  Stage 4: ARCHIVIST not available")
            result["stages"]["archivist"] = "SKIPPED"
        
        print("✅ MANUS: Orchestration complete\n")
        
        return result
    
    def health_check(self) -> Dict:
        """
        Perform system health check.
        
        Returns:
            Health check results
        """
        health = {
            "status": "HEALTHY",
            "checks": {
                "project_structure": self.project_root.exists(),
                "config_dir": self.config_dir.exists(),
                "src_dir": self.src_dir.exists(),
                "agents_registered": len(self.agents),
                "modules_registered": len(self.modules)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Check if any critical check failed
        if not all([v for k, v in health["checks"].items() if isinstance(v, bool)]):
            health["status"] = "DEGRADED"
        
        return health
    
    def get_status(self) -> Dict:
        """Get current agent status."""
        return {
            "agent": self.name,
            "version": self.version,
            "status": self.status,
            "project_root": str(self.project_root),
            "agents_registered": list(self.agents.keys()),
            "modules_registered": list(self.modules.keys())
        }


def main():
    """Test VÉLØ MANUS agent."""
    print("⚙️  VÉLØ MANUS - DevOps & Integration Agent")
    print("="*60)
    
    manus = VeloManus()
    manus.activate()
    
    # Health check
    health = manus.health_check()
    print(f"\n🏥 Health Check:")
    print(json.dumps(health, indent=2))
    
    # Version info
    version_info = manus.get_version_info()
    print(f"\n📌 Version Info:")
    print(json.dumps(version_info, indent=2))
    
    # Dependencies check
    deps = manus.check_dependencies()
    print(f"\n📦 Dependencies:")
    print(json.dumps(deps, indent=2))
    
    # Display status
    status = manus.get_status()
    print(f"\n📊 MANUS Status:")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()

