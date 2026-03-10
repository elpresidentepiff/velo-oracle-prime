"""
VÉLØ PRIME — GitHub Sync Module
=================================
Automated git operations for persisting analyses, sigma debriefs,
and the memory database back to the repository.

Folder structure on repo:
  /analyses/{YYYY-MM-DD}/{course}_analysis.md
  /sigma/{YYYY-MM-DD}/{course}_sigma.md
  /data/velo_memory.db
  /reports/weekly/{YYYY-WXX}_report.md

Usage:
    from src.memory.github_sync import GitHubSync
    sync = GitHubSync(repo_root="/path/to/velo-oracle-prime")
    sync.auto_commit_analysis("2026-02-16", "Kempton", "path/to/analysis.md")
    sync.sync_all()
"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


class GitHubSync:
    """
    Handles all git operations for VÉLØ persistent storage.
    Commits analyses, sigma debriefs, database snapshots, and weekly reports.
    """

    def __init__(self, repo_root: Optional[str] = None):
        """
        Initialize the sync module.

        Args:
            repo_root: Path to the local git repository root.
                       Defaults to the project root (auto-detected).
        """
        if repo_root is None:
            # Try to find repo root from this file's location
            repo_root = str(Path(__file__).resolve().parent.parent.parent)
        self.repo_root = Path(repo_root)
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create the folder structure if it doesn't exist."""
        for d in ["analyses", "sigma", "data", "reports/weekly"]:
            (self.repo_root / d).mkdir(parents=True, exist_ok=True)

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repo root."""
        cmd = ["git", "-C", str(self.repo_root)] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=60,
        )

    def _sanitize_course(self, course: str) -> str:
        """Sanitize course name for use in file paths."""
        return course.strip().lower().replace(" ", "_").replace("'", "")

    # ─────────────────────────────────────────
    # AUTO-COMMIT METHODS
    # ─────────────────────────────────────────

    def auto_commit_analysis(
        self, date: str, course: str, analysis_file_path: str
    ) -> bool:
        """
        Copy analysis file to analyses/{date}/ and commit.

        Args:
            date: Date string (YYYY-MM-DD)
            course: Course name
            analysis_file_path: Path to the analysis markdown file

        Returns:
            True if committed successfully, False otherwise.
        """
        src = Path(analysis_file_path)
        if not src.exists():
            raise FileNotFoundError(f"Analysis file not found: {analysis_file_path}")

        dest_dir = self.repo_root / "analyses" / date
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{self._sanitize_course(course)}_analysis.md"

        shutil.copy2(str(src), str(dest))

        self._run_git("add", str(dest.relative_to(self.repo_root)))
        result = self._run_git(
            "commit", "-m",
            f"analysis: {course} {date}",
            check=False,
        )
        return result.returncode == 0

    def auto_commit_sigma(
        self, date: str, course: str, sigma_file_path: str
    ) -> bool:
        """
        Copy sigma debrief to sigma/{date}/ and commit.

        Args:
            date: Date string (YYYY-MM-DD)
            course: Course name
            sigma_file_path: Path to the sigma debrief markdown file

        Returns:
            True if committed successfully, False otherwise.
        """
        src = Path(sigma_file_path)
        if not src.exists():
            raise FileNotFoundError(f"Sigma file not found: {sigma_file_path}")

        dest_dir = self.repo_root / "sigma" / date
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{self._sanitize_course(course)}_sigma.md"

        shutil.copy2(str(src), str(dest))

        self._run_git("add", str(dest.relative_to(self.repo_root)))
        result = self._run_git(
            "commit", "-m",
            f"sigma: {course} {date}",
            check=False,
        )
        return result.returncode == 0

    def auto_commit_database(self, db_path: Optional[str] = None) -> bool:
        """
        Copy the current velo_memory.db to data/ and commit.

        Args:
            db_path: Path to the database file.
                     Defaults to data/velo_memory.db in repo root.

        Returns:
            True if committed successfully, False otherwise.
        """
        if db_path is None:
            db_path = str(self.repo_root / "data" / "velo_memory.db")

        src = Path(db_path)
        dest = self.repo_root / "data" / "velo_memory.db"

        if src.resolve() != dest.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))

        self._run_git("add", "data/velo_memory.db")
        result = self._run_git(
            "commit", "-m",
            f"data: update velo_memory.db — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            check=False,
        )
        return result.returncode == 0

    def auto_commit_report(self, report_path: str) -> bool:
        """
        Copy a weekly report to reports/weekly/ and commit.

        Args:
            report_path: Path to the report markdown file.

        Returns:
            True if committed successfully, False otherwise.
        """
        src = Path(report_path)
        if not src.exists():
            raise FileNotFoundError(f"Report file not found: {report_path}")

        dest = self.repo_root / "reports" / "weekly" / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))

        self._run_git("add", str(dest.relative_to(self.repo_root)))
        result = self._run_git(
            "commit", "-m",
            f"report: {src.stem}",
            check=False,
        )
        return result.returncode == 0

    # ─────────────────────────────────────────
    # SYNC
    # ─────────────────────────────────────────

    def sync_all(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """
        Push all committed changes to remote.

        Args:
            remote: Git remote name (default: origin)
            branch: Branch name. If None, pushes current branch.

        Returns:
            True if push succeeded, False otherwise.
        """
        if branch is None:
            # Get current branch name
            result = self._run_git("rev-parse", "--abbrev-ref", "HEAD", check=False)
            branch = result.stdout.strip() or "main"

        result = self._run_git("push", remote, branch, check=False)
        return result.returncode == 0

    def commit_and_push_all(
        self, message: Optional[str] = None, remote: str = "origin"
    ) -> bool:
        """
        Stage all changes, commit, and push. Convenience method.

        Args:
            message: Commit message. Auto-generated if None.
            remote: Git remote name.

        Returns:
            True if successful, False otherwise.
        """
        if message is None:
            message = f"auto: VÉLØ sync — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

        self._run_git("add", "-A", check=False)
        commit_result = self._run_git("commit", "-m", message, check=False)
        if commit_result.returncode != 0:
            # Nothing to commit is fine
            if "nothing to commit" in commit_result.stdout:
                return True
            return False

        return self.sync_all(remote=remote)

    # ─────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────

    def get_status(self) -> dict:
        """Return current git status information."""
        branch_result = self._run_git("rev-parse", "--abbrev-ref", "HEAD", check=False)
        status_result = self._run_git("status", "--porcelain", check=False)
        log_result = self._run_git("log", "--oneline", "-5", check=False)

        return {
            "branch": branch_result.stdout.strip(),
            "dirty_files": [
                line.strip() for line in status_result.stdout.strip().split("\n") if line.strip()
            ],
            "recent_commits": [
                line.strip() for line in log_result.stdout.strip().split("\n") if line.strip()
            ],
        }
