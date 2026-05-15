from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from app.services.ops_service import OpsService

ROOT = Path(__file__).resolve().parents[2]

if load_dotenv is not None:
    load_dotenv(ROOT / ".env", override=False)

APPROVED_SHADOW_TARGET = "shadow_full_train_v2"
CONTAMINATED_SHADOW_TARGETS = {"shadow_full_train_v1"}

FORBIDDEN_EXACT_PATHS = {
    "data/sentient_state.json",
    "app/services/velo_prime_service.py",
    "app/services/predictor.py",
    "app/services/model_loader.py",
    "app/services/model_manager.py",
    "scripts/run_prime_today.py",
    "scripts/send_telegram_summary.py",
    "config/weights.json",
}

FORBIDDEN_PREFIX_PATHS = (
    "app/router/",
    "app/staking/",
    "app/telegram/",
    "scripts/router/",
    "scripts/staking/",
    "scripts/telegram/",
)

WARN_ONLY_PATH_MATCHERS = (
    "docs/engineering/VELO_LLM_COUNCIL_V1.md",
    "docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md",
)

SCRIPT_EXTENSIONS = {".py", ".ps1", ".sh", ".bat"}


@dataclass
class GitState:
    branch: str
    dirty: bool
    modified_paths: list[str]
    staged_added_paths: list[str]


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.stdout.strip()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _git_state() -> GitState:
    branch = _run_git(["branch", "--show-current"]) or "UNKNOWN"
    modified_paths = []
    for cmd in (["diff", "--name-only"], ["ls-files", "--others", "--exclude-standard"]):
        for line in _run_git(cmd).splitlines():
            path = line.strip()
            if path:
                modified_paths.append(path.replace("\\", "/"))
    modified_paths = sorted(set(modified_paths))
    staged_added = _run_git(["diff", "--cached", "--name-only", "--diff-filter=A"]).splitlines()
    staged_added = [p.strip().replace("\\", "/") for p in staged_added if p.strip()]
    return GitState(
        branch=branch,
        dirty=bool(modified_paths),
        modified_paths=modified_paths,
        staged_added_paths=staged_added,
    )


