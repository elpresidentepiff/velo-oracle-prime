"""
Doctrine Version Management — Supabase adaptation

Handles semantic versioning of doctrine rules with version bumps and rollbacks.
Reads/writes the doctrine_versions table.

Semantic versioning:
- MAJOR (X.0.0): Breaking change (e.g., critic authority model changed)
- MINOR (X.Y.0): New rule added (e.g., temporal validation)
- PATCH (X.Y.Z): Bug fix, no behaviour change
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DoctrineManager:
    """
    Manages doctrine version lifecycle against Supabase doctrine_versions table.

    Active version constraint: exactly one row has active=True at any time.
    bump_version() deactivates current, inserts new, commits atomically via
    two sequential Supabase calls (no transaction — Supabase REST doesn't
    expose multi-statement transactions; the window of inconsistency is
    milliseconds and acceptable here).
    """

    def __init__(self, db):
        self.db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_active_version(self) -> str:
        """Return the currently active doctrine version string."""
        result = (
            self.db.table("doctrine_versions")
            .select("version")
            .eq("active", True)
            .execute()
        )
        if result.data:
            return result.data[0]["version"]
        # First-time: seed baseline
        self.initialize_version(
            "13.0.0",
            "V13 Constitutional Baseline — episodic memory + read-only critics + doctrine guards",
        )
        return "13.0.0"

    def get_version_details(self, version: str) -> Optional[Dict[str, Any]]:
        """Get full row for a specific version, or None."""
        result = (
            self.db.table("doctrine_versions")
            .select("*")
            .eq("version", version)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_version_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return version history newest-first."""
        result = (
            self.db.table("doctrine_versions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def count_versions(self) -> int:
        """Count total doctrine version rows."""
        result = self.db.table("doctrine_versions").select("id").execute()
        return len(result.data) if result.data else 0

    # ── Mutations ─────────────────────────────────────────────────────────────

    def initialize_version(self, version: str, description: str) -> None:
        """Seed the baseline doctrine version (idempotent — skips if already exists)."""
        existing = self.get_version_details(version)
        if existing:
            return
        self.db.table("doctrine_versions").insert({
            "version":        version,
            "created_at":     datetime.now(timezone.utc).isoformat(),
            "created_by":     "system",
            "description":    description,
            "rules_snapshot": {},
            "parent_version": None,
            "active":         True,
        }).execute()

    def bump_version(
        self,
        change_type: str,
        description: str,
        created_by: str,
        rules_snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Bump the active doctrine version and return the new version string.

        Args:
            change_type:     MAJOR / MINOR / PATCH
            description:     Human-readable reason for bump
            created_by:      Reviewer ID
            rules_snapshot:  Optional dict snapshot of changed rules

        Returns:
            New version string e.g. "13.1.0"
        """
        current = self.get_active_version()
        major, minor, patch = map(int, current.split("."))

        if change_type == "MAJOR":
            new_version = f"{major + 1}.0.0"
        elif change_type == "MINOR":
            new_version = f"{major}.{minor + 1}.0"
        elif change_type == "PATCH":
            new_version = f"{major}.{minor}.{patch + 1}"
        else:
            raise ValueError(f"Invalid change_type: {change_type!r} — must be MAJOR/MINOR/PATCH")

        # Deactivate current
        self.db.table("doctrine_versions").update({"active": False}).eq("version", current).execute()

        # Insert new active version
        self.db.table("doctrine_versions").insert({
            "version":        new_version,
            "created_at":     datetime.now(timezone.utc).isoformat(),
            "created_by":     created_by,
            "description":    description,
            "rules_snapshot": rules_snapshot or {},
            "parent_version": current,
            "active":         True,
        }).execute()

        return new_version

    def rollback_to_version(self, target_version: str) -> None:
        """
        Rollback to a previous doctrine version.

        Deactivates all rows, re-activates the target version.
        Raises ValueError if target_version does not exist.
        """
        if not self.get_version_details(target_version):
            raise ValueError(f"Doctrine version {target_version!r} not found")

        # Deactivate all
        self.db.table("doctrine_versions").update({"active": False}).neq("version", "__none__").execute()

        # Activate target
        self.db.table("doctrine_versions").update({"active": True}).eq("version", target_version).execute()
