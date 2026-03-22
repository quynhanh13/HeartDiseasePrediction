import pandas as pd


def load_data(path):
    df = pd.read_csv(path)
    return df


def clean_data(df):
    # drop rows with missing values and convert categorical if needed
    df = df.dropna().copy()

    # convert any object columns to numeric where possible
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        except Exception:
            pass
    df = df.dropna()
    return df


def feature_engineer(df):
    # keep only the 9 required features + target
    features_to_keep = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg", "thalach", "exang"]
    
    # select numeric features that exist in the dataframe
    available = [f for f in features_to_keep if f in df.columns]
    numeric = df[available].copy()
    
    # preserve target if exists
    if "target" in df.columns:
        numeric["target"] = df["target"].values
    return numeric


if __name__ == "__main__":
    df = load_data("../data/heart.csv")
    df = clean_data(df)
    df = feature_engineer(df)
    print("Preprocessing complete", df.shape)
