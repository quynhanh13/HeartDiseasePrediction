# Heart Disease Prediction System - AWS Architecture

This directory contains the AWS deployment for the heart disease prediction platform, including the Lambda backend, static frontend, and CloudFormation templates.

## Architecture Overview

1. Doctor signs in via Amazon Cognito.
2. Frontend is served from Amazon S3 + CloudFront.
3. API Gateway receives authenticated requests.
4. AWS Lambda handles model inference, patient management, and statistics queries.
5. Prediction history and patient records are stored in Amazon RDS MySQL.
6. Optional S3 and SNS integrations can store artifacts and send notifications.

## AWS Services Used

- Amazon Cognito for doctor authentication and password management
- Amazon S3 + CloudFront for static frontend hosting and Lambda artifacts
- Amazon API Gateway for REST API endpoints
- AWS Lambda for inference, patient management, and statistics logic
- Amazon RDS (MySQL) for structured patient and prediction data
- Amazon SNS for optional notifications

## Prerequisites

1. AWS CLI configured and authenticated
2. Python 3.9+
3. Trained model at `../model/model.pkl`
4. PowerShell or Bash shell
5. A VPC with at least 2 subnets in the target region

## Deployment Model (Split Stacks)

Infrastructure is split across six stacks for easier debugging and partial redeploy:

- `hdps-storage` -> `templates/1-storage.yaml`
- `hdps-database` -> `templates/2-database.yaml`
- `hdps-notifications` -> `templates/3-notifications.yaml`
- `hdps-compute` -> `templates/4-compute.yaml`
- `hdps-api` -> `templates/5-api.yaml`
- `hdps-frontend` -> `templates/6-frontend.yaml`

## Quick Start

1. Go to the lambda folder:

```bash
cd lambda
```

2. Deploy all stacks:

```bash
export DB_PASSWORD='Password123!'
./deploy-v2.sh
```

If `DB_PASSWORD` is empty, the script auto-generates one.

3. Check deployment status:

```bash
./deploy-v2.sh --status
```

## Partial Redeploy

Redeploy only what changed:

```bash
./deploy-v2.sh --only compute
./deploy-v2.sh --only api
./deploy-v2.sh --only frontend
```

Deploy from a stack onward:

```bash
./deploy-v2.sh --from database
```

Teardown all stacks in reverse order:

```bash
./deploy-v2.sh --teardown
```

## Frontend Upload

After editing `frontend.html`, upload it to the frontend bucket:

```bash
aws s3 cp frontend.html s3://dev-frontend-627330320034-us-east-1/index.html --region us-east-1
aws cloudfront create-invalidation --distribution-id E6S8G36CF7LQD --paths "/*" --region us-east-1
```

## Cognito Doctor Users

Create a doctor user:

```bash
aws cognito-idp admin-create-user \
   --user-pool-id YOUR_USER_POOL_ID \
   --username doctor@example.com \
   --temporary-password TempPass123! \
   --message-action SUPPRESS \
   --region us-east-1
```

Set a permanent password:

```bash
aws cognito-idp admin-set-user-password \
   --user-pool-id YOUR_USER_POOL_ID \
   --username doctor@example.com \
   --password NewStrongPass123! \
   --permanent \
   --region us-east-1
```

## Frontend Authentication Features

The frontend currently supports:

- doctor sign in
- Cognito session restore after page refresh
- forgot password flow
- password reset with verification code
- forced password change flow for first login or reset-required users

## Frontend Configuration

Update these values in `frontend.html` as needed:

- `AWS_REGION`
- `USER_POOL_ID`
- `USER_POOL_CLIENT_ID`
- `API_ENDPOINT`

## API Endpoints

### Prediction

- `POST /predict`

Example request:

```http
POST /predict
Authorization: Bearer <cognito-jwt-token>
Content-Type: application/json

{
   "features": [50, 1, 2, 140, 200, 0, 1, 150, 0],
   "patient_id": "P001"
}
```

Example response:

```json
{
   "prediction_id": "uuid",
   "outcome": "Medium risk",
   "probability": 0.63,
   "message": "Prediction completed and stored successfully"
}
```

### Statistics

- `GET /stats`

Returns summary counts, averages, and latest predictions.

### Patients

- `GET /patients`
- `GET /patients/{patientId}`
- `PUT /patients/{patientId}`

Example patient update payload:

```json
{
   "name": "Nguyen Van A",
   "date_of_birth": "1975-03-15",
   "gender": "Male",
   "contact_number": "+84901234567",
   "email": "patient@example.com",
   "address": "Hanoi, Vietnam",
   "medical_notes": "Hypertension"
}
```

## Database Schema

### predictions

```sql
CREATE TABLE predictions (
      id VARCHAR(36) PRIMARY KEY,
      patient_id VARCHAR(100),
      age DOUBLE,
      sex DOUBLE,
      cp DOUBLE,
      trestbps DOUBLE,
      chol DOUBLE,
      fbs DOUBLE,
      restecg DOUBLE,
      thalach DOUBLE,
      exang DOUBLE,
      outcome VARCHAR(20),
      probability DOUBLE,
      created_at TIMESTAMP
);
```

### patients

```sql
CREATE TABLE patients (
      patient_id VARCHAR(100) PRIMARY KEY,
      name VARCHAR(200),
      date_of_birth DATE,
      gender VARCHAR(10),
      contact_number VARCHAR(50),
      email VARCHAR(200),
      address TEXT,
      medical_notes TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

Tables are auto-created by Lambda on first use.

## Troubleshooting

1. CORS errors: Verify API Gateway deployment and OPTIONS methods.
2. Auth failures: Verify Cognito pool, client, token audience, and user status.
3. Password reset issues: Verify the Cognito user state and email delivery for verification codes.
4. Model loading errors: Ensure `model.pkl` exists and is packaged into Lambda.
5. Database connection errors: Verify VPC, subnets, security groups, DB endpoint, and credentials.
6. Endpoint connectivity errors: test with:

```bash
aws sts get-caller-identity --region us-east-1
```

If Bash or WSL is unstable, run deployment commands in PowerShell.

## Support

For debugging, check:

- CloudFormation stack events
- CloudWatch Logs (Lambda)
- API Gateway execution logs
- Lambda function errors