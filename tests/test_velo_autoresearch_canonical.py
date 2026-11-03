from scripts.backtest import velo_autoresearch_shadow as mod


def test_canonical_loader_uses_settled_scorecard_rows(monkeypatch):
    monkeypatch.setattr(
        mod,
        "_canonical_rows",
        lambda *_: [
            {
                "run_date": "2026-10-02",
                "race_id": "927457",
                "horse": "Stay Hopeful",
                "score": "0.3471",
                "settled_sp_dec": "1.91",
                "result_position": 1,
                "win": True,
                "frame": True,
                "official_evaluation_eligible": True,
            },
            {
                "run_date": "2026-10-02",
                "race_id": "void",
                "horse": "Ineligible",
                "score": "0.90",
                "settled_sp_dec": "5.0",
                "result_position": 1,
                "win": True,
                "frame": True,
                "official_evaluation_eligible": False,
            },
        ],
    )

    rows = mod.collect_canonical_records("2026-10-01", "2026-10-03")

    assert len(rows) == 1
    assert rows[0].outcome == "W"
    assert rows[0].sp == 1.91
    assert rows[0].stack_roles == ["VP30", "VP30_BASE"]


def test_canonical_metrics_use_persisted_settlement_price(monkeypatch):
    rows = [
        mod.ResearchRecord("2026-10-02", "1", "Winner", "", 0.4, "W", ["VP30"], 6.0),
        mod.ResearchRecord("2026-10-02", "2", "Loser", "", 0.4, "M", ["VP30"], 4.0),
    ]

    metrics = mod.metric_block(rows)

    assert metrics["wins"] == 1
    assert metrics["roi"] == 200.0
