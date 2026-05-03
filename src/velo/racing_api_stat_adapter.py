from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.velo.race_metadata_resolver import (
    chunked,
    load_env_candidates,
    normalize_text,
    resolve_supabase_headers,
    resolve_supabase_url,
    get_json,
)

MIN_RUNNERS_FOR_SIGNAL = 10
DIST_MAP: dict[float, str] = {
    4.5: "4½f",
    5.0: "5f", 5.5: "5½f",
    6.0: "6f", 6.5: "6½f",
    7.0: "7f", 7.5: "7½f",
    8.0: "1m", 8.5: "1m½f",
    9.0: "1m1f", 9.5: "1m1½f",
    10.0: "1m2f", 10.5: "1m2½f",
    11.0: "1m3f", 11.5: "1m3½f",
    12.0: "1m4f", 12.5: "1m4½f",
    13.0: "1m5f", 13.5: "1m5½f",
    14.0: "1m6f", 14.5: "1m6½f",
    15.0: "1m7f", 15.5: "1m7½f",
    16.0: "2m", 16.5: "2m½f",
    17.0: "2m1f", 17.5: "2m1½f",
    18.0: "2m2f", 18.5: "2m2½f",
    19.0: "2m3f", 19.5: "2m3½f",
    20.0: "2m4f", 20.5: "2m4½f",
    21.0: "2m5f", 21.5: "2m5½f",
    22.0: "2m6f", 22.5: "2m6½f",
    23.0: "2m7f", 23.5: "2m7½f",
    24.0: "3m", 24.5: "3m½f",
    25.0: "3m1f", 25.5: "3m1½f",
    26.0: "3m2f", 26.5: "3m2½f",
    27.0: "3m3f", 27.5: "3m3½f",
    28.0: "3m4f", 28.5: "3m4½f",
    29.0: "3m5f", 29.5: "3m5½f",
    30.0: "3m6f", 30.5: "3m6½f",
    31.0: "3m7f", 31.5: "3m7½f",
    32.0: "4m", 32.5: "4m½f",
    33.0: "4m1f", 33.5: "4m1½f",
    34.0: "4m2f", 34.5: "4m2½f",
    35.0: "4m3f", 35.5: "4m3½f",
    36.0: "4m4f", 36.5: "4m4½f",
    37.0: "4m5f", 37.5: "4m5½f",
    38.0: "4m6f", 38.5: "4m6½f",
    39.0: "4m7f", 39.5: "4m7½f",
    40.0: "5m"
}

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None

def _normalize_distance_f_to_furlongs(raw: Any) -> float | None:
    value = _safe_float(raw)
    if value is None or value <= 0:
        return None
    # 0.0 - 45.0: Already furlongs
    if value <= 45.0:
        return round(value, 1)
    # 46 - 8000: Likely yards/meters (e.g. 1760 for 1m, 3520 for 2m)
    if value <= 8000:
        return round(value / 220.0, 1)
    # Default to raw furlongs if uncertain
    return round(value, 1)

def _furlongs_to_dist(furlongs: float | None) -> str | None:
    if furlongs is None:
        return None
    rounded = round(furlongs * 2) / 2
    if rounded in DIST_MAP:
        return DIST_MAP[rounded]
    closest = min(DIST_MAP.keys(), key=lambda x: abs(x - rounded))
    return DIST_MAP[closest]

def races_distance_to_dist(raw: Any) -> str | None:
    return _furlongs_to_dist(_normalize_distance_f_to_furlongs(raw))

