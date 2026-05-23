from __future__ import annotations

import pandas as pd

from src.market_data import yfinance_ohlcv_to_long


def test_yfinance_ohlcv_to_long_multiindex_schema():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["AAPL", "MSFT"]]
    )
    data = pd.DataFrame(1.0, index=dates, columns=columns)
    data[("Close", "AAPL")] = [10.0, 11.0]
    data[("Adj Close", "AAPL")] = [9.5, 10.5]
    data[("Volume", "AAPL")] = [100, 120]
    data[("Close", "MSFT")] = [20.0, 21.0]
    data[("Adj Close", "MSFT")] = [19.5, 20.5]

    out = yfinance_ohlcv_to_long(data, ["AAPL", "MSFT"])

    assert list(out.columns) == ["ticker", "date", "open", "high", "low", "close", "volume"]
    assert set(out["ticker"]) == {"AAPL", "MSFT"}
    assert len(out) == 4
    assert out.loc[(out["ticker"] == "AAPL") & (out["date"] == dates[0]), "close"].iloc[0] == 9.5


def test_yfinance_ohlcv_to_long_single_ticker_schema():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    data = pd.DataFrame(
        {
            "Open": [9.0, 10.0],
            "High": [11.0, 12.0],
            "Low": [8.5, 9.5],
            "Close": [10.0, 11.0],
            "Volume": [100, 120],
        },
        index=dates,
    )

    out = yfinance_ohlcv_to_long(data, ["AAPL"])

    assert set(out["ticker"]) == {"AAPL"}
    assert len(out) == 2
    assert out["close"].tolist() == [10.0, 11.0]
