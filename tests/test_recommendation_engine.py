import pandas as pd

from src.portfolio_state import PortfolioState, Holding
from src.recommendation_engine import generate_recommendations


def test_generate_recommendations_smoke():
    dates = pd.date_range("2024-01-01", periods=120, freq="B")
    prices = pd.DataFrame({"AAPL": range(100, 220), "MSFT": range(200, 320)}, index=dates, dtype=float)
    state = PortfolioState(cash=10000.0, holdings={"AAPL": Holding(shares=5, average_cost=100)}, strategy="Top-K Momentum")
    recs = generate_recommendations(state, prices, strategy_name="Top-K Momentum", strategy_params={"lookback": 30, "top_k": 1})
    assert not recs.empty
    assert set(["ticker", "action", "share_delta"]).issubset(recs.columns)
