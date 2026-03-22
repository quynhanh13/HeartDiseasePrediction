# Health Risk Prediction

A basic health risk prediction pipeline including data preprocessing, model training, prediction interface, and AWS Lambda deployment without SageMaker.

## Project structure

- data/: raw input data
- notebooks/: exploratory analysis and model training
- src/: script modules for preprocess/train/predict
- lambda/: AWS Lambda handler
- model/: persisted model artifacts
- report/: write up and results
- presentation/: slides and demos

## Getting started

1. `pip install -r requirements.txt`
2. `python src/train.py` (reads `data/heart.csv` and writes `model/model.pkl`)
3. `python src/predict.py --input data/heart.csv` (returns Low/Medium/High risk)4. `python app.py` and open `http://localhost:5000` to use the web form (enter features from heart.csv and submit)
## AWS Lambda

- Package `model/model.pkl` together with `lambda/lambda_function.py` so Lambda can run inference locally.
- `event` input format: `{"features": [age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang], "patient_id": "optional-id"}`
