import json

from src.velo.rich_context_challenger import build_runner_shadow_packet
from src.velo.rich_context_shadow_store import packet_row, persist_supabase_rows, write_local_jsonl


def _packet():
    return build_runner_shadow_packet(
        race_id="r1", horse_id="101", race_date="2026-11-07",
        prime_snapshot={"velo_prime_prob": 0.2},
        formfav_manifest=None,
        history_packet={"eligible": True, "source_row_ids": ["7"], "features": {"win_rate": 0.1}},
        comment_packet=None,
    )


class _Response:
    data = []


class _Query:
    def __init__(self):
        self.args = None
    def upsert(self, rows, **kwargs):
        self.args = (rows, kwargs)
        return self
    def execute(self):
        return _Response()


class _Client:
    def __init__(self):
        self.query = _Query()
    def table(self, name):
        assert name == "rich_context_shadow_packets"
        return self.query


def test_row_enforces_shadow_safety_invariants():
    row = packet_row(_packet(), code_sha="abc")
    assert row["production_influence"] is False
    assert row["provider_predictions_consumed"] is False
    assert row["challenger_probability"] is None
    assert row["enriched_feature_contract"]["feature_schema_hash"]
    assert row["enriched_feature_contract"]["vector"]


def test_local_jsonl_is_deterministic_and_complete(tmp_path):
    path = tmp_path / "packets.jsonl"
    assert write_local_jsonl([_packet()], output_path=path, code_sha="abc") == 1
    row = json.loads(path.read_text().strip())
    assert row["race_id"] == "r1"
    assert row["enriched_feature_contract"]["scoring_status"] == "AWAITING_CHRONOLOGICAL_V2_FIT"


def test_supabase_persistence_is_idempotent_by_identity_and_input_hash():
    client = _Client()
    result = persist_supabase_rows([_packet()], client=client, code_sha="abc")
    assert result == {"attempted": 1, "inserted": 0, "existing": 1}
    _rows, kwargs = client.query.args
    assert kwargs == {"on_conflict": "race_id,horse_id,input_sha256", "ignore_duplicates": True}
