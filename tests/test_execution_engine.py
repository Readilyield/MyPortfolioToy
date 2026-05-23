from src.portfolio_state import PortfolioState, Holding
from src.execution_engine import apply_execution


def test_buy_execution_updates_cash_and_shares(tmp_path, monkeypatch):
    state = PortfolioState(cash=1000.0, holdings={})
    row = apply_execution(state, "AAPL", "BUY", True, 2, 100, save_state=False)
    assert state.cash == 800.0
    assert state.holdings["AAPL"].shares == 2
    assert row["executed"] is True


def test_sell_execution_updates_cash_and_shares():
    state = PortfolioState(cash=0.0, holdings={"AAPL": Holding(shares=3, average_cost=90)})
    apply_execution(state, "AAPL", "SELL", True, 1, 110, save_state=False)
    assert state.cash == 110.0
    assert state.holdings["AAPL"].shares == 2
