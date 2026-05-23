import pandas as pd
from src.portfolio_state import PortfolioState, Holding, portfolio_value


def test_portfolio_value():
    state = PortfolioState(cash=100.0, holdings={"AAPL": Holding(shares=2)})
    latest = pd.Series({"AAPL": 50.0})
    assert portfolio_value(state, latest) == 200.0
