# Heart Disease Prediction System - AWS Architecture

This project deploys a heart disease prediction platform on AWS without SageMaker hosting.

## Architecture Overview

1. Doctor signs in via Amazon Cognito.
2. Frontend is served from S3 + CloudFront.
3. API Gateway receives prediction requests.
4. Lambda executes model inference.
5. Results are stored in RDS and S3.
6. SNS sends prediction notifications.

## AWS Services Used

- Amazon Cognito for doctor authentication
- Amazon S3 + CloudFront for static hosting and artifacts
- Amazon API Gateway for REST API
- AWS Lambda for inference and persistence logic
- Amazon RDS (MySQL) for structured prediction data
- Amazon SNS for notifications

## Prerequisites

1. AWS CLI configured and authenticated
2. Python 3.9+
3. Trained model at `../model/model.pkl`
4. Bash shell (Git Bash / WSL)
5. A VPC with at least 2 subnets in target region

## Deployment Model (Split Stacks)

The infrastructure is split for easier debugging and partial redeploy:

- `hdps-storage` -> `templates/1-storage.yaml`
- `hdps-database` -> `templates/2-database.yaml`
- `hdps-notifications` -> `templates/3-notifications.yaml`
- `hdps-compute` -> `templates/4-compute.yaml`
- `hdps-api` -> `templates/5-api.yaml`
- `hdps-frontend` -> `templates/6-frontend.yaml`

## Quick Start

1. Go to lambda folder:

```bash
cd lambda
chmod +x deploy-v2.sh
```

2. Deploy all stacks:

```bash
export DB_PASSWORD='Password123!'
./deploy-v2.sh
```

If `DB_PASSWORD` is empty, script auto-generates one.

3. Check status:

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

Teardown all stacks (reverse order):

```bash
./deploy-v2.sh --teardown
```

## Upload Frontend

After editing `frontend.html`, upload it to the frontend bucket:

```bash
aws s3 cp frontend.html s3://dev-frontend-627330320034-us-east-1/index.html
```

Replace bucket name if your environment name or account/region differs.

## Create Doctor User

```bash
aws cognito-idp admin-create-user \
   --user-pool-id YOUR_USER_POOL_ID \
   --username doctor@example.com \
   --temporary-password TempPass123!
```

## Frontend Configuration

Update values in `frontend.html`:

- `AWS_REGION`
- `USER_POOL_ID`
- `USER_POOL_CLIENT_ID`
- `API_ENDPOINT`

## API Usage

### Endpoint

```http
POST /predict
Authorization: Bearer <cognito-jwt-token>
Content-Type: application/json

{
   "features": [50, 1, 2, 140, 200, 0, 1, 150, 0],
   "patient_id": "patient123"
}
```

### Response

```json
{
   "prediction_id": "uuid",
   "outcome": "Medium risk",
   "probability": 0.63,
   "message": "Prediction completed and stored successfully"
}
```

## Database Schema

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

Table is auto-created by Lambda on first insert.

## Troubleshooting

1. CORS errors: Verify API Gateway method/integration responses.
2. Auth failures: Verify Cognito pool, client, and token audience.
3. Model loading errors: Ensure `model.pkl` exists and is zipped into Lambda artifact.
4. Database connection errors: Verify VPC, subnets, SG rules, and DB endpoint.
5. `Could not connect to the endpoint URL`: network/proxy/WSL issue; test with:

```bash
aws sts get-caller-identity --region us-east-1
```

If Bash/WSL is unstable, run deploy commands in PowerShell.

## Support

For debugging, check:

- CloudFormation stack events
- CloudWatch Logs (Lambda)
- API Gateway execution logs
- Lambda function errors