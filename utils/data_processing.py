import pandas as pd
import yfinance as yf


def download_stock_data(symbol, period="2y"):
    """
    Download historical stock data using Yahoo Finance.
    """

    if not symbol:
        raise ValueError("Please enter a stock symbol.")

    symbol = symbol.strip().upper()

    allowed_periods = {"6mo", "1y", "2y", "5y"}

    if period not in allowed_periods:
        raise ValueError("Invalid historical data period.")

    data = yf.download(
        symbol,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if data.empty:
        raise ValueError(
            f"No historical data found for {symbol}. "
            "Check the symbol or internet connection."
        )

    # Handle column names returned by different yfinance versions.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()

    if "Close" not in data.columns:
        raise ValueError("Historical closing prices are unavailable.")

    data = data.dropna(subset=["Close"]).copy()

    if len(data) < 30:
        raise ValueError("Not enough historical data for prediction.")

    return data


def prepare_features(data):
    """
    Create historical price features for machine learning.
    """

    if "Close" not in data.columns:
        raise ValueError("Dataset must contain a Close column.")

    result = data.copy()

    result["Close"] = pd.to_numeric(
        result["Close"],
        errors="coerce",
    )

    result = result.dropna(subset=["Close"]).copy()

    result["MA5"] = result["Close"].rolling(5).mean()
    result["MA10"] = result["Close"].rolling(10).mean()
    result["MA20"] = result["Close"].rolling(20).mean()

    result["Return"] = result["Close"].pct_change()

    result = result.dropna().reset_index(drop=True)

    feature_columns = ["Close", "MA5", "MA10", "MA20", "Return"]

    return result, feature_columns