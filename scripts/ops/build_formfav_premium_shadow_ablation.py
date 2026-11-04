"""Timestamped FormFav Premium shadow ablation against frozen Prime.

This is research evidence only.  It never writes predictions, changes model
weights, updates a policy decision, or authorises execution.  Candidate blend
weights are sensitivity probes, not proposed production weights.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
PAGE_SIZE = 1000
ALPHAS = (0.10, 0.20, 0.30)

load_dotenv(ROOT / ".env")


def normalise_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _top(scores: dict[str, float]) -> str | None:
    return max(scores, key=scores.get) if scores else None


def blend_scores(
    prime: dict[str, float],
    evidence: dict[str, float],
    alpha: float,
) -> dict[str, float]:
    common = set(prime) & set(evidence)
    return {name: (1.0 - alpha) * prime[name] + alpha * evidence[name] for name in common}


def analyse_static_blends(
    prime: dict[str, float],
    evidence: dict[str, float],
    alphas: Iterable[float] = ALPHAS,
) -> dict[str, dict[str, Any]]:
    prime_top = _top(prime)
    output: dict[str, dict[str, Any]] = {}
    for alpha in alphas:
        scores = blend_scores(prime, evidence, alpha)
        top = _top(scores)
        output[f"{alpha:.2f}"] = {
            "top": top,
            "changed": bool(top and prime_top and top != prime_top),
            "matched_runners": len(scores),
        }
    return output


def first_market_flip(
    prime: dict[str, float],
    observations: list[dict[str, Any]],
    alpha: float,
    minimum_coverage: float = 0.80,
) -> dict[str, Any] | None:
    """First minute a market blend changes top pick with adequate coverage."""
    prime_top = _top(prime)
    if not prime_top or not observations:
        return None
    by_minute: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        captured = str(row.get("captured_at") or "")
        if captured:
            by_minute[captured[:16]].append(row)

    latest: dict[str, float] = {}
    for minute in sorted(by_minute):
        for row in by_minute[minute]:
            name = normalise_name(row.get("horse_name"))
            fair = _number((row.get("market_payload") or {}).get("market", {}).get("fairProbability"))
            if name and fair is not None:
                latest[name] = fair
        common = set(prime) & set(latest)
        coverage = len(common) / len(prime) if prime else 0.0
        if coverage < minimum_coverage:
            continue
        scores = blend_scores(prime, latest, alpha)
        top = _top(scores)
        if top and top != prime_top:
            return {
                "captured_minute_utc": minute + ":00Z",
                "from": prime_top,
                "to": top,
                "coverage": round(coverage, 4),
                "matched_runners": len(common),
            }
    return None


def _url() -> str:
    value = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    if not value:
        raise RuntimeError("SUPABASE_URL not set")
    return value


def _headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) not set")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(f"{_url()}/rest/v1/{table}", headers=_headers(), params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected {table} response: {type(data).__name__}")
    return data


def _chunks(values: list[str], size: int = 40) -> Iterable[list[str]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _in(values: Iterable[str]) -> str:
    return "in.(" + ",".join(values) + ")"


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def load_evidence(
    date_str: str,
) -> tuple[list[dict[str, Any]], dict[str, dict], dict[str, dict], dict[str, dict], list[dict]]:
    mappings = _get(
        "velo_vs_formfav",
        {
            "select": "race_id,provider_race_key,course,off_time,velo_top_horse,formfav_top_horse",
            "race_date": f"eq.{date_str}",
            "order": "off_time.asc",
        },
    )
    race_ids = [str(row["race_id"]) for row in mappings if row.get("race_id")]
    provider_keys = [str(row["provider_race_key"]) for row in mappings if row.get("provider_race_key")]

    race_meta: dict[str, dict] = {}
    for chunk in _chunks(provider_keys):
        for row in _get(
            "formfav_races",
            {"select": "provider_race_key,start_time,country,track", "provider_race_key": _in(chunk)},
        ):
            race_meta[str(row["provider_race_key"])] = row

    verdicts: dict[str, dict] = {}
    for chunk in _chunks(race_ids):
        for row in _get(
            "velo_verdicts",
            {"select": "race_id,generated_at,full_analysis", "race_id": _in(chunk)},
        ):
            verdicts[str(row["race_id"])] = row

    predictions: dict[str, dict] = {}
    for chunk in _chunks(provider_keys):
        for row in _get(
            "formfav_predictions",
            {"select": "provider_race_key,captured_at,predictions_payload", "provider_race_key": _in(chunk)},
        ):
            predictions[str(row["provider_race_key"])] = row

    markets: list[dict] = []
    for chunk in _chunks(provider_keys):
        offset = 0
        while True:
            page = _get(
                "formfav_market_snapshots",
                {
                    "select": "provider_race_key,captured_at,horse_name,best_win,best_place,market_payload",
                    "provider_race_key": _in(chunk),
                    "order": "captured_at.asc",
                    "limit": str(PAGE_SIZE),
                    "offset": str(offset),
                },
            )
            markets.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    return mappings, verdicts, predictions, race_meta, markets


def build_ablation(date_str: str) -> dict[str, Any]:
    mappings, verdicts, predictions, race_meta, market_rows = load_evidence(date_str)
    markets_by_race: dict[str, list[dict]] = defaultdict(list)
    for row in market_rows:
        markets_by_race[str(row.get("provider_race_key"))].append(row)

    races: list[dict[str, Any]] = []
    for mapping in mappings:
        race_id = str(mapping.get("race_id") or "")
        provider_key = str(mapping.get("provider_race_key") or "")
        verdict = verdicts.get(race_id) or {}
        ff_row = predictions.get(provider_key) or {}
        prime_predictions = (verdict.get("full_analysis") or {}).get("predictions") or []
        ff_payload = ff_row.get("predictions_payload") or {}
        ff_predictions = ff_payload.get("predictions") or []

        prime = {
            normalise_name(row.get("horse")): float(row["velo_prime_prob"])
            for row in prime_predictions
            if normalise_name(row.get("horse")) and _number(row.get("velo_prime_prob")) is not None
        }
        ff = {
            normalise_name(row.get("name")): float(row["winProb"])
            for row in ff_predictions
            if normalise_name(row.get("name")) and _number(row.get("winProb")) is not None
        }
        common = set(prime) & set(ff)
        prime_top = _top(prime)
        ff_top = _top(ff)
        scheduled_off = _timestamp((race_meta.get(provider_key) or {}).get("start_time"))
        market_obs = [
            row
            for row in markets_by_race.get(provider_key, [])
            if scheduled_off is not None
            and (captured := _timestamp(row.get("captured_at"))) is not None
            and captured < scheduled_off
        ]

        race = {
            "race_id": race_id,
            "provider_race_key": provider_key,
            "course": mapping.get("course"),
            "off_time": mapping.get("off_time"),
            "prime_generated_at": verdict.get("generated_at"),
            "formfav_predicted_at": ff_payload.get("predictedAt"),
            "formfav_captured_at": ff_row.get("captured_at"),
            "scheduled_off_utc": scheduled_off.isoformat() if scheduled_off else None,
            "prime_top": prime_top,
            "formfav_top": ff_top,
            "top_agreement": bool(prime_top and ff_top and prime_top == ff_top),
            "prime_runners": len(prime),
            "formfav_runners": len(ff),
            "matched_runners": len(common),
            "match_coverage": round(len(common) / len(prime), 4) if prime else 0.0,
            "formfav_blends": analyse_static_blends(prime, ff),
            "premium_market_rows": len(market_obs),
            "premium_market_first_capture": min((str(r.get("captured_at")) for r in market_obs), default=None),
            "premium_market_last_capture": max((str(r.get("captured_at")) for r in market_obs), default=None),
            "premium_market_first_flip": {
                f"{alpha:.2f}": first_market_flip(prime, market_obs, alpha) for alpha in ALPHAS
            },
        }
        races.append(race)

    summary: dict[str, Any] = {
        "races": len(races),
        "races_with_prime_and_formfav": sum(bool(r["prime_runners"] and r["formfav_runners"]) for r in races),
        "top_pick_agreements": sum(r["top_agreement"] for r in races),
        "races_with_premium_market": sum(r["premium_market_rows"] > 0 for r in races),
    }
    for alpha in ALPHAS:
        key = f"{alpha:.2f}"
        summary[f"formfav_blend_changes_{key}"] = sum(bool(r["formfav_blends"][key]["changed"]) for r in races)
        summary[f"premium_market_changes_{key}"] = sum(r["premium_market_first_flip"][key] is not None for r in races)

    return {
        "status": "SHADOW_ONLY",
        "date": date_str,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "method": {
            "prime": "frozen velo_prime_prob from velo_verdicts.full_analysis.predictions",
            "formfav": "captured FormFav winProb",
            "premium_market": "timestamped fairProbability; minute buckets; minimum 80% Prime-runner coverage",
            "sensitivity_alphas": list(ALPHAS),
            "formula": "(1-alpha)*Prime + alpha*evidence",
            "production_effect": "NONE",
        },
        "summary": summary,
        "races": races,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# FormFav Premium Shadow Ablation — {report['date']}",
        "",
        "**SHADOW ONLY. Prime predictions, weights, policy and execution were not changed.**",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Mapped races: **{s['races']}**",
        f"- Races with both full prediction fields: **{s['races_with_prime_and_formfav']}**",
        f"- Prime/FormFav top-pick agreements: **{s['top_pick_agreements']}**",
        f"- Races with Premium market snapshots: **{s['races_with_premium_market']}**",
        "",
        "| Evidence weight | FormFav-model top changes | First Premium-market top changes |",
        "|---:|---:|---:|",
    ]
    for alpha in ALPHAS:
        key = f"{alpha:.2f}"
        lines.append(
            f"| {int(alpha * 100)}% | {s[f'formfav_blend_changes_{key}']} | {s[f'premium_market_changes_{key}']} |"
        )
    lines.extend(
        [
            "",
            "## Timestamped changes",
            "",
            "| Race | Prime top | 10% market first flip | 20% market first flip | 30% market first flip |",
            "|---|---|---|---|---|",
        ]
    )
    for race in report["races"]:
        flips = race["premium_market_first_flip"]
        cells = {
            key: ("—" if not flips[key] else f"{flips[key]['captured_minute_utc']} → {flips[key]['to']}")
            for key in ("0.10", "0.20", "0.30")
        }
        lines.append(
            f"| {race['off_time']} {race['course']} | {race['prime_top'] or '—'} | {cells['0.10']} | {cells['0.20']} | {cells['0.30']} |"
        )
    lines.extend(
        [
            "",
            "Candidate percentages are sensitivity probes, not selected model weights. A change is evidence for review, not proof of improvement; settlement and chronological repetition are still required.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "reports")
    args = parser.parse_args()

    report = build_ablation(args.date)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tag = args.date.replace("-", "_")
    json_path = args.output_dir / f"formfav_premium_shadow_ablation_{tag}.json"
    md_path = args.output_dir / f"formfav_premium_shadow_ablation_{tag}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {"status": report["status"], "summary": report["summary"], "json": str(json_path), "md": str(md_path)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
