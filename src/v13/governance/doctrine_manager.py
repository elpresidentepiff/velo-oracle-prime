"""
Doctrine Version Management

Handles semantic versioning of doctrine rules with version bumps and rollbacks.
"""

from datetime import datetime, UTC
from typing import Dict, Any, Optional
import sqlite3
import json


class DoctrineManager:
    """
    Manages doctrine version lifecycle.
    
    Semantic versioning:
    - MAJOR (X.0.0): Breaking change (e.g., critic authority model changed)
    - MINOR (X.Y.0): New rule added (e.g., temporal validation)
    - PATCH (X.Y.Z): Bug fix, no behavior change
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
    
    def get_active_version(self) -> str:
        """Get currently active doctrine version."""
        cursor = self.db.execute(
            "SELECT version FROM doctrine_versions WHERE active = TRUE"
        )
        row = cursor.fetchone()
        
        if not row:
            # Initialize with V13 baseline
            self.initialize_version(
                "13.0.0",
                "V13 Constitutional Baseline - Episodic memory + read-only critics + doctrine guards"
            )
            return "13.0.0"
        
        return row[0]
    
    def bump_version(
        self,
        change_type: str,  # MAJOR, MINOR, PATCH
        description: str,
        created_by: str,
        rules_snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Bump doctrine version and create new version record.
        
        Does NOT apply actual rule changes (deferred to Phase 3C).
        
        Args:
            change_type: MAJOR, MINOR, or PATCH
            description: Human-readable description of change
            created_by: Reviewer username/ID
            rules_snapshot: Optional snapshot of rules (empty dict if not provided)
        
        Returns:
            New version string
        """
        current_version = self.get_active_version()
        
        # Parse semantic version
        major, minor, patch = map(int, current_version.split("."))
        
        if change_type == "MAJOR":
            new_version = f"{major + 1}.0.0"
        elif change_type == "MINOR":
            new_version = f"{major}.{minor + 1}.0"
        elif change_type == "PATCH":
            new_version = f"{major}.{minor}.{patch + 1}"
        else:
            raise ValueError(f"Invalid change_type: {change_type}")
        
        # Deactivate current version
        self.db.execute(
            "UPDATE doctrine_versions SET active = FALSE WHERE version = ?",
            (current_version,)
        )
        
        # Create new version
        self.db.execute(
            """
            INSERT INTO doctrine_versions (
                version, created_at, created_by, description,
                rules_snapshot, parent_version, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_version,
                datetime.now(UTC).isoformat(),
                created_by,
                description,
                json.dumps(rules_snapshot or {}),
                current_version,
                True,
            )
        )
        
        self.db.commit()
        return new_version
    
    def initialize_version(self, version: str, description: str):
        """Initialize doctrine version (first-time setup)."""
        self.db.execute(
            """
            INSERT OR IGNORE INTO doctrine_versions (
                version, created_at, created_by, description,
                rules_snapshot, parent_version, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                datetime.now(UTC).isoformat(),
                "system",
                description,
                json.dumps({}),
                None,
                True,
            )
        )
        self.db.commit()
    
    def get_version_history(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Get doctrine version history."""
        cursor = self.db.execute(
            """
            SELECT version, created_at, created_by, description,
                   rules_snapshot, parent_version, active
            FROM doctrine_versions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        
        versions = []
        for row in cursor.fetchall():
            versions.append({
                "version": row[0],
                "created_at": row[1],
                "created_by": row[2],
                "description": row[3],
                "rules_snapshot": json.loads(row[4]),
                "parent_version": row[5],
                "active": bool(row[6]),
            })
        
        return versions
    
    def get_version_details(self, version: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific version."""
        cursor = self.db.execute(
            """
            SELECT version, created_at, created_by, description,
                   rules_snapshot, parent_version, active
            FROM doctrine_versions
            WHERE version = ?
            """,
            (version,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "version": row[0],
            "created_at": row[1],
            "created_by": row[2],
            "description": row[3],
            "rules_snapshot": json.loads(row[4]),
            "parent_version": row[5],
            "active": bool(row[6]),
        }
    
    def rollback_to_version(self, target_version: str):
        """
        Rollback to a previous doctrine version.
        
        Args:
            target_version: Version to rollback to
        """
        # Verify target version exists
        if not self.get_version_details(target_version):
            raise ValueError(f"Version {target_version} not found")
        
        # Deactivate current version
        self.db.execute(
            "UPDATE doctrine_versions SET active = FALSE WHERE active = TRUE"
        )
        
        # Activate target version
        self.db.execute(
            "UPDATE doctrine_versions SET active = TRUE WHERE version = ?",
            (target_version,)
        )
        
        self.db.commit()
    
    def count_versions(self) -> int:
        """Count total doctrine versions."""
        cursor = self.db.execute("SELECT COUNT(*) FROM doctrine_versions")
        return cursor.fetchone()[0]
