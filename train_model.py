import argparse
import joblib
import os

from utils.prediction import train_stock_model
from utils.data_processing import download_stock_data


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_DIR = os.path.join(BASE_DIR, "models")
DATASET_DIR = os.path.join(BASE_DIR, "dataset")


def main():

    parser = argparse.ArgumentParser(
        description="Train the StockPredictAI machine learning model."
    )

    parser.add_argument(
        "--symbol",
        default="AAPL",
        help="Stock symbol, for example AAPL or RELIANCE.NS",
    )

    parser.add_argument(
        "--period",
        default="2y",
        choices=["6mo", "1y", "2y", "5y"],
        help="Historical data period",
    )

    args = parser.parse_args()

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(DATASET_DIR, exist_ok=True)

    print(f"Downloading historical data for {args.symbol}...")

    data = download_stock_data(args.symbol, args.period)

    dataset_path = os.path.join(
        DATASET_DIR,
        f"{args.symbol.replace('.', '_')}_data.csv",
    )

    data.to_csv(dataset_path, index=False)

    print("Training machine learning model...")

    model, prepared_data, mae = train_stock_model(data)

    model_path = os.path.join(
        MODEL_DIR,
        f"{args.symbol.replace('.', '_')}_model.joblib",
    )

    joblib.dump(model, model_path)

    print("\nModel training completed.")
    print(f"Stock symbol: {args.symbol.upper()}")
    print(f"Training samples: {len(prepared_data)}")
    print(f"Test MAE: {mae:.4f}")
    print(f"Dataset saved: {dataset_path}")
    print(f"Model saved: {model_path}")


if __name__ == "__main__":
    main()