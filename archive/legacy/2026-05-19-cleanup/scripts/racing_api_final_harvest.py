from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs" / "engineering"
RAW_ROOT = DATA_DIR / "racing_api_raw" / "final_harvest"
CHECKPOINT_PATH = RAW_ROOT / "checkpoint.json"
REPORT_JSON = DATA_DIR / "racing_api_final_harvest_report.json"
REPORT_MD = DOCS_DIR / "RACING_API_FINAL_HARVEST_REPORT.md"

RAW_DIRS = [
    "schema",
    "capability_map",
    "results",
    "racecards",
    "courses",
    "regions",
    "trainers",
    "jockeys",
    "horses",
    "errors",
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_env() -> None:
    for env_path in [
        ROOT / ".env",
        Path(r"C:\Users\puror\velo-oracle-prime\.env"),
        Path("/mnt/c/Users/puror/velo-oracle-prime/.env"),
    ]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def request_hash(endpoint: str, params: dict[str, Any] | None) -> str:
    blob = json_dumps({"endpoint": endpoint, "params": params or {}})
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def sample_keys(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return sorted(payload.keys())[:25]
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            return sorted(payload[0].keys())[:25]
        return ["<empty_or_scalar_list>"]
    return [f"<{type(payload).__name__}>"]


def extract_plan_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("message", "detail", "error", "msg"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value[:300]
    if isinstance(payload, str):
        return payload[:300]
    return None


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


class RateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_call = 0.0

    def wait(self) -> float:
        now = time.monotonic()
        delta = now - self._last_call
        slept = 0.0
        if delta < self.min_interval_seconds:
            slept = self.min_interval_seconds - delta
            time.sleep(slept)
        self._last_call = time.monotonic()
        return slept


@dataclass
class Probe:
    path_template: str
    category: str
    params: dict[str, Any] | None = None
    requires_seed: tuple[str, ...] = ()


class RacingAPIHarvester:
    def __init__(self, args: argparse.Namespace) -> None:
        load_env()
        self.args = args
        self.base_url = os.environ["RACING_API_BASE_URL"].rstrip("/")
        self.username = os.environ["RACING_API_USERNAME"]
        self.password = os.environ["RACING_API_PASSWORD"]
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({
            "User-Agent": "velo-oracle-prime/racing-api-final-harvest",
            "Accept": "application/json",
        })
        self.limiter = RateLimiter(args.min_interval_seconds)
        self.checkpoint = load_json(CHECKPOINT_PATH, {
            "started_utc": utc_now(),
            "updated_utc": utc_now(),
            "requests": {},
            "runs": {},
        })
        self.report: dict[str, Any] = {
            "started_utc": self.checkpoint.get("started_utc", utc_now()),
            "finished_utc": None,
            "scope": {
                "start_date": args.start_date,
                "through_date": args.through_date,
                "racecard_days": args.racecard_days,
                "max_trainers": args.max_trainers,
                "max_jockeys": args.max_jockeys,
                "max_horses": args.max_horses,
                "normalize_performed": False,
            },
            "capability_map": [],
            "results_gapfill": [],
            "racecards": [],
            "courses_regions": [],
            "trainer_analysis": [],
            "jockey_analysis": [],
            "horse_profiles": [],
            "errors": [],
        }
        self.seed: dict[str, Any] = {}

    @staticmethod
    def racecard_day_token(offset: int) -> str | None:
        if offset == 0:
            return "today"
        if offset == 1:
            return "tomorrow"
        return None

    def save_checkpoint(self) -> None:
        self.checkpoint["updated_utc"] = utc_now()
        save_json(CHECKPOINT_PATH, self.checkpoint)

    def raw_path(self, category: str, endpoint: str, params: dict[str, Any] | None) -> Path:
        req_hash = request_hash(endpoint, params)
        return RAW_ROOT / category / f"{req_hash}.json"

    def fetch(
        self,
        endpoint: str,
        category: str,
        params: dict[str, Any] | None = None,
        absolute_url: str | None = None,
    ) -> dict[str, Any]:
        path = self.raw_path(category, absolute_url or endpoint, params)
        req_hash = request_hash(absolute_url or endpoint, params)
        if path.exists():
            envelope = load_json(path, {})
            envelope["from_checkpoint"] = True
            return envelope

        url = absolute_url or f"{self.base_url}/{endpoint.lstrip('/')}"
        attempt = 0
        last_error: str | None = None
        while attempt < 5:
            attempt += 1
            slept = self.limiter.wait()
            fetched_at = utc_now()
            try:
                response = self.session.get(url, params=params, timeout=60)
                try:
                    payload = response.json()
                except Exception:
                    payload = {"non_json_text": response.text[:1000]}

                envelope = {
                    "endpoint": endpoint,
                    "absolute_url": url,
                    "params": params or {},
                    "fetched_at": fetched_at,
                    "status_code": response.status_code,
                    "request_hash": req_hash,
                    "rate_limit_wait": round(slept, 3),
                    "response_json": payload,
                    "error": None if response.status_code < 400 else extract_plan_message(payload),
                }
                save_json(path, envelope)
                self.checkpoint["requests"][req_hash] = {
                    "category": category,
                    "path": str(path),
                    "status_code": response.status_code,
                    "fetched_at": fetched_at,
                }
                self.save_checkpoint()
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 5:
                    time.sleep(min(10, 1.5 * attempt))
                    last_error = f"HTTP {response.status_code}"
                    continue
                return envelope
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < 5:
                    time.sleep(min(10, 1.5 * attempt))
                    continue

        envelope = {
            "endpoint": endpoint,
            "absolute_url": url,
            "params": params or {},
            "fetched_at": utc_now(),
            "status_code": 0,
            "request_hash": req_hash,
            "rate_limit_wait": 0,
            "response_json": None,
            "error": last_error or "unknown request error",
        }
        error_path = RAW_ROOT / "errors" / f"{req_hash}.json"
        save_json(error_path, envelope)
        self.checkpoint["requests"][req_hash] = {
            "category": "errors",
            "path": str(error_path),
            "status_code": 0,
            "fetched_at": envelope["fetched_at"],
        }
        self.save_checkpoint()
        return envelope

    def fetch_schema(self) -> dict[str, Any]:
        envelope = self.fetch(
            endpoint="openapi.json",
            category="schema",
            absolute_url="https://api.theracingapi.com/openapi.json",
        )
        payload = envelope.get("response_json") or {}
        self.report["schema"] = {
            "status_code": envelope["status_code"],
            "path_count": len(payload.get("paths", {})) if isinstance(payload, dict) else 0,
            "version": payload.get("info", {}).get("version") if isinstance(payload, dict) else None,
        }
        return payload if isinstance(payload, dict) else {}

    def fetch_seed_racecards(self) -> None:
        today_env = self.fetch(
            endpoint="racecards/standard",
            category="racecards",
            params={"day": "today", "limit": 500},
        )
        payload = today_env.get("response_json") or {}
        cards = payload.get("racecards", []) if isinstance(payload, dict) else []
        if not cards:
            return
        first_race = cards[0]
        first_runner = (first_race.get("runners") or [{}])[0]
        self.seed = {
            "race_id": first_race.get("race_id"),
            "horse_id": first_runner.get("horse_id"),
            "horse_name": first_runner.get("horse") or "Frankel",
            "trainer_id": first_runner.get("trainer_id"),
            "trainer_name": first_runner.get("trainer") or "A P O'Brien",
            "jockey_id": first_runner.get("jockey_id"),
            "jockey_name": first_runner.get("jockey") or "Ryan Moore",
        }

    def capability_map(self, schema: dict[str, Any]) -> None:
        self.fetch_seed_racecards()
        probes = [
            Probe("racecards/free", "capability_map", {"day": "today", "limit": 500}),
            Probe("racecards/basic", "capability_map", {"day": "today", "limit": 500}),
            Probe("racecards/standard", "capability_map", {"day": "today", "limit": 500}),
            Probe("racecards/pro", "capability_map", {"day": self.args.through_date, "limit": 10}),
            Probe("racecards/{race_id}/standard", "capability_map", requires_seed=("race_id",)),
            Probe("results", "capability_map", {"start_date": self.args.through_date, "end_date": self.args.through_date, "limit": 100}),
            Probe("results/today", "capability_map", {"limit": 50}),
            Probe("results/today/free", "capability_map", {"limit": 50}),
            Probe("odds/{race_id}/{horse_id}", "capability_map", requires_seed=("race_id", "horse_id")),
            Probe("horses/search", "capability_map", {"name": None}, requires_seed=("horse_name",)),
            Probe("horses/{horse_id}/results", "capability_map", requires_seed=("horse_id",)),
            Probe("horses/{horse_id}/standard", "capability_map", requires_seed=("horse_id",)),
            Probe("horses/{horse_id}/pro", "capability_map", requires_seed=("horse_id",)),
            Probe("jockeys/search", "capability_map", {"name": None}, requires_seed=("jockey_name",)),
            Probe("jockeys/{jockey_id}/results", "capability_map", requires_seed=("jockey_id",)),
            Probe("jockeys/{jockey_id}/analysis/courses", "capability_map", requires_seed=("jockey_id",)),
            Probe("jockeys/{jockey_id}/analysis/distances", "capability_map", requires_seed=("jockey_id",)),
            Probe("jockeys/{jockey_id}/analysis/trainers", "capability_map", requires_seed=("jockey_id",)),
            Probe("trainers/search", "capability_map", {"name": None}, requires_seed=("trainer_name",)),
            Probe("trainers/{trainer_id}/results", "capability_map", requires_seed=("trainer_id",)),
            Probe("trainers/{trainer_id}/analysis/courses", "capability_map", requires_seed=("trainer_id",)),
            Probe("trainers/{trainer_id}/analysis/distances", "capability_map", requires_seed=("trainer_id",)),
            Probe("trainers/{trainer_id}/analysis/jockeys", "capability_map", requires_seed=("trainer_id",)),
            Probe("courses", "courses"),
            Probe("courses/regions", "regions"),
        ]

        path_spec = schema.get("paths", {})
        results: list[dict[str, Any]] = []
        for probe in probes:
            params = dict(probe.params or {})
            missing_seed = []
            for key in probe.requires_seed:
                value = self.seed.get(key)
                if not value:
                    missing_seed.append(key)
                    continue
                if "{" + key + "}" in probe.path_template:
                    continue
                if key.endswith("_name"):
                    params["name"] = value
            if missing_seed:
                results.append({
                    "endpoint": f"/v1/{probe.path_template}",
                    "method": "GET",
                    "accessible": "requires_seed",
                    "status_code": None,
                    "required_params": missing_seed,
                    "optional_params": [],
                    "sample_keys": [],
                    "pagination_support": False,
                    "plan_limit_message": "seed value missing",
                })
                continue

            endpoint = probe.path_template.format(**self.seed)
            envelope = self.fetch(endpoint=endpoint, category=probe.category, params=params)
            spec = path_spec.get(f"/v1/{probe.path_template}", {}).get("get", {})
            param_specs = spec.get("parameters", [])
            body = envelope.get("response_json")
            accessible = "accessible" if envelope["status_code"] == 200 else "blocked" if envelope["status_code"] in {401, 403} else "error"
            results.append({
                "endpoint": f"/v1/{probe.path_template}",
                "method": "GET",
                "accessible": accessible,
                "status_code": envelope["status_code"],
                "required_params": [p.get("name") for p in param_specs if p.get("required")],
                "optional_params": [p.get("name") for p in param_specs if not p.get("required")],
                "sample_keys": sample_keys(body.get("results") if isinstance(body, dict) and "results" in body else body),
                "pagination_support": any(p.get("name") in {"limit", "skip"} for p in param_specs),
                "plan_limit_message": extract_plan_message(body),
            })

        self.report["capability_map"] = results

    def results_gapfill(self) -> None:
        start = date.fromisoformat(self.args.start_date)
        end = date.fromisoformat(self.args.through_date)
        current = start
        while current <= end:
            skip = 0
            pages = 0
            total_rows = 0
            statuses: list[int] = []
            while True:
                params = {
                    "start_date": current.isoformat(),
                    "end_date": current.isoformat(),
                    "limit": 100,
                    "skip": skip,
                }
                envelope = self.fetch("results", "results", params=params)
                statuses.append(envelope["status_code"])
                payload = envelope.get("response_json") or {}
                rows = payload.get("results", []) if isinstance(payload, dict) else []
                if envelope["status_code"] != 200:
                    self.report["errors"].append({
                        "phase": "results_gapfill",
                        "date": current.isoformat(),
                        "status_code": envelope["status_code"],
                        "error": envelope.get("error"),
                    })
                    break
                pages += 1
                total_rows += len(rows)
                if len(rows) < 100:
                    break
                skip += 100
            self.report["results_gapfill"].append({
                "date": current.isoformat(),
                "pages": pages,
                "rows": total_rows,
                "statuses": statuses,
            })
            current += timedelta(days=1)

    def racecards(self) -> None:
        endpoints = ["racecards/free", "racecards/basic", "racecards/standard"]
        for offset in range(self.args.racecard_days):
            day = self.racecard_day_token(offset)
            if not day:
                continue
            for endpoint in endpoints:
                envelope = self.fetch(endpoint, "racecards", {"day": day, "limit": 500})
                payload = envelope.get("response_json") or {}
                cards = payload.get("racecards", []) if isinstance(payload, dict) else []
                self.report["racecards"].append({
                    "endpoint": endpoint,
                    "day": day,
                    "status_code": envelope["status_code"],
                    "race_count": len(cards),
                    "runner_count": sum(len(card.get("runners", [])) for card in cards) if cards else 0,
                })

    def courses_regions(self) -> None:
        for endpoint, category in [("courses", "courses"), ("courses/regions", "regions")]:
            envelope = self.fetch(endpoint, category)
            payload = envelope.get("response_json") or {}
            count = len(payload.get("courses", [])) if isinstance(payload, dict) and "courses" in payload else len(payload) if isinstance(payload, list) else 0
            self.report["courses_regions"].append({
                "endpoint": endpoint,
                "status_code": envelope["status_code"],
                "count": count,
                "sample_keys": sample_keys(payload),
            })

    def collect_entities(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
        trainer_counter: Counter[tuple[str, str]] = Counter()
        jockey_counter: Counter[tuple[str, str]] = Counter()
        horse_counter: Counter[tuple[str, str]] = Counter()

        for verdict_path in sorted(DATA_DIR.glob("velo_prime_verdicts_2026_05_*.json")):
            try:
                day_str = verdict_path.stem.split("_", 3)[-1].replace("_", "-")
                verdict_day = date.fromisoformat(day_str)
            except Exception:
                continue
            if verdict_day < date.fromisoformat(self.args.start_date) or verdict_day > date.fromisoformat(self.args.through_date):
                continue
            try:
                rows = json.loads(verdict_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for race in rows if isinstance(rows, list) else []:
                top = race.get("top") or {}
                trainer_id = top.get("trainer_id")
                trainer_name = top.get("trainer")
                jockey_id = top.get("jockey_id")
                jockey_name = top.get("jockey")
                horse_id = top.get("horse_id")
                horse_name = top.get("horse")
                if trainer_id and trainer_name:
                    trainer_counter[(trainer_id, trainer_name)] += 1
                if jockey_id and jockey_name:
                    jockey_counter[(jockey_id, jockey_name)] += 1
                if horse_id and horse_name:
                    horse_counter[(horse_id, horse_name)] += 1

        for item in self.report["racecards"]:
            if item["endpoint"] != "racecards/standard" or item["status_code"] != 200:
                continue
            raw = self.fetch("racecards/standard", "racecards", {"day": item["day"], "limit": 500})
            payload = raw.get("response_json") or {}
            for card in payload.get("racecards", []) if isinstance(payload, dict) else []:
                for runner in card.get("runners", []):
                    if runner.get("trainer_id") and runner.get("trainer"):
                        trainer_counter[(runner["trainer_id"], runner["trainer"])] += 1
                    if runner.get("jockey_id") and runner.get("jockey"):
                        jockey_counter[(runner["jockey_id"], runner["jockey"])] += 1
                    if runner.get("horse_id") and runner.get("horse"):
                        horse_counter[(runner["horse_id"], runner["horse"])] += 1

        trainers = [(entity_id, name) for (entity_id, name), _ in trainer_counter.most_common(self.args.max_trainers)]
        jockeys = [(entity_id, name) for (entity_id, name), _ in jockey_counter.most_common(self.args.max_jockeys)]
        horses = [(entity_id, name) for (entity_id, name), _ in horse_counter.most_common(self.args.max_horses)]
        self.report["entity_selection"] = {
            "trainers_available": len(trainer_counter),
            "jockeys_available": len(jockey_counter),
            "horses_available": len(horse_counter),
            "trainers_selected": len(trainers),
            "jockeys_selected": len(jockeys),
            "horses_selected": len(horses),
        }
        return trainers, jockeys, horses

    def entity_analysis(self) -> None:
        trainers, jockeys, horses = self.collect_entities()
        trainer_endpoints = [
            "trainers/{entity_id}/analysis/courses",
            "trainers/{entity_id}/analysis/distances",
            "trainers/{entity_id}/analysis/jockeys",
        ]
        jockey_endpoints = [
            "jockeys/{entity_id}/analysis/courses",
            "jockeys/{entity_id}/analysis/distances",
            "jockeys/{entity_id}/analysis/trainers",
        ]

        for entity_id, name in trainers:
            for template in trainer_endpoints:
                endpoint = template.format(entity_id=entity_id)
                envelope = self.fetch(endpoint, "trainers", {"start_date": self.args.start_date, "end_date": self.args.through_date})
                payload = envelope.get("response_json") or {}
                self.report["trainer_analysis"].append({
                    "trainer_id": entity_id,
                    "trainer_name": name,
                    "endpoint": endpoint,
                    "status_code": envelope["status_code"],
                    "sample_keys": sample_keys(payload),
                })

        for entity_id, name in jockeys:
            for template in jockey_endpoints:
                endpoint = template.format(entity_id=entity_id)
                envelope = self.fetch(endpoint, "jockeys", {"start_date": self.args.start_date, "end_date": self.args.through_date})
                payload = envelope.get("response_json") or {}
                self.report["jockey_analysis"].append({
                    "jockey_id": entity_id,
                    "jockey_name": name,
                    "endpoint": endpoint,
                    "status_code": envelope["status_code"],
                    "sample_keys": sample_keys(payload),
                })

        for entity_id, name in horses:
            endpoint = f"horses/{entity_id}/standard"
            envelope = self.fetch(endpoint, "horses")
            payload = envelope.get("response_json") or {}
            self.report["horse_profiles"].append({
                "horse_id": entity_id,
                "horse_name": name,
                "endpoint": endpoint,
                "status_code": envelope["status_code"],
                "sample_keys": sample_keys(payload),
            })

    def finalize(self) -> None:
        self.report["finished_utc"] = utc_now()
        self.report["raw_response_counts"] = {}
        for raw_dir in RAW_DIRS:
            folder = RAW_ROOT / raw_dir
            self.report["raw_response_counts"][raw_dir] = len(list(folder.glob("*.json"))) if folder.exists() else 0
        self.report["rows_normalized"] = 0
        self.report["normalization_note"] = "Raw capture only. Normalization skipped under corrected contained scope."
        save_json(REPORT_JSON, self.report)
        self.write_markdown()

    def write_markdown(self) -> None:
        cap_accessible = sum(1 for row in self.report["capability_map"] if row.get("accessible") == "accessible")
        cap_blocked = sum(1 for row in self.report["capability_map"] if row.get("accessible") == "blocked")
        lines = [
            "# Racing API Final Harvest Report",
            "",
            f"- Started (UTC): `{self.report['started_utc']}`",
            f"- Finished (UTC): `{self.report['finished_utc']}`",
            f"- Scope: `{self.args.start_date}` to `{self.args.through_date}`",
            f"- Normalization: `{self.report['normalization_note']}`",
            "",
            "## Capability Map",
            "",
            f"- Accessible endpoints: `{cap_accessible}`",
            f"- Blocked endpoints: `{cap_blocked}`",
            "",
            "| Endpoint | Status | HTTP | Pagination | Plan message |",
            "|---|---|---:|---|---|",
        ]
        for row in self.report["capability_map"]:
            lines.append(
                f"| `{row['endpoint']}` | `{row['accessible']}` | `{row['status_code']}` | `{row['pagination_support']}` | `{(row.get('plan_limit_message') or '')[:80]}` |"
            )

        lines.extend([
            "",
            "## Results Gap-Fill",
            "",
            "| Date | Pages | Rows | Statuses |",
            "|---|---:|---:|---|",
        ])
        for row in self.report["results_gapfill"]:
            lines.append(f"| `{row['date']}` | {row['pages']} | {row['rows']} | `{row['statuses']}` |")

        lines.extend([
            "",
            "## Racecards",
            "",
            "| Endpoint | Day | HTTP | Races | Runners |",
            "|---|---|---:|---:|---:|",
        ])
        for row in self.report["racecards"]:
            lines.append(f"| `{row['endpoint']}` | `{row['day']}` | {row['status_code']} | {row['race_count']} | {row['runner_count']} |")

        lines.extend([
            "",
            "## Courses / Regions",
            "",
            "| Endpoint | HTTP | Count |",
            "|---|---:|---:|",
        ])
        for row in self.report["courses_regions"]:
            lines.append(f"| `{row['endpoint']}` | {row['status_code']} | {row['count']} |")

        entity_sel = self.report.get("entity_selection", {})
        lines.extend([
            "",
            "## Targeted Entity Analysis",
            "",
            f"- Trainers selected: `{entity_sel.get('trainers_selected', 0)}` of `{entity_sel.get('trainers_available', 0)}`",
            f"- Jockeys selected: `{entity_sel.get('jockeys_selected', 0)}` of `{entity_sel.get('jockeys_available', 0)}`",
            f"- Horses selected: `{entity_sel.get('horses_selected', 0)}` of `{entity_sel.get('horses_available', 0)}`",
            "",
            "## Raw Response Counts",
            "",
        ])
        for key, value in self.report["raw_response_counts"].items():
            lines.append(f"- `{key}`: `{value}`")

        if self.report["errors"]:
            lines.extend(["", "## Errors", ""])
            for error in self.report["errors"]:
                lines.append(f"- `{error}`")

        REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> None:
        for name in RAW_DIRS:
            (RAW_ROOT / name).mkdir(parents=True, exist_ok=True)
        schema = self.fetch_schema()
        self.capability_map(schema)
        self.results_gapfill()
        self.racecards()
        self.courses_regions()
        self.entity_analysis()
        self.finalize()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Corrected-scope Racing API final harvest runner.")
    parser.add_argument("--start-date", default="2026-05-07")
    parser.add_argument("--through-date", default=date.today().isoformat())
    parser.add_argument("--racecard-days", type=int, default=3)
    parser.add_argument("--max-trainers", type=int, default=20)
    parser.add_argument("--max-jockeys", type=int, default=20)
    parser.add_argument("--max-horses", type=int, default=20)
    parser.add_argument("--min-interval-seconds", type=float, default=0.4)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    harvester = RacingAPIHarvester(args)
    harvester.run()
    print(json.dumps({
        "report_json": str(REPORT_JSON),
        "report_md": str(REPORT_MD),
        "raw_root": str(RAW_ROOT),
    }, indent=2))


if __name__ == "__main__":
    main()
