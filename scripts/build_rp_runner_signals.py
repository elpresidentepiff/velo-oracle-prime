from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from statistics import pstdev
from typing import Any

from app.core.runtime_env import resolve_supabase_url, resolve_supabase_service_key, load_optional_env_file
from supabase import create_client

DECODER_VERSION = "rp_v3.0.0"
_SIMPLE_NUM_RE = re.compile(r"^(?:[A-Za-z]{1,4})?(?P<num>-?\d+(?:\.\d+)?)$")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _norm_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _extract_num(token: str | None) -> int | None:
    """
    Conservative numeric extraction from mixed tokens like '7728g' or '0196sd'.

    For v3, we only decode clearly numeric or prefix+numeric tokens. Real RP
    outing tokens like '1328sd' or '79783/4' are retained as raw tokens and
    flagged for future domain-specific decoding rather than being coerced into
    misleading integers.
    """
    if not token:
        return None

    match = _SIMPLE_NUM_RE.match(str(token).strip())
    if not match:
        return None

    try:
        return int(float(match.group("num")))
    except ValueError:
        return None


def decode_last6(tokens: list[str] | None) -> dict[str, Any]:
    cleaned_tokens: list[str] = []
    values: list[int] = []
    errors: list[dict[str, str]] = []

    for token in (tokens or [])[:6]:
        if token is None:
            continue
        cleaned = str(token).strip()
        if not cleaned:
            continue

        cleaned_tokens.append(cleaned)
        numeric = _extract_num(cleaned)
        if numeric is None:
            errors.append({"token": cleaned, "error": "no_numeric_value"})
        else:
            values.append(numeric)

    return {
        "tokens": cleaned_tokens or None,
        "values": values or None,
        "valid_count": len(values),
        "invalid_count": len(errors),
        "errors": errors,
    }


def analyze_ts_or(ts_values: list[int] | None, or_values: list[int] | None) -> dict[str, Any]:
    ts_vals = ts_values or []
    or_vals = or_values or []

    ts_delta_1 = (ts_vals[-1] - ts_vals[-2]) if len(ts_vals) >= 2 else None
    ts_delta_3 = (ts_vals[-1] - ts_vals[-4]) if len(ts_vals) >= 4 else None
    ts_slope = ((ts_vals[-1] - ts_vals[0]) / (len(ts_vals) - 1)) if len(ts_vals) >= 2 else None
    ts_volatility = pstdev(ts_vals) if len(ts_vals) >= 2 else None

    ts_rises = 0
    if len(ts_vals) >= 2:
        for idx in range(1, len(ts_vals)):
            if ts_vals[idx] > ts_vals[idx - 1]:
                ts_rises += 1

    ts_improving_flag = ts_slope is not None and ts_slope > 0 and ts_rises >= 3

    or_drop_streak = 0
    if len(or_vals) >= 2:
        for idx in range(len(or_vals) - 1, 0, -1):
            if or_vals[idx] < or_vals[idx - 1]:
                or_drop_streak += 1
            else:
                break

    or_compression_score = float(max(or_vals) - min(or_vals)) if len(or_vals) >= 2 else None

    return {
        "ts_delta_1": ts_delta_1,
        "ts_delta_3": ts_delta_3,
        "ts_slope": ts_slope,
        "ts_volatility": ts_volatility,
        "ts_improving_flag": ts_improving_flag if ts_vals else None,
        "or_drop_streak": or_drop_streak,
        "or_compression_score": or_compression_score,
    }


def build_decoder_fields(
    ts_history_last6_tokens: list[str] | None,
    or_history_last6_tokens: list[str] | None,
    *,
    confidence: float | None = None,
    decoder_version: str = DECODER_VERSION,
) -> dict[str, Any]:
    ts_decoded = decode_last6(ts_history_last6_tokens)
    or_decoded = decode_last6(or_history_last6_tokens)
    features = analyze_ts_or(ts_decoded.get("values"), or_decoded.get("values"))

    decode_errors: list[dict[str, str]] = []
    decode_errors.extend({"field": "ts", **item} for item in ts_decoded["errors"])
    decode_errors.extend({"field": "or", **item} for item in or_decoded["errors"])

    return {
        "decoder_version": decoder_version,
        "decoded_at": _utc_now_iso(),
        "decode_confidence": _norm_confidence(confidence),
        "decode_errors": decode_errors,
        "ts_history_tokens": ts_decoded["tokens"],
        "or_history_tokens": or_decoded["tokens"],
        "ts_history_values": ts_decoded["values"],
        "or_history_values": or_decoded["values"],
        "ts_history_valid_count": ts_decoded["valid_count"],
        "or_history_valid_count": or_decoded["valid_count"],
        "ts_history_invalid_count": ts_decoded["invalid_count"],
        "or_history_invalid_count": or_decoded["invalid_count"],
        "ts_improving_flag": features["ts_improving_flag"],
        "or_drop_streak": features["or_drop_streak"],
        "or_compression_score": features["or_compression_score"],
        "decoder_metrics": {
            "ts_delta_1": features["ts_delta_1"],
            "ts_delta_3": features["ts_delta_3"],
            "ts_slope": features["ts_slope"],
            "ts_volatility": features["ts_volatility"],
        },
    }


def build_row_update_from_signal(signal_row: dict[str, Any]) -> dict[str, Any]:
    raw_signal_payload = signal_row.get("raw_signal_payload") or {}
    available = raw_signal_payload.get("available_fields") or {}
    decoded = build_decoder_fields(
        available.get("ts_history_last6"),
        available.get("or_history_last6"),
    )
    decoder_metrics = decoded.pop("decoder_metrics")
    return {
        "race_key": signal_row["race_key"],
        "runner_number": signal_row["runner_number"],
        **decoded,
        "raw_signal_payload": {
            **raw_signal_payload,
            "decoder_metrics": decoder_metrics,
        },
    }


def run_backfill(limit: int | None = None, *, dry_run: bool = False) -> int:
    load_optional_env_file()
    url = resolve_supabase_url()
    key = resolve_supabase_service_key()
    if not url or not key:
        print("Error: Supabase credentials not found.")
        return 1
    supabase = create_client(url, key)

    query = supabase.table("rp_runner_signals").select("race_key,runner_number,raw_signal_payload")
    if limit:
        query = query.limit(limit)
    response = query.execute()
    rows = response.data or []

    if not rows:
        print("No rp_runner_signals rows found.")
        return 0

    updates = [build_row_update_from_signal(row) for row in rows]
    print(f"Prepared decoder updates for {len(updates)} runner signal row(s).")

    if dry_run:
        first = updates[0]
        print(
            {
                "race_key": first["race_key"],
                "runner_number": first["runner_number"],
                "ts_history_values": first.get("ts_history_values"),
                "or_history_values": first.get("or_history_values"),
                "ts_improving_flag": first.get("ts_improving_flag"),
                "or_drop_streak": first.get("or_drop_streak"),
                "or_compression_score": first.get("or_compression_score"),
            }
        )
        return 0

    supabase.table("rp_runner_signals").upsert(updates, on_conflict="race_key,runner_number").execute()
    print(f"Upserted decoder fields for {len(updates)} runner signal row(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill RP runner signal decoder fields")
    parser.add_argument("--limit", type=int, help="Limit number of rp_runner_signals rows to decode")
    parser.add_argument("--dry-run", action="store_true", help="Decode and print sample without writing to Supabase")
    args = parser.parse_args()
    return run_backfill(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