class SafetySentinel:
    def __init__(self) -> None:
        self.ops = OpsService(dry_run=True, execute=False)

    def _safe_count(self, table: str, *, eq: tuple[str, Any] | None = None) -> int | None:
        try:
            query = self.ops._get_sb().client.table(table).select("id", count="exact")
            if eq:
                query = query.eq(eq[0], eq[1])
            resp = query.execute()
            if getattr(resp, "count", None) is not None:
                return int(resp.count or 0)
            return len(resp.data or [])
        except Exception:
            return None

    def _cloud_backup_row(self) -> dict[str, Any]:
        try:
            primary = (
                self.ops._get_sb()
                .client.table("learned_patterns")
                .select("pattern_name,pattern_type,updated_at")
                .eq("pattern_name", "SENTIENT_STATE_BACKUP")
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            if primary.data:
                return primary.data[0]
            fallback = (
                self.ops._get_sb()
                .client.table("learned_patterns")
                .select("pattern_name,pattern_type,updated_at")
                .eq("pattern_type", "SENTIENT_STATE_BACKUP")
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            if fallback.data:
                return fallback.data[0]
        except Exception as exc:
            return {"error": str(exc)}
        return {"exists": False}

    def _sigma_counts(self, date: str) -> dict[str, int | None]:
        results_path = ROOT / "data" / f"results_{date.replace('-', '_')}.json"
        results_races = 0
        if results_path.exists():
            try:
                payload = _read_json(results_path)
                races = payload.get("results", []) if isinstance(payload, dict) else payload
                if isinstance(races, list):
                    results_races = len(races)
            except Exception:
                results_races = 0
        sigma_audits = None
        try:
            resp = (
                self.ops._get_sb()
                .client.table("sigma_audits")
                .select("race_id", count="exact")
                .eq("date", date)
                .execute()
            )
            sigma_audits = int(resp.count or 0) if getattr(resp, "count", None) is not None else len(resp.data or [])
        except Exception:
            sigma_audits = None
        return {
            "results_races": results_races,
            "sigma_audits": sigma_audits,
        }

    def _prediction_exists(self, date: str) -> bool:
        path = ROOT / "data" / f"velo_prime_verdicts_{date.replace('-', '_')}.json"
        if not path.exists():
            return False
        try:
            data = _read_json(path)
            return isinstance(data, list) and len(data) > 0
        except Exception:
            return False

    def _forbidden_modified_paths(self, paths: list[str]) -> list[str]:
        hits: list[str] = []
        for path in paths:
            normalized = path.replace("\\", "/")
            if normalized in FORBIDDEN_EXACT_PATHS or any(
                normalized.startswith(prefix) for prefix in FORBIDDEN_PREFIX_PATHS
            ):
                hits.append(normalized)
        return sorted(set(hits))

    def _modified_matchers(self, paths: list[str], matchers: tuple[str, ...]) -> list[str]:
        hits: list[str] = []
        for path in paths:
            normalized = path.replace("\\", "/")
            if any(matcher in normalized for matcher in matchers):
                hits.append(normalized)
        return sorted(set(hits))

    def _secret_hits(self, paths: list[str]) -> list[str]:
        hits: list[str] = []
        for path in paths:
            lowered = path.lower()
            basename = Path(lowered).name
            if (
                lowered.endswith(".env")
                or "/.env" in lowered
                or basename in {"credentials.json", "service_account.json"}
                or "secret" in basename
                or basename.endswith(".pem")
                or basename.endswith(".p12")
                or basename.endswith(".key")
            ):
                hits.append(path)
        return sorted(set(hits))

    def _verify_false_hits(self, paths: list[str]) -> list[str]:
        hits: list[str] = []
        for path in paths:
            if path.replace("\\", "/") == "app/services/safety_sentinel.py":
                continue
            full = ROOT / path
            if not full.exists() or full.suffix not in {".py", ".ps1", ".sh", ".bat", ".js", ".ts"}:
                continue
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "verify=False" in text or "verify = False" in text:
                hits.append(path)
        return sorted(set(hits))

    def _new_executable_hits(self, staged_added_paths: list[str]) -> list[str]:
        hits: list[str] = []
        for path in staged_added_paths:
            if Path(path).suffix.lower() in SCRIPT_EXTENSIONS:
                hits.append(path)
        return sorted(set(hits))

    def evaluate(
        self,
        *,
        date: str,
        command: str = "status",
        target_state: str = APPROVED_SHADOW_TARGET,
        learning_requested: bool = False,
    ) -> dict[str, Any]:
        git_state = _git_state()
        sigma = self._sigma_counts(date)
        live_path = ROOT / "data" / "sentient_state.json"
        shadow_path = ROOT / "data" / f"sentient_state_{target_state}.json"
        live_hash = _file_hash(live_path)
        shadow_race_count = None
        if shadow_path.exists():
            try:
                shadow_race_count = int(_read_json(shadow_path).get("total_races_observed", 0))
            except Exception:
                shadow_race_count = None
        consumed_live_count = self._safe_count("velo_learning_events", eq=("consumed_live", True))
        cloud_backup = self._cloud_backup_row()

        forbidden_modified = self._forbidden_modified_paths(git_state.modified_paths)
        warn_only_modified = self._modified_matchers(git_state.modified_paths, WARN_ONLY_PATH_MATCHERS)
        secret_hits = self._secret_hits(git_state.modified_paths + git_state.staged_added_paths)
        verify_false_hits = self._verify_false_hits(git_state.modified_paths + git_state.staged_added_paths)
        new_executable_hits = self._new_executable_hits(git_state.staged_added_paths)

        checks: list[dict[str, Any]] = []
        block_reasons: list[str] = []
        warn_reasons: list[str] = []

        def add_check(name: str, status: str, detail: str, severity: str) -> None:
            checks.append(
                {
                    "name": name,
                    "status": status,
                    "severity": severity,
                    "detail": detail,
                }
            )
            if severity == "BLOCK" and status == "FAIL":
                block_reasons.append(f"{name}: {detail}")
            if severity == "WARN" and status == "FAIL":
                warn_reasons.append(f"{name}: {detail}")

        add_check(
            "approved_shadow_target",
            "PASS" if target_state == APPROVED_SHADOW_TARGET else "FAIL",
            f"target_state={target_state}",
            "BLOCK" if learning_requested else "WARN",
        )
        add_check(
            "contaminated_shadow_target",
            "FAIL" if target_state in CONTAMINATED_SHADOW_TARGETS else "PASS",
            f"target_state={target_state}",
            "BLOCK",
        )
        add_check(
            "live_state_git_clean",
            "FAIL" if "data/sentient_state.json" in git_state.modified_paths else "PASS",
            f"live_hash={live_hash}",
            "BLOCK",
        )
        add_check(
            "consumed_live_zero",
            "FAIL" if (consumed_live_count or 0) > 0 else "PASS",
            f"consumed_live_count={consumed_live_count}",
            "BLOCK",
        )
        add_check(
            "forbidden_paths_clean",
            "FAIL" if forbidden_modified else "PASS",
            ", ".join(forbidden_modified) if forbidden_modified else "no forbidden paths modified",
            "BLOCK",
        )
        add_check(
            "secret_files_clean",
            "FAIL" if secret_hits else "PASS",
            ", ".join(secret_hits) if secret_hits else "no secret-like paths modified",
            "BLOCK",
        )
        add_check(
            "verify_false_absent",
            "FAIL" if verify_false_hits else "PASS",
            ", ".join(verify_false_hits) if verify_false_hits else "no verify=False hits in changed files",
            "BLOCK",
        )
        add_check(
            "new_executable_scripts_staged",
            "FAIL" if new_executable_hits else "PASS",
            ", ".join(new_executable_hits) if new_executable_hits else "no staged executable additions",
            "BLOCK",
        )
        add_check(
            "repo_dirty",
            "FAIL" if git_state.dirty else "PASS",
            f"modified_paths={len(git_state.modified_paths)}",
            "WARN",
        )
        add_check(
            "runbook_docs_dirty",
            "FAIL" if warn_only_modified else "PASS",
            ", ".join(warn_only_modified) if warn_only_modified else "no governance doc drift",
            "WARN",
        )

        prediction_exists = self._prediction_exists(date)
        add_check(
            "prediction_overwrite_risk",
            "FAIL" if command == "predict" and prediction_exists else "PASS",
            f"prediction_exists={prediction_exists}",
            "BLOCK",
        )

        if learning_requested:
            sigma_ready = (sigma["results_races"] or 0) > 0 and (sigma["sigma_audits"] or 0) > 0
            add_check(
                "sigma_truth_ready",
                "PASS" if sigma_ready else "FAIL",
                f"results_races={sigma['results_races']} sigma_audits={sigma['sigma_audits']}",
                "BLOCK",
            )

        classification = "SAFE"
        if block_reasons:
            classification = "BLOCK"
        elif warn_reasons:
            classification = "WARN"

        report = {
            "date": date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "learning_requested": learning_requested,
            "classification": classification,
            "blocked_reason": block_reasons[0] if block_reasons else None,
            "checks": checks,
            "repo": {
                "branch": git_state.branch,
                "dirty": git_state.dirty,
                "modified_paths": git_state.modified_paths,
                "forbidden_files_modified": bool(forbidden_modified),
            },
            "state": {
                "approved_shadow_target": APPROVED_SHADOW_TARGET,
                "target_state": target_state,
                "shadow_race_count": shadow_race_count,
                "live_state_hash": live_hash,
                "cloud_backup": cloud_backup,
                "consumed_live_count": consumed_live_count,
            },
            "sigma": sigma,
        }

        out_dir = ROOT / "data" / "safety_sentinel"
        out_dir.mkdir(parents=True, exist_ok=True)
        dated_path = out_dir / f"{date}_preflight.json"
        latest_path = out_dir / "latest.json"
        payload = json.dumps(report, indent=2)
        dated_path.write_text(payload, encoding="utf-8")
        latest_path.write_text(payload, encoding="utf-8")
        return report
