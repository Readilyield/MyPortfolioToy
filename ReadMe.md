# NASDAQ-100 Personal Portfolio Strategy App

This project turns the original Course Project 1 backtesting demo into a Streamlit app for personal NASDAQ-100 portfolio planning, strategy recommendation, execution tracking, and backtesting.

## Disclaimer

This app is for educational and personal research use only. It does not provide financial advice, investment advice, or automated trading execution.

## What the App Does

The app allows a user to:

1. Enter initial cash.
2. Enter an existing stock portfolio.
3. Select a NASDAQ-100-only portfolio strategy.
4. Generate daily buy/sell/hold recommendations.
5. Attach a suggested price range to each buy/sell recommendation.
6. Record whether each recommendation was executed.
7. Update the tracked portfolio state after executed trades.
8. Review recommendation and execution history.
9. Backtest the same strategy family before using it in the tracker.

## Repository Structure

```text
nasdaq100-portfolio-app/
├── app.py
├── pages/
│   ├── 1_Initial_Setup.py
│   ├── 2_Strategy_Recommendation.py
│   ├── 3_Portfolio_Tracker.py
│   ├── 4_Action_History.py
│   ├── 5_Backtest_Lab.py
│   └── 6_Data_Update.py
├── src/
│   ├── data_loader.py
│   ├── market_data.py
│   ├── portfolio_state.py
│   ├── recommendation_engine.py
│   ├── execution_engine.py
│   ├── strategy_registry.py
│   ├── backtester.py
│   ├── portfolio_strategies.py
│   ├── utils.py
│   └── plotting.py
├── data/
│   ├── nasdaq100_daily_5y.csv
│   ├── nasdaq100_tickers.csv
│   ├── NDX_daily_5y.csv
│   └── market_data_metadata.json  # created after refresh
├── storage/
├── notebooks/
└── tests/
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the App

```bash
streamlit run app.py
```

## Recommended First Workflow

1. Open **Initial Setup**.
2. Enter cash and existing holdings.
3. Select a strategy and save setup.
4. Open **Strategy Recommendation**.
5. Generate recommendations.
6. For each stock, record whether the recommendation was executed.
7. Open **Portfolio Tracker** to review current holdings and target allocation.
8. Open **Action History** to audit past recommendations and executions.
9. Open **Data Update** whenever you want to download the latest NASDAQ-100 and NDX daily prices.
10. Open **Backtest Lab** to test strategies and parameters.

## Strategy Design

The app separates strategy logic from execution logic:

```text
strategy function -> target weights -> target shares -> buy/sell/hold recommendation -> user execution input -> updated portfolio state
```

This makes the system reusable. Strategies only need to output target portfolio weights.

## Supported Strategy Families

- Top-K Momentum
- Trend-Filtered Top-K Momentum
- Momentum with Pullback
- Inverse-Volatility Momentum
- Low-Volatility Momentum
- Defensive Momentum
- SMA Cross

## Storage

The app uses local files in `storage/`:

- `portfolio_state.json`
- `recommendation_log.csv`
- `execution_log.csv`
- `portfolio_snapshots.csv`

These files are intentionally ignored by Git so personal portfolio information is not committed.

## Updating Market Data

The app now includes a **Data Update** page. Click **Download latest market data** to refresh the local CSV files from the internet.

The refresh process does the following:

1. Fetches the current NASDAQ-100 ticker universe from Wikipedia, unless that option is disabled.
2. Downloads NASDAQ-100 OHLCV daily price data through `yfinance`.
3. Downloads the NDX benchmark series through `yfinance`.
4. Overwrites `data/nasdaq100_daily_5y.csv` and `data/NDX_daily_5y.csv`.
5. Writes the ticker universe to `data/nasdaq100_tickers.csv`.
6. Writes refresh metadata to `data/market_data_metadata.json`.

If the live Wikipedia ticker refresh fails, disable that checkbox and the app will use the local ticker universe already stored in the repo.

The refresh button clears Streamlit's cached data after a successful download, so the recommendation and tracker pages will use the latest local files after refresh.

## Git Setup

```bash
git init
git add .
git commit -m "Initial Streamlit portfolio app"
```
