"""Decision packet rendering for Radical Velo shadow mode."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_packet(
    *,
    date: str,
    source_path: str,
    decisions: list[dict[str, Any]],
    obstacles: list[str],
    gate_status: dict[str, Any],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for decision in decisions:
        action = decision.get("radical", {}).get("action", "UNKNOWN")
        counts[action] = counts.get(action, 0) + 1
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "date": date,
        "status": "SHADOW_ONLY_NOT_LIVE",
        "live_writes": False,
        "source_path": source_path,
        "decision_counts": counts,
        "gate_status": gate_status,
        "obstacles": obstacles,
        "decisions": decisions,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Radical Velo Shadow - {packet['date']}",
        f"Generated: {packet['generated_at']}",
        "",
        f"- Status: {packet['status']}",
        f"- Live writes: {packet['live_writes']}",
        f"- Source: `{packet['source_path']}`",
        "",
        "## Decision Counts",
    ]
    for action, count in sorted(packet.get("decision_counts", {}).items()):
        lines.append(f"- {action}: {count}")
    if packet.get("obstacles"):
        lines.extend(["", "## Obstacles"])
        for item in packet["obstacles"]:
            lines.append(f"- {item}")
    lines.extend(["", "## Gate Status"])
    for key, value in packet.get("gate_status", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Decisions"])
    for row in packet.get("decisions", [])[:40]:
        radical = row.get("radical", {})
        lines.append(
            "- "
            f"{row.get('off_time', '')} {row.get('course', '')} | "
            f"{row.get('horse', '')} | "
            f"{radical.get('action', 'UNKNOWN')} | "
            f"win_gate={row.get('win_gate_probability')} "
            f"frame_gate={row.get('frame_gate_probability')} | "
            f"{', '.join(radical.get('reasons') or radical.get('warnings') or [])}"
        )
    return "\n".join(lines) + "\n"

