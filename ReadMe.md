# NASDAQ-100 Personal Portfolio Strategy App

This project turns a toy backtesting demo into a Streamlit app for personal NASDAQ-100 portfolio planning, strategy recommendation, and daily action tracking.

## Goal

The app allows a user to:

1. Enter initial cash.
2. Enter an existing stock portfolio.
3. Choose a portfolio strategy.
4. Generate buy/sell recommendations using NASDAQ-100 stocks only.
5. Track whether each recommended action was executed.
6. Maintain a daily portfolio history.
7. Compare strategy performance against the NASDAQ-100 index.

## Disclaimer

This app is for educational and personal research use only. It does not provide financial advice.

## Current Strategy Universe

The app only recommends stocks from the NASDAQ-100 universe.

Example supported strategies:

- Top-K Momentum
- Trend-Filtered Top-K Momentum
- Momentum with Pullback
- Low-Volatility Momentum Filter
- Defensive Top-K Momentum

## Installation

```bash
git clone https://github.com/Readilyield/MyPortfolioToy.git
cd nasdaq100-portfolio-app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt