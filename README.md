# Heart Disease Prediction System

An end-to-end heart disease prediction project with local model training and an AWS-hosted application.

The project includes:

- data preprocessing and model training
- local Flask-based demo application
- AWS Lambda inference API without SageMaker hosting
- patient management backed by Amazon RDS MySQL
- prediction statistics dashboard
- Amazon Cognito authentication for doctors
- password reset and forced password change flows
- S3 + CloudFront frontend hosting

## Project Structure

- data/: raw dataset files
- notebooks/: exploratory analysis and training notebooks
- src/: preprocessing, training, and local prediction scripts
- model/: trained model artifact (`model.pkl`)
- lambda/: AWS deployment package, frontend, Lambda handler, and CloudFormation templates
- report/: technical report and results
- presentation/: slides and demo material
- app.py: local Flask demo application
- models.py: local database models for local app flow

## Local Development

1. Install dependencies:
	`pip install -r requirements.txt`

2. Train the model:
	`python src/train.py`

3. Run local prediction from dataset input:
	`python src/predict.py --input data/heart.csv`

4. Start the local Flask app:
	`python app.py`

5. Open:
	`http://localhost:5000`

## AWS Application Features

The deployed AWS application supports:

- secure doctor sign-in with Amazon Cognito
- heart disease prediction through API Gateway + Lambda
- patient list, patient detail, and patient update flows
- statistics dashboard with prediction summary and latest prediction history
- automatic session restore after page refresh
- forgot password and force-change-password flows in the frontend

## AWS Lambda Event Example

Package `model/model.pkl` together with `lambda/lambda_function.py` so Lambda can run inference locally.

Example event:

```json
{
  "features": [50, 1, 2, 140, 200, 0, 1, 150, 0],
  "patient_id": "P001"
}
```

## AWS Deployment Details

See [lambda/README.md] for:

- CloudFormation stack layout
- deployment commands
- Cognito user management
- API endpoint details
- database schema
- troubleshooting guidance
