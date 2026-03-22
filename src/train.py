import sys
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# make sure src package path is accessible when running `python src/train.py`
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from preprocess import load_data, clean_data, feature_engineer


def train_model(data_path="data/heart.csv", model_path="model/model.pkl"):
    df = load_data(data_path)
    df = clean_data(df)
    df = feature_engineer(df)

    if "target" not in df.columns:
        raise ValueError("Dataset must include 'target' column")

    X = df.drop(columns=["target"])
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("Sample probabilities:", y_prob[:5])

    joblib.dump(model, model_path)
    print("Saved model to", model_path)


if __name__ == "__main__":
    train_model()
