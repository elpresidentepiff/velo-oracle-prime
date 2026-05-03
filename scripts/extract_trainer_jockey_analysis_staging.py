import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sys

import requests


if sys.platform == "win32":
    WORKROOT = Path(r"C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix")
else:
    WORKROOT = Path("/mnt/c/Users/puror/OneDrive/Documents/New project/velo_feature_v10_launch_fix")
DATA_DIR = WORKROOT / "data"
STAGING_DIR = DATA_DIR / "racing_api_staging"
DOCS_DIR = WORKROOT / "docs" / "engineering"
JSON_REPORT = DATA_DIR / "racing_api_trainer_jockey_analysis_run_v1.json"
MD_REPORT = DOCS_DIR / "RACING_API_TRAINER_JOCKEY_ANALYSIS_RUN_V1.md"
PROGRESS_FILE = DATA_DIR / "racing_api_trainer_jockey_analysis_progress_v1.json"

ENDPOINT_SPECS = [
    {
        "name": "trainer_analysis_courses",
        "entity": "trainer",
        "path": "trainers/{id}/analysis/courses",
        "id_field": "trainer_id",
        "source_table": "trainer_profiles",
        "staging_file": "trainer_analysis_courses_v1.jsonl",
    },
    {
        "name": "trainer_analysis_distances",
        "entity": "trainer",
        "path": "trainers/{id}/analysis/distances",
        "id_field": "trainer_id",
        "source_table": "trainer_profiles",
        "staging_file": "trainer_analysis_distances_v1.jsonl",
    },
    {
        "name": "trainer_analysis_jockeys",
        "entity": "trainer",
        "path": "trainers/{id}/analysis/jockeys",
        "id_field": "trainer_id",
        "source_table": "trainer_profiles",
        "staging_file": "trainer_analysis_jockeys_v1.jsonl",
    },
    {
        "name": "jockey_analysis_courses",
        "entity": "jockey",
        "path": "jockeys/{id}/analysis/courses",
        "id_field": "jockey_id",
        "source_table": "jockey_profiles",
        "staging_file": "jockey_analysis_courses_v1.jsonl",
    },
    {
        "name": "jockey_analysis_distances",
        "entity": "jockey",
        "path": "jockeys/{id}/analysis/distances",
        "id_field": "jockey_id",
        "source_table": "jockey_profiles",
        "staging_file": "jockey_analysis_distances_v1.jsonl",
    },
    {
        "name": "jockey_analysis_trainers",
        "entity": "jockey",
        "path": "jockeys/{id}/analysis/trainers",
        "id_field": "jockey_id",
        "source_table": "jockey_profiles",
        "staging_file": "jockey_analysis_trainers_v1.jsonl",
    },
]


def load_env() -> None:
    for env_path in [
        Path(r"C:\Users\puror\velo-oracle-prime\.env"),
        Path("/mnt/c/Users/puror/velo-oracle-prime/.env"),
        WORKROOT / ".env",
        Path("/mnt/c/Users/puror/OneDrive/Documents/New project/velo_feature_v10_launch_fix/.env"),
    ]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RateLimiter:
    def __init__(self, min_interval_seconds: float = 1.0) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_call = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last_call
        if delta < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - delta)
        self._last_call = time.monotonic()


