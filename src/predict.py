import sys
import os
import argparse
import joblib
import pandas as pd

# make sure src package path is accessible when running `python src/predict.py`
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from preprocess import clean_data, feature_engineer

def load_model(model_path="model/model.pkl"):
    return joblib.load(model_path)


def risk_category(prob):
    if prob < 0.33:
        return "Low risk"
    if prob < 0.66:
        return "Medium risk"
    return "High risk"


def predict(model, input_df):
    # preprocess: clean and feature engineer
    input_df = clean_data(input_df)
    input_df = feature_engineer(input_df)
    
    if "target" in input_df.columns:
        input_df = input_df.drop(columns=["target"])

    proba = model.predict_proba(input_df)[:, 1]
    return [risk_category(p) for p in proba]


def predict_raw(model, input_df):
    # preprocess: clean and feature engineer
    input_df = clean_data(input_df)
    input_df = feature_engineer(input_df)
    
    if "target" in input_df.columns:
        input_df = input_df.drop(columns=["target"])
    return model.predict(input_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Health risk prediction")
    parser.add_argument("--input", type=str, required=True, help="CSV file path containing features")
    parser.add_argument("--model", type=str, default="model/model.pkl")
    parser.add_argument("--mode", choices=["category", "binary"], default="category")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    model = load_model(args.model)

    if args.mode == "category":
        preds = predict(model, df)
    else:
        preds = predict_raw(model, df)

    print("Predictions:\n", preds)