@dataclass
class RacingAPIStatAdapter:
    trainer_course_cache: dict[tuple[str, str], dict[str, Any]]
    trainer_distance_cache: dict[tuple[str, str], dict[str, Any]]
    trainer_jockey_cache: dict[tuple[str, str], dict[str, Any]]
    jockey_course_cache: dict[tuple[str, str], dict[str, Any]]
    jockey_distance_cache: dict[tuple[str, str], dict[str, Any]]
    jockey_trainer_cache: dict[tuple[str, str], dict[str, Any]]

    @classmethod
    def from_supabase(cls) -> "RacingAPIStatAdapter":
        load_env_candidates()
        base_url = resolve_supabase_url()
        headers = resolve_supabase_headers()
        
        def build_multi_key_cache(table: str, select: str, key_builders: list):
            rows = []
            offset = 0
            limit = 1000
            while True:
                query = f"select={select}&limit={limit}&offset={offset}"
                status, payload = get_json(f"{base_url}/rest/v1/{table}?{query}", headers=headers)
                if status == 0 or status >= 400:
                    raise RuntimeError(f"{table} fetch failed HTTP {status}: {payload}")
                if not isinstance(payload, list):
                    raise RuntimeError(f"{table} returned non-list payload")
                rows.extend(payload)
                if len(payload) < limit:
                    break
                offset += limit
            
            cache = {}
            for row in rows:
                row["below_threshold"] = (_safe_int(row.get("runners_or_rides")) or 0) < MIN_RUNNERS_FOR_SIGNAL
                for kb in key_builders:
                    k = kb(row)
                    if k[0] and k[1]:  # Both parts of the tuple must be truthy
                        cache[k] = row
            return cache

        return cls(
            trainer_course_cache=build_multi_key_cache(
                "racing_api_trainer_analysis_courses",
                "entity_id,course,course_id,runners_or_rides,wins,win_pct,ae_ratio,pnl",
                [
                    lambda row: (row.get("entity_id"), row.get("course_id")),
                    lambda row: (row.get("entity_id"), normalize_text(row.get("course")).lower() if row.get("course") else None)
                ]
            ),
            trainer_distance_cache=build_multi_key_cache(
                "racing_api_trainer_analysis_distances",
                "entity_id,dist,dist_f,runners_or_rides,wins,win_pct,ae_ratio,pnl",
                [
                    lambda row: (row.get("entity_id"), normalize_text(row.get("dist")).lower() if row.get("dist") else None),
                    lambda row: (row.get("entity_id"), str(row.get("dist_f")))
                ]
            ),
            trainer_jockey_cache=build_multi_key_cache(
                "racing_api_trainer_analysis_jockeys",
                "entity_id,jockey_id,runners_or_rides,wins,win_pct,ae_ratio,pnl",
                [lambda row: (row.get("entity_id"), row.get("jockey_id"))]
            ),
            jockey_course_cache=build_multi_key_cache(
                "racing_api_jockey_analysis_courses",
                "entity_id,course,course_id,runners_or_rides,wins,win_pct,ae_ratio,pnl",
                [
                    lambda row: (row.get("entity_id"), row.get("course_id")),
                    lambda row: (row.get("entity_id"), normalize_text(row.get("course")).lower() if row.get("course") else None)
                ]
            ),
            jockey_distance_cache=build_multi_key_cache(
                "racing_api_jockey_analysis_distances",
                "entity_id,dist,dist_f,runners_or_rides,wins,win_pct,ae_ratio,pnl",
                [
                    lambda row: (row.get("entity_id"), normalize_text(row.get("dist")).lower() if row.get("dist") else None),
                    lambda row: (row.get("entity_id"), str(row.get("dist_f")))
                ]
            ),
            jockey_trainer_cache=build_multi_key_cache(
                "racing_api_jockey_analysis_trainers",
                "entity_id,trainer_id,runners_or_rides,wins,win_pct,ae_ratio,pnl",
                [lambda row: (row.get("entity_id"), row.get("trainer_id"))]
            ),
        )

    def enrich_runner(self, runner: dict[str, Any], race: dict[str, Any]) -> dict[str, Any]:
        trainer_id = normalize_text(runner.get("trainer_id"))
        jockey_id = normalize_text(runner.get("jockey_id"))
        course = normalize_text(race.get("course"))
        course_id = normalize_text(race.get("course_id")) or normalize_text(runner.get("course_id"))
        
        dist_raw = race.get("distance_f") or runner.get("distance_f")
        dist = races_distance_to_dist(dist_raw)
        dist_f_str = str(dist_raw) if dist_raw else None

        row: dict[str, Any] = {
            "trainer_course_win_pct": None,
            "trainer_course_ae": None,
            "trainer_course_sample": None,
            "jockey_course_win_pct": None,
            "jockey_course_ae": None,
            "jockey_course_sample": None,
            "trainer_distance_win_pct": None,
            "trainer_distance_ae": None,
            "trainer_distance_sample": None,
            "jockey_distance_win_pct": None,
            "jockey_distance_ae": None,
            "jockey_distance_sample": None,
            "trainer_jockey_win_pct": None,
            "trainer_jockey_ae": None,
            "trainer_jockey_sample": None,
            "jockey_trainer_win_pct": None,
            "jockey_trainer_ae": None,
            "jockey_trainer_sample": None,
            "racing_api_connection_shadow_score": None,
            "racing_api_course_shadow_score": None,
            "racing_api_distance_shadow_score": None,
            "racing_api_enrichment_shadow_score": None,
            "racing_api_stat_status": "MISSING",
            "missing_ids_or_fields": [],
        }

        if not trainer_id: row["missing_ids_or_fields"].append("trainer_id")
        if not jockey_id: row["missing_ids_or_fields"].append("jockey_id")
        if not (course or course_id): row["missing_ids_or_fields"].append("course")
        if not (dist or dist_f_str): row["missing_ids_or_fields"].append("dist")

        def _get_from_cache(cache, keys_to_try, prefix):
            for k in keys_to_try:
                if not k[0] or not k[1]: continue
                hit = cache.get(k)
                if hit:
                    if hit.get("below_threshold"):
                        row["missing_ids_or_fields"].append(f"{prefix}_below_threshold")
                        return False
                    row[f"{prefix}_win_pct"] = _safe_float(hit.get("win_pct"))
                    row[f"{prefix}_ae"] = _safe_float(hit.get("ae_ratio"))
                    row[f"{prefix}_sample"] = _safe_int(hit.get("runners_or_rides"))
                    return True
            row["missing_ids_or_fields"].append(f"{prefix}_missing_in_db")
            return False

        # Try Course ID first, then Course Name
        t_course_keys = [(trainer_id, course_id), (trainer_id, course.lower() if course else None)]
        j_course_keys = [(jockey_id, course_id), (jockey_id, course.lower() if course else None)]
        
        # Try mapped distance text first, then raw distance_f string
        t_dist_keys = [(trainer_id, dist.lower() if dist else None), (trainer_id, dist_f_str)]
        j_dist_keys = [(jockey_id, dist.lower() if dist else None), (jockey_id, dist_f_str)]

        if trainer_id:
            _get_from_cache(self.trainer_course_cache, t_course_keys, "trainer_course")
            _get_from_cache(self.trainer_distance_cache, t_dist_keys, "trainer_distance")
            if jockey_id:
                _get_from_cache(self.trainer_jockey_cache, [(trainer_id, jockey_id)], "trainer_jockey")
        
        if jockey_id:
            _get_from_cache(self.jockey_course_cache, j_course_keys, "jockey_course")
            _get_from_cache(self.jockey_distance_cache, j_dist_keys, "jockey_distance")
            if trainer_id:
                _get_from_cache(self.jockey_trainer_cache, [(jockey_id, trainer_id)], "jockey_trainer")

        self._compute_shadow_scores(row)

        score_fields = [
            row["racing_api_connection_shadow_score"],
            row["racing_api_course_shadow_score"],
            row["racing_api_distance_shadow_score"],
        ]
        populated = sum(1 for field in score_fields if field is not None)
        if populated == 3:
            row["racing_api_stat_status"] = "COMPLETE"
        elif populated > 0:
            row["racing_api_stat_status"] = "PARTIAL"
        else:
            row["racing_api_stat_status"] = "MISSING"
        return row

    @staticmethod
    def _compute_shadow_scores(row: dict[str, Any]) -> None:
        conn_wp, conn_ae = [], []
        for prefix in ("trainer_jockey", "jockey_trainer"):
            wp = row.get(f"{prefix}_win_pct")
            ae = row.get(f"{prefix}_ae")
            if wp is not None: conn_wp.append(float(wp))
            if ae is not None: conn_ae.append(float(ae))
        if conn_wp:
            row["racing_api_connection_shadow_score"] = round(0.6 * (_avg(conn_wp) or 0.0) + 0.4 * ((_avg(conn_ae) or 1.0)), 4)

        crs_wp, crs_ae = [], []
        for prefix in ("trainer_course", "jockey_course"):
            wp = row.get(f"{prefix}_win_pct")
            ae = row.get(f"{prefix}_ae")
            if wp is not None: crs_wp.append(float(wp))
            if ae is not None: crs_ae.append(float(ae))
        if crs_wp:
            row["racing_api_course_shadow_score"] = round(0.6 * (_avg(crs_wp) or 0.0) + 0.4 * ((_avg(crs_ae) or 1.0)), 4)

        dst_wp, dst_ae = [], []
        for prefix in ("trainer_distance", "jockey_distance"):
            wp = row.get(f"{prefix}_win_pct")
            ae = row.get(f"{prefix}_ae")
            if wp is not None: dst_wp.append(float(wp))
            if ae is not None: dst_ae.append(float(ae))
        if dst_wp:
            row["racing_api_distance_shadow_score"] = round(0.6 * (_avg(dst_wp) or 0.0) + 0.4 * ((_avg(dst_ae) or 1.0)), 4)

        all_wp = conn_wp + crs_wp + dst_wp
        all_ae = conn_ae + crs_ae + dst_ae
        if all_wp:
            row["racing_api_enrichment_shadow_score"] = round(0.6 * (_avg(all_wp) or 0.0) + 0.4 * ((_avg(all_ae) or 1.0)), 4)
