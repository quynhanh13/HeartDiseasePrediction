#!/usr/bin/env bash

set -euo pipefail

# ================= CONFIG =================
STACK_NAME="heart-disease-prediction-system"
TEMPLATE_FILE="cloudformation-template.yaml"
ENVIRONMENT="dev"
REGION="${REGION:-us-east-1}"

DB_USERNAME="admin"
DB_PASSWORD="${DB_PASSWORD:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR=""

# ================= COLORS =================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ================= LOGGING =================
log()   { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ================= CLEANUP =================
cleanup() {
    if [[ -n "${DEPLOYMENT_DIR}" && -d "${DEPLOYMENT_DIR}" ]]; then
        rm -rf "${DEPLOYMENT_DIR}"
    fi
    rm -f "${SCRIPT_DIR}/lambda-deployment.zip"
}
trap cleanup EXIT

# ================= VALIDATION =================
check_prerequisites() {
    log "Checking prerequisites..."

    command -v aws >/dev/null || { error "AWS CLI not found"; exit 1; }
    command -v python >/dev/null || { error "Python not found"; exit 1; }

    if ! aws sts get-caller-identity --region "$REGION" &>/dev/null; then
        error "AWS CLI not configured"
        exit 1
    fi
}

# ================= PASSWORD =================
generate_password() {
    if [[ -z "$DB_PASSWORD" ]]; then
        log "Generating DB password..."
        DB_PASSWORD=$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(18))
PY
)
    fi
}

# ================= NETWORK =================
get_networking() {
    log "Fetching VPC and subnets..."

    VPC_ID=$(aws ec2 describe-vpcs \
        --region "$REGION" \
        --query 'Vpcs[0].VpcId' \
        --output text)

    SUBNET_IDS=($(aws ec2 describe-subnets \
        --region "$REGION" \
        --query 'Subnets[*].SubnetId' \
        --output text))

    if [[ -z "$VPC_ID" || ${#SUBNET_IDS[@]} -lt 2 ]]; then
        error "No valid VPC or subnets found"
        exit 1
    fi

    log "VPC: $VPC_ID"
    log "Subnet1: ${SUBNET_IDS[0]}"
    log "Subnet2: ${SUBNET_IDS[1]}"
}

# ================= BUILD =================
build_lambda() {
    log "Building Lambda package..."

    DEPLOYMENT_DIR=$(mktemp -d "${SCRIPT_DIR}/deployment_XXXX")
    cd "$DEPLOYMENT_DIR"

    cp "${SCRIPT_DIR}/lambda_function.py" .
    python -m pip install -r "${SCRIPT_DIR}/requirements.txt" -t .

    if [[ ! -f "${SCRIPT_DIR}/../model/model.pkl" ]]; then
        error "model.pkl not found"
        exit 1
    fi

    mkdir -p model
    cp "${SCRIPT_DIR}/../model/model.pkl" model/

    python - <<'PY'
import zipfile, os
zipf = zipfile.ZipFile("lambda-deployment.zip", "w")
for root, dirs, files in os.walk("."):
    for file in files:
        if "__pycache__" in root or file.endswith(".pyc"):
            continue
        path = os.path.join(root, file)
        zipf.write(path, os.path.relpath(path, "."))
zipf.close()
PY

    cd ..
    mv "${DEPLOYMENT_DIR}/lambda-deployment.zip" "${SCRIPT_DIR}/lambda-deployment.zip"
}

# ================= S3 =================
upload_artifact() {
    log "Uploading Lambda to S3..."

    ACCOUNT_ID=$(aws sts get-caller-identity \
        --query Account --output text --region "$REGION")

    ARTIFACT_BUCKET="hdps-art-${ACCOUNT_ID}-${REGION}"
    ARTIFACT_KEY="lambda/lambda-deployment.zip"

    if ! aws s3api head-bucket \
        --bucket "$ARTIFACT_BUCKET" \
        --region "$REGION" 2>/dev/null; then
        
        warn "Creating S3 bucket..."
        aws s3 mb "s3://$ARTIFACT_BUCKET" --region "$REGION"
    fi

    aws s3 cp "${SCRIPT_DIR}/lambda-deployment.zip" \
        "s3://$ARTIFACT_BUCKET/$ARTIFACT_KEY" \
        --region "$REGION"
}

# ================= STACK HANDLING =================
handle_failed_stack() {
    STATUS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region "$REGION" \
        --query "Stacks[0].StackStatus" \
        --output text 2>/dev/null || echo "NOT_EXIST")

    if [[ "$STATUS" == "ROLLBACK_COMPLETE" ]]; then
        warn "Stack in ROLLBACK_COMPLETE. Deleting..."

        aws cloudformation delete-stack \
            --stack-name $STACK_NAME \
            --region "$REGION"

        aws cloudformation wait stack-delete-complete \
            --stack-name $STACK_NAME \
            --region "$REGION"
    fi
}

# ================= DEPLOY =================
deploy_stack() {
    log "Deploying CloudFormation stack..."

    aws cloudformation deploy \
        --template-file "${SCRIPT_DIR}/${TEMPLATE_FILE}" \
        --stack-name $STACK_NAME \
        --parameter-overrides \
            EnvironmentName=$ENVIRONMENT \
            LambdaArtifactBucket=$ARTIFACT_BUCKET \
            LambdaArtifactKey=$ARTIFACT_KEY \
            VpcId=$VPC_ID \
            PublicSubnet1Id=${SUBNET_IDS[0]} \
            PublicSubnet2Id=${SUBNET_IDS[1]} \
            DBUsername=$DB_USERNAME \
            DBPassword=$DB_PASSWORD \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
}

# ================= MAIN =================
main() {
    log "🚀 Starting deployment..."

    check_prerequisites
    generate_password
    get_networking
    build_lambda
    upload_artifact
    handle_failed_stack
    deploy_stack

    log "🎉 Deployment successful!"
}

main