from __future__ import annotations

import sys
import types

from app.integrations.betfair_client import BetfairClient, BetfairMode
from src.velo import execution_risk as risk

LIMITS = risk.RiskLimits(
    max_stake=10, max_liability_per_race=20, max_daily_liability=50,
    daily_loss_stop=30, bankroll_floor=100,
)


def _order(**kw):
    o = {"market_id": "1.1", "selection_id": 7, "side": "BACK", "size": 5.0, "price": 3.0,
         "customer_order_ref": "ref-1"}
    o.update(kw)
    return o


def _state(**kw):
    s = {"kill_switch": False, "operator_approval": {"approved": True, "market_ids": ["1.1"]},
         "market_status": "OPEN", "market_in_play": False, "seen_order_refs": [],
         "race_liability": 0.0, "daily_liability": 0.0, "daily_realised_pnl": 0.0, "bankroll": 500.0}
    s.update(kw)
    return s


def test_happy_path_allows() -> None:
    assert risk.authorize(_order(), _state(), LIMITS) == risk.Decision(True, "OK")


def test_every_rule_denies_with_its_own_reason() -> None:
    cases = {
        "KILL_SWITCH_ON_OR_UNKNOWN": (_order(), _state(kill_switch=True)),
        "NO_OPERATOR_APPROVAL_FOR_MARKET": (_order(), _state(operator_approval={"approved": True, "market_ids": ["9.9"]})),
        "MARKET_NOT_OPEN_PREPLAY": (_order(), _state(market_in_play=True)),
        "NO_CUSTOMER_ORDER_REF": (_order(customer_order_ref=""), _state()),
        "DUPLICATE_ORDER_REF": (_order(), _state(seen_order_refs=["ref-1"])),
        "STAKE_OUT_OF_RANGE": (_order(size=11), _state()),
        "PRICE_OUT_OF_RANGE_OR_OFF_LADDER": (_order(price=3.03), _state()),
        "RACE_LIABILITY_CAP": (_order(size=10), _state(race_liability=15)),
        "DAILY_LIABILITY_CAP": (_order(size=5), _state(daily_liability=48)),
        "DAILY_LOSS_STOP": (_order(), _state(daily_realised_pnl=-30)),
        "BANKROLL_FLOOR": (_order(size=10), _state(bankroll=105)),
        "BAD_SIDE": (_order(side="HOLD"), _state()),
    }
    for reason, (order, state) in cases.items():
        assert risk.authorize(order, state, LIMITS) == risk.Decision(False, reason), reason


def test_missing_or_malformed_inputs_deny() -> None:
    assert risk.authorize(_order(), None, LIMITS).reason == "STATE_OR_LIMITS_MISSING"
    assert risk.authorize(_order(), _state(), None).reason == "STATE_OR_LIMITS_MISSING"
    assert risk.authorize({"side": "BACK"}, _state(), LIMITS).reason == "MALFORMED_ORDER_OR_STATE"
    bad = _state()
    del bad["bankroll"]
    assert risk.authorize(_order(), bad, LIMITS).reason == "MALFORMED_ORDER_OR_STATE"
    assert risk.authorize(_order(), _state(kill_switch=None), LIMITS).reason == "KILL_SWITCH_ON_OR_UNKNOWN"


def test_lay_liability_is_size_times_price_minus_one() -> None:
    assert risk.liability("LAY", 5.0, 3.0) == 10.0
    assert risk.authorize(_order(side="LAY", size=5, price=6.0), _state(), LIMITS).reason == "RACE_LIABILITY_CAP"


def test_price_ladder() -> None:
    assert risk.on_ladder(2.02) and risk.on_ladder(3.05) and risk.on_ladder(10.5)
    assert not risk.on_ladder(2.015) and not risk.on_ladder(3.01) and not risk.on_ladder(10.2) and not risk.on_ladder(1.0)


def _fake_betfairlightweight(calls: list):
    m = types.ModuleType("betfairlightweight")
    f = types.SimpleNamespace(
        limit_order=lambda **kw: kw,
        place_instruction=lambda **kw: kw,
    )
    m.filters = f
    return m, calls


def test_live_client_blocks_by_default_and_never_reaches_betfair(monkeypatch) -> None:
    calls: list = []
    fake, _ = _fake_betfairlightweight(calls)
    monkeypatch.setitem(sys.modules, "betfairlightweight", fake)
    c = BetfairClient("k", "u", "p", mode=BetfairMode.LIVE)
    c.trading = types.SimpleNamespace(betting=types.SimpleNamespace(place_orders=lambda **kw: calls.append(kw)))
    out = c.place_order("1.1", 7, "BACK", 5.0, 3.0, customer_order_ref="ref-1")
    assert out == {"status": "BLOCKED", "error": "NO_RISK_GATE_CONFIGURED"}
    assert calls == []


def test_live_client_with_denying_gate_blocks_and_allowing_gate_reaches_betfair(monkeypatch) -> None:
    calls: list = []
    fake, _ = _fake_betfairlightweight(calls)
    monkeypatch.setitem(sys.modules, "betfairlightweight", fake)
    report = types.SimpleNamespace(bet_id="b1", placed_date="d", average_price_matched=3.0, size_matched=5.0)
    result = types.SimpleNamespace(status="SUCCESS", instruction_reports=[report])

    def place_orders(**kw):
        calls.append(kw)
        return result

    deny = BetfairClient("k", "u", "p", mode=BetfairMode.LIVE,
                         risk_gate=lambda o: risk.authorize(o, _state(kill_switch=True), LIMITS))
    deny.trading = types.SimpleNamespace(betting=types.SimpleNamespace(place_orders=place_orders))
    assert deny.place_order("1.1", 7, "BACK", 5.0, 3.0, customer_order_ref="r")["error"] == "KILL_SWITCH_ON_OR_UNKNOWN"
    assert calls == []

    ok = BetfairClient("k", "u", "p", mode=BetfairMode.LIVE,
                       risk_gate=lambda o: risk.authorize(o, _state(), LIMITS))
    ok.trading = types.SimpleNamespace(betting=types.SimpleNamespace(place_orders=place_orders))
    assert ok.place_order("1.1", 7, "BACK", 5.0, 3.0, customer_order_ref="r")["status"] == "SUCCESS"
    assert len(calls) == 1


def test_sim_mode_unaffected() -> None:
    c = BetfairClient("k", "u", "p", mode=BetfairMode.SIM)
    assert c.place_order("1.1", 7, "BACK", 5.0, 3.0)["status"] != "BLOCKED"
