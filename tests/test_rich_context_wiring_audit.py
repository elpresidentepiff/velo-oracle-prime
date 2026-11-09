from scripts.ops.audit_rich_context_wiring import audit_packets
from src.velo.rich_context_challenger import build_runner_shadow_packet


def test_audit_proves_vector_and_safety_contract() -> None:
    packet = build_runner_shadow_packet(
        race_id="r1",
        horse_id="h1",
        race_date="2026-11-09",
        prime_snapshot={"velo_prime_prob": 0.2, "place_prob": 0.5, "sp_dec": 5},
        formfav_manifest={
            "training_eligible": True,
            "families": {
                "raw_facts": {"weightKg": 58},
                "provider_derived_context": {
                    "speedMap": {"earlySpeedIndex": 8},
                    "classProfile": {"currentRating": 80},
                    "trackBias": {"sampleSize": 12},
                },
            },
        },
        history_packet={"eligible": True, "features": {"win_rate": 0.2}},
        comment_packet={"training_eligible": True, "family_counts": {"pace_and_running_style": 1}},
        connections_passport={"current_jockey_pair_runs": 2},
        market_facts={"sp_dec": 5},
    )
    report = audit_packets([packet])
    assert report["wiring_pass"] is True
    assert report["fully_enriched_packets"] == 1
    assert all(item["present"] == 1 for item in report["family_coverage"].values())