class SupabaseREST:
    def __init__(self, base_url: str, service_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    def fetch_ids(self, table: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page_size = 1000
        while True:
            response = self.session.get(
                f"{self.base_url}/rest/v1/{table}",
                headers=self.headers,
                params={"select": "id,name", "order": "id.asc", "limit": str(page_size), "offset": str(len(rows))},
                timeout=60,
            )
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                break
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < page_size:
                break
        return rows


class RacingAPI:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.limiter = RateLimiter(1.0)

    def get(self, endpoint: str) -> requests.Response:
        attempt = 0
        while True:
            attempt += 1
            self.limiter.wait()
            response = self.session.get(f"{self.base_url}/{endpoint.lstrip('/')}", timeout=60)
            if response.status_code == 429 and attempt < 5:
                time.sleep(3 * attempt)
                continue
            return response


def load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {
        "started_utc": utc_now(),
        "updated_utc": utc_now(),
        "rate_limit_seconds": 1.0,
        "specs": {
            spec["name"]: {
                "next_index": 0,
                "completed": False,
                "rows_written": 0,
                "successes": 0,
                "failures": 0,
                "blocked": 0,
                "last_status": None,
            }
            for spec in ENDPOINT_SPECS
        },
    }


def save_progress(progress: dict[str, Any]) -> None:
    progress["updated_utc"] = utc_now()
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def sample_keys(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return sorted(list(payload.keys()))[:25]
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return sorted(list(payload[0].keys()))[:25]
    if isinstance(payload, list):
        return ["<empty_or_scalar_list>"]
    return [f"<{type(payload).__name__}>"]


def main() -> None:
    load_env()
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    supa = SupabaseREST(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"],
    )
    api = RacingAPI(
        os.environ["RACING_API_BASE_URL"],
        os.environ["RACING_API_USERNAME"],
        os.environ["RACING_API_PASSWORD"],
    )

    trainer_entities = supa.fetch_ids("trainer_profiles")
    jockey_entities = supa.fetch_ids("jockey_profiles")
    entity_map = {
        "trainer": trainer_entities,
        "jockey": jockey_entities,
    }

    progress = load_progress()
    report: dict[str, Any] = {
        "started_utc": progress.get("started_utc", utc_now()),
        "finished_utc": None,
        "rate_limit_seconds": 1.0,
        "entity_counts": {
            "trainer_profiles": len(trainer_entities),
            "jockey_profiles": len(jockey_entities),
        },
        "endpoint_runs": [],
    }

    for spec in ENDPOINT_SPECS:
        state = progress["specs"][spec["name"]]
        entities = entity_map[spec["entity"]]
        stage_path = STAGING_DIR / spec["staging_file"]
        for idx in range(state["next_index"], len(entities)):
            entity = entities[idx]
            entity_id = entity["id"]
            endpoint = spec["path"].format(id=entity_id)
            response = api.get(endpoint)
            try:
                payload = response.json()
            except Exception:
                payload = {"non_json": True, "text": response.text[:500]}

            entry = {
                "endpoint_name": spec["name"],
                "entity_type": spec["entity"],
                "entity_id": entity_id,
                "entity_name": entity.get("name"),
                "requested_at_utc": utc_now(),
                "status_code": response.status_code,
                "accessible": response.status_code == 200,
                "sample_keys": sample_keys(payload),
                "payload": payload if response.status_code == 200 else None,
                "error": payload if response.status_code != 200 else None,
            }
            append_jsonl(stage_path, entry)

            state["next_index"] = idx + 1
            state["last_status"] = response.status_code
            if response.status_code == 200:
                state["successes"] += 1
                state["rows_written"] += 1
            elif response.status_code in {401, 403, 404, 422}:
                state["blocked"] += 1
            else:
                state["failures"] += 1
            save_progress(progress)

        state["completed"] = True
        save_progress(progress)
        report["endpoint_runs"].append(
            {
                "endpoint_name": spec["name"],
                "entity_type": spec["entity"],
                "entities_total": len(entities),
                "rows_written": state["rows_written"],
                "successes": state["successes"],
                "blocked": state["blocked"],
                "failures": state["failures"],
                "staging_file": str(stage_path),
            }
        )

    report["finished_utc"] = utc_now()
    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Racing API Trainer/Jockey Analysis Extraction V1",
        "",
        f"- Started (UTC): `{report['started_utc']}`",
        f"- Finished (UTC): `{report['finished_utc']}`",
        f"- Rate gate: `{report['rate_limit_seconds']}` seconds per request",
        "",
        "## Entity Counts",
        "",
        f"- Trainer profiles: `{report['entity_counts']['trainer_profiles']}`",
        f"- Jockey profiles: `{report['entity_counts']['jockey_profiles']}`",
        "",
        "## Endpoint Runs",
        "",
        "| Endpoint | Entity Type | Entities | Successes | Blocked | Failures | Staging File |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for run in report["endpoint_runs"]:
        lines.append(
            f"| `{run['endpoint_name']}` | `{run['entity_type']}` | {run['entities_total']} | {run['successes']} | {run['blocked']} | {run['failures']} | `{Path(run['staging_file']).name}` |"
        )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
