import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from utils.data_processing import (
    download_stock_data,
    prepare_features,
)


FEATURE_COLUMNS = ["Close", "MA5", "MA10", "MA20", "Return"]


def train_stock_model(data):
    """
    Train a Random Forest model using historical stock prices.
    """

    prepared_data, feature_columns = prepare_features(data)

    if len(prepared_data) < 20:
        raise ValueError("Not enough data to train the model.")

    X = prepared_data[feature_columns]
    y = prepared_data["Close"].shift(-1)

    # The target is the next available trading day's closing price.
    X = X.iloc[:-1]
    y = y.iloc[:-1]

    if len(X) < 20:
        raise ValueError("Not enough samples for model training.")

    split_index = int(len(X) * 0.8)

    if split_index < 10 or len(X) - split_index < 5:
        raise ValueError("Not enough data for model evaluation.")

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    test_predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, test_predictions)

    return model, prepared_data, float(mae)


def predict_stock_price(symbol, period="2y", days=1):
    """
    Generate iterative estimates for future trading days.

    Returns estimated prices and a basic historical test MAE.
    """

    if days not in {1, 5, 10, 20}:
        raise ValueError("Choose 1, 5, 10, or 20 trading days.")

    data = download_stock_data(symbol, period)

    model, prepared_data, mae = train_stock_model(data)

    latest_close = float(prepared_data["Close"].iloc[-1])

    # Use the latest historical data to build the first prediction.
    recent_closes = prepared_data["Close"].tail(20).tolist()

    if len(recent_closes) < 20:
        raise ValueError("Not enough closing prices.")

    future_prices = []

    for _ in range(days):

        current_price = recent_closes[-1]

        ma5 = float(np.mean(recent_closes[-5:]))
        ma10 = float(np.mean(recent_closes[-10:]))
        ma20 = float(np.mean(recent_closes[-20:]))

        previous_price = recent_closes[-2]

        daily_return = (
            (current_price - previous_price) / previous_price
            if previous_price != 0
            else 0.0
        )

        features = pd.DataFrame(
            [[current_price, ma5, ma10, ma20, daily_return]],
            columns=FEATURE_COLUMNS,
        )

        estimated_price = float(model.predict(features)[0])

        # Stock prices cannot be negative.
        estimated_price = max(0.0, estimated_price)

        future_prices.append(estimated_price)
        recent_closes.append(estimated_price)

    final_price = future_prices[-1]

    change_percent = (
        ((final_price - latest_close) / latest_close) * 100
        if latest_close != 0
        else 0.0
    )

    return {
        "symbol": symbol.strip().upper(),
        "current_price": round(latest_close, 2),
        "predicted_price": round(final_price, 2),
        "change_percent": round(change_percent, 2),
        "days": days,
        "future_prices": [round(price, 2) for price in future_prices],
        "mae": round(mae, 4),
    }