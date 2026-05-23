from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    import yfinance as yf
except Exception:  # yfinance is optional until a user refreshes data
    yf = None

from src.paths import DATA_DIR, NASDAQ_PRICES_PATH, NDX_PRICES_PATH, NASDAQ_TICKERS_PATH, DATA_METADATA_PATH

WIKIPEDIA_NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
DEFAULT_BENCHMARK_TICKER = "^NDX"


@dataclass(frozen=True)
class RefreshResult:
    """Summary returned after a market data refresh."""

    price_path: Path
    ndx_path: Path
    metadata_path: Path
    tickers_requested: int
    tickers_downloaded: int
    rows_written: int
    start_date: str | None
    end_date: str | None
    benchmark_rows_written: int


class MarketDataError(RuntimeError):
    """Raised when live market data refresh fails with a user-actionable message."""


def yfinance_environment() -> dict[str, str | bool]:
    """Return basic diagnostics for the Data Update page."""
    if yf is None:
        return {"installed": False, "version": "not installed"}
    version = getattr(yf, "__version__", "unknown")
    return {"installed": True, "version": str(version)}


def _require_yfinance() -> None:
    if yf is None:
        raise ImportError("yfinance is not installed in this Python environment. Run `pip install yfinance` inside the same virtual environment that runs Streamlit, then restart Streamlit.")


def _normalize_yahoo_ticker(symbol: str) -> str:
    """Convert symbols into the format expected by Yahoo Finance/yfinance."""
    return str(symbol).strip().upper().replace(".", "-")


def fetch_nasdaq100_tickers_from_wikipedia() -> list[str]:
    """Fetch the current Nasdaq-100 constituents from Wikipedia.

    Wikipedia is used only to build the ticker universe. Price data is downloaded
    separately from Yahoo Finance through yfinance.
    """
    tables = pd.read_html(WIKIPEDIA_NASDAQ100_URL)
    candidates: list[pd.DataFrame] = []
    for table in tables:
        lowered = {str(col).lower(): col for col in table.columns}
        if "ticker" in lowered or "symbol" in lowered:
            candidates.append(table)
    if not candidates:
        raise ValueError("Could not find a ticker table on the Nasdaq-100 Wikipedia page.")

    table = candidates[0]
    col = None
    for name in table.columns:
        if str(name).lower() in {"ticker", "symbol"}:
            col = name
            break
    if col is None:
        raise ValueError("Could not identify the ticker column in the Nasdaq-100 Wikipedia table.")

    tickers = [_normalize_yahoo_ticker(x) for x in table[col].dropna().tolist()]
    tickers = sorted(dict.fromkeys(t for t in tickers if t))
    if len(tickers) < 50:
        raise ValueError(f"Ticker fetch returned only {len(tickers)} symbols; refusing to overwrite ticker universe.")
    return tickers


def load_local_ticker_universe(csv_path: Path = NASDAQ_PRICES_PATH) -> list[str]:
    """Load tickers from the current local price CSV."""
    df = pd.read_csv(csv_path, usecols=["ticker"])
    return sorted(df["ticker"].dropna().astype(str).map(_normalize_yahoo_ticker).unique().tolist())


def save_ticker_universe(tickers: Iterable[str], path: Path = NASDAQ_TICKERS_PATH) -> None:
    """Persist the ticker universe used by the app."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame({"ticker": sorted(dict.fromkeys(_normalize_yahoo_ticker(t) for t in tickers))})
    out.to_csv(path, index=False)


def get_ticker_universe(use_live_wikipedia: bool = True) -> list[str]:
    """Return Nasdaq-100 tickers, using live Wikipedia when requested and available.

    If the live fetch fails, the existing local CSV ticker universe is used as a
    fallback so the app can still run offline.
    """
    if use_live_wikipedia:
        try:
            tickers = fetch_nasdaq100_tickers_from_wikipedia()
            save_ticker_universe(tickers)
            return tickers
        except Exception:
            pass

    if NASDAQ_TICKERS_PATH.exists():
        df = pd.read_csv(NASDAQ_TICKERS_PATH)
        if "ticker" in df.columns and not df.empty:
            return sorted(df["ticker"].dropna().astype(str).map(_normalize_yahoo_ticker).unique().tolist())

    return load_local_ticker_universe(NASDAQ_PRICES_PATH)


def _download_yfinance(
    tickers: list[str],
    period: str = "5y",
    interval: str = "1d",
    chunk_size: int = 25,
) -> pd.DataFrame:
    """Download OHLCV data from yfinance with chunked fallback.

    Bulk yfinance downloads can fail when the ticker list is large, a single
    symbol is temporarily unavailable, or Yahoo throttles the request. Chunking
    keeps the refresh usable and lets us save all successfully downloaded names.
    """
    _require_yfinance()
    tickers = [_normalize_yahoo_ticker(t) for t in tickers if str(t).strip()]
    if not tickers:
        raise ValueError("Ticker list is empty.")

    pieces: list[pd.DataFrame] = []
    failures: list[str] = []
    for i in range(0, len(tickers), max(1, chunk_size)):
        chunk = tickers[i : i + max(1, chunk_size)]
        try:
            data = yf.download(
                tickers=chunk,
                period=period,
                interval=interval,
                auto_adjust=False,
                group_by="column",
                progress=False,
                threads=True,
            )
            if data is None or data.empty:
                failures.extend(chunk)
                continue
            pieces.append(data.sort_index())
        except Exception:
            failures.extend(chunk)

    if not pieces:
        raise MarketDataError(
            "No data was returned by yfinance. This usually means Streamlit is running in a "
            "Python environment without internet access, Yahoo Finance is temporarily blocking "
            "the request, or the installed yfinance package is outdated. Try `python -m pip "
            "install --upgrade yfinance curl_cffi lxml`, restart Streamlit, and verify that your "
            "browser or firewall is not blocking outbound connections."
        )

    data = pd.concat(pieces, axis=1)
    # Remove duplicate columns that can happen if a retry/chunk overlap occurs.
    data = data.loc[:, ~data.columns.duplicated()]
    return data.sort_index()


def yfinance_ohlcv_to_long(data: pd.DataFrame, requested_tickers: list[str]) -> pd.DataFrame:
    """Convert yfinance output into the app's long-form CSV schema.

    Output columns: ticker, date, open, high, low, close, volume.
    """
    tickers = [_normalize_yahoo_ticker(t) for t in requested_tickers]

    if isinstance(data.columns, pd.MultiIndex):
        # yfinance normally returns level 0 = OHLCV field, level 1 = ticker.
        fields = set(map(str, data.columns.get_level_values(0)))
        if "Close" in fields:
            field_level = 0
            ticker_level = 1
        else:
            field_level = 1
            ticker_level = 0

        close_field = "Adj Close" if "Adj Close" in set(map(str, data.columns.get_level_values(field_level))) else "Close"
        pieces: list[pd.DataFrame] = []
        for ticker in tickers:
            if ticker not in set(map(str, data.columns.get_level_values(ticker_level))):
                continue
            try:
                one = data.xs(ticker, axis=1, level=ticker_level).copy()
            except KeyError:
                continue
            if one.empty:
                continue
            out = pd.DataFrame(index=one.index)
            out["ticker"] = ticker
            out["date"] = pd.to_datetime(one.index).date
            out["open"] = one["Open"] if "Open" in one.columns else pd.NA
            out["high"] = one["High"] if "High" in one.columns else pd.NA
            out["low"] = one["Low"] if "Low" in one.columns else pd.NA
            out["close"] = one[close_field] if close_field in one.columns else pd.NA
            out["volume"] = one["Volume"] if "Volume" in one.columns else pd.NA
            pieces.append(out.reset_index(drop=True))
        if not pieces:
            raise ValueError("Could not parse any ticker data from yfinance result.")
        long_df = pd.concat(pieces, ignore_index=True)
    else:
        # Single ticker download.
        ticker = tickers[0]
        close_field = "Adj Close" if "Adj Close" in data.columns else "Close"
        long_df = pd.DataFrame(
            {
                "ticker": ticker,
                "date": pd.to_datetime(data.index).date,
                "open": data["Open"] if "Open" in data.columns else pd.NA,
                "high": data["High"] if "High" in data.columns else pd.NA,
                "low": data["Low"] if "Low" in data.columns else pd.NA,
                "close": data[close_field] if close_field in data.columns else pd.NA,
                "volume": data["Volume"] if "Volume" in data.columns else pd.NA,
            }
        )

    long_df["date"] = pd.to_datetime(long_df["date"])
    long_df = long_df.dropna(subset=["ticker", "date", "close"])
    long_df = long_df.sort_values(["date", "ticker"]).reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        long_df[col] = pd.to_numeric(long_df[col], errors="coerce")
    return long_df[["ticker", "date", "open", "high", "low", "close", "volume"]]


def _benchmark_to_long(data: pd.DataFrame, benchmark_ticker: str = DEFAULT_BENCHMARK_TICKER) -> pd.DataFrame:
    """Convert yfinance benchmark output into the NDX CSV schema."""
    if isinstance(data.columns, pd.MultiIndex):
        # For one ticker, yfinance may still return a MultiIndex.
        try:
            one = data.xs(benchmark_ticker, axis=1, level=1)
        except Exception:
            one = data.droplevel(1, axis=1)
    else:
        one = data.copy()
    close_field = "Adj Close" if "Adj Close" in one.columns else "Close"
    if close_field not in one.columns:
        raise ValueError("Benchmark data does not contain a Close or Adj Close column.")
    return pd.DataFrame({"date": pd.to_datetime(one.index), "close": pd.to_numeric(one[close_field], errors="coerce")}).dropna()


def refresh_market_data(
    period: str = "5y",
    interval: str = "1d",
    use_live_wikipedia: bool = True,
    price_path: Path = NASDAQ_PRICES_PATH,
    ndx_path: Path = NDX_PRICES_PATH,
) -> RefreshResult:
    """Refresh Nasdaq-100 stock prices and NDX benchmark data from the internet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tickers = get_ticker_universe(use_live_wikipedia=use_live_wikipedia)
    raw = _download_yfinance(tickers, period=period, interval=interval)
    long_df = yfinance_ohlcv_to_long(raw, tickers)
    if long_df.empty:
        raise ValueError("Downloaded data could not be converted into the app schema.")

    # Persist only tickers that actually downloaded successfully.
    downloaded_tickers = sorted(long_df["ticker"].unique().tolist())
    save_ticker_universe(downloaded_tickers)
    price_path.parent.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(price_path, index=False)

    ndx_raw = _download_yfinance([DEFAULT_BENCHMARK_TICKER], period=period, interval=interval)
    ndx_df = _benchmark_to_long(ndx_raw, DEFAULT_BENCHMARK_TICKER)
    ndx_df.to_csv(ndx_path, index=False)

    metadata = {
        "source": "yfinance/Yahoo Finance",
        "ticker_universe_source": "Wikipedia Nasdaq-100" if use_live_wikipedia else "local file",
        "period": period,
        "interval": interval,
        "refreshed_at_utc": datetime.now(timezone.utc).isoformat(),
        "tickers_requested": len(tickers),
        "tickers_downloaded": len(downloaded_tickers),
        "rows_written": int(len(long_df)),
        "start_date": long_df["date"].min().date().isoformat() if not long_df.empty else None,
        "end_date": long_df["date"].max().date().isoformat() if not long_df.empty else None,
        "benchmark_ticker": DEFAULT_BENCHMARK_TICKER,
        "benchmark_rows_written": int(len(ndx_df)),
    }
    DATA_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return RefreshResult(
        price_path=price_path,
        ndx_path=ndx_path,
        metadata_path=DATA_METADATA_PATH,
        tickers_requested=len(tickers),
        tickers_downloaded=len(downloaded_tickers),
        rows_written=int(len(long_df)),
        start_date=metadata["start_date"],
        end_date=metadata["end_date"],
        benchmark_rows_written=int(len(ndx_df)),
    )


def load_data_metadata(path: Path = DATA_METADATA_PATH) -> dict:
    """Load refresh metadata if available."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
