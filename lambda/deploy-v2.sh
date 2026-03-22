#!/usr/bin/env bash
# deploy-v2.sh — Deploy HDPS stacks with selective deploy, teardown, and status check
# Usage:
#   ./deploy-v2.sh                          # deploy all stacks
#   ./deploy-v2.sh --only storage           # deploy one stack by name
#   ./deploy-v2.sh --from database          # deploy from stack N onwards
#   ./deploy-v2.sh --teardown               # delete all stacks in reverse order
#   ./deploy-v2.sh --status                 # show status of all stacks

set -euo pipefail

# ================= CONFIG =================
STACK_PREFIX="hdps"
ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${REGION:-us-east-1}"
DB_USERNAME="${DB_USERNAME:-admin}"
DB_PASSWORD="${DB_PASSWORD:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="${SCRIPT_DIR}/templates"
DEPLOYMENT_DIR=""

# Ordered stack list: (logical-name  template-file)
STACK_ORDER=(storage database notifications compute api frontend)
declare -A STACK_TEMPLATE=(
    [storage]="1-storage.yaml"
    [database]="2-database.yaml"
    [notifications]="3-notifications.yaml"
    [compute]="4-compute.yaml"
    [api]="5-api.yaml"
    [frontend]="6-frontend.yaml"
)

# ================= COLORS =================
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()     { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
section() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

# ================= CLEANUP =================
cleanup() {
    [[ -n "${DEPLOYMENT_DIR}" && -d "${DEPLOYMENT_DIR}" ]] && rm -rf "${DEPLOYMENT_DIR}"
    rm -f "${SCRIPT_DIR}/lambda-deployment.zip"
}
trap cleanup EXIT

# ================= VALIDATION =================
check_prerequisites() {
    section "Prerequisites"
    command -v aws    >/dev/null || { error "AWS CLI not found. Install from https://aws.amazon.com/cli/"; exit 1; }
    command -v python >/dev/null || command -v python3 >/dev/null || { error "Python not found"; exit 1; }
    # Prefer python3 if available
    command -v python3 >/dev/null && alias python=python3 2>/dev/null || true
    aws sts get-caller-identity --region "$REGION" &>/dev/null || { error "AWS credentials not configured"; exit 1; }
    log "AWS identity: $(aws sts get-caller-identity --query 'Arn' --output text --region "$REGION")"
}

# ================= PASSWORD =================
generate_password() {
    if [[ -z "$DB_PASSWORD" ]]; then
        log "Generating DB password..."
        DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(18))" 2>/dev/null \
                   || python  -c "import secrets; print(secrets.token_urlsafe(18))")
        warn "Generated DB password (save this!): ${DB_PASSWORD}"
    fi
}

# ================= NETWORK =================
get_networking() {
    section "Networking"

    VPC_ID="${VPC_ID:-}"
    if [[ -z "$VPC_ID" ]]; then
        VPC_ID=$(aws ec2 describe-vpcs \
            --region "$REGION" \
            --filters "Name=isDefault,Values=true" \
            --query 'Vpcs[0].VpcId' \
            --output text)
        # fallback to first VPC if no default
        if [[ -z "$VPC_ID" || "$VPC_ID" == "None" ]]; then
            VPC_ID=$(aws ec2 describe-vpcs \
                --region "$REGION" \
                --query 'Vpcs[0].VpcId' \
                --output text)
        fi
    fi

    mapfile -t SUBNET_IDS < <(aws ec2 describe-subnets \
        --region "$REGION" \
        --filters "Name=vpc-id,Values=${VPC_ID}" \
        --query 'Subnets[*].SubnetId' \
        --output text | tr '\t' '\n')

    if [[ -z "$VPC_ID" || "${#SUBNET_IDS[@]}" -lt 2 ]]; then
        error "Need at least 2 subnets in VPC ${VPC_ID}"
        exit 1
    fi

    log "VPC:     $VPC_ID"
    log "Subnet1: ${SUBNET_IDS[0]}"
    log "Subnet2: ${SUBNET_IDS[1]}"
}

# ================= BUILD =================
build_lambda() {
    section "Build Lambda"

    [[ -f "${SCRIPT_DIR}/../model/model.pkl" ]] || { error "model/model.pkl not found"; exit 1; }

    DEPLOYMENT_DIR=$(mktemp -d "${SCRIPT_DIR}/deployment_XXXX")
    cp "${SCRIPT_DIR}/lambda_function.py" "${DEPLOYMENT_DIR}/"
    python3 -m pip install -q -r "${SCRIPT_DIR}/requirements.txt" -t "${DEPLOYMENT_DIR}/" \
        2>/dev/null || python -m pip install -q -r "${SCRIPT_DIR}/requirements.txt" -t "${DEPLOYMENT_DIR}/"

    mkdir -p "${DEPLOYMENT_DIR}/model"
    cp "${SCRIPT_DIR}/../model/model.pkl" "${DEPLOYMENT_DIR}/model/"

    python3 - <<PY "${DEPLOYMENT_DIR}" "${SCRIPT_DIR}/lambda-deployment.zip"
import zipfile, os, sys
src_dir, out_zip = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            path = os.path.join(root, f)
            zf.write(path, os.path.relpath(path, src_dir))
print(f"Package: {out_zip} ({os.path.getsize(out_zip)//1024} KB)")
PY

    log "Lambda package built: $(du -sh "${SCRIPT_DIR}/lambda-deployment.zip" | cut -f1)"
}

# ================= S3 =================
upload_artifact() {
    section "Upload Artifact"

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
    ARTIFACT_BUCKET="hdps-art-${ACCOUNT_ID}-${REGION}"
    ARTIFACT_KEY="lambda/lambda-deployment.zip"

    if ! aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION" 2>/dev/null; then
        warn "Creating S3 bucket: $ARTIFACT_BUCKET"
        if [[ "$REGION" == "us-east-1" ]]; then
            aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"
        else
            aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION" \
                --create-bucket-configuration LocationConstraint="$REGION"
        fi
    fi

    aws s3 cp "${SCRIPT_DIR}/lambda-deployment.zip" \
        "s3://${ARTIFACT_BUCKET}/${ARTIFACT_KEY}" --region "$REGION"
    log "Uploaded to s3://${ARTIFACT_BUCKET}/${ARTIFACT_KEY}"
}

# ================= STACK STATUS =================
stack_status() {
    local stack_name="$1"
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "Stacks[0].StackStatus" \
        --output text 2>/dev/null || echo "NOT_EXIST"
}

show_all_status() {
    section "Stack Status"
    printf "%-40s %s\n" "Stack" "Status"
    printf "%-40s %s\n" "─────────────────────────────────────" "────────────────────"
    for name in "${STACK_ORDER[@]}"; do
        local full="${STACK_PREFIX}-${name}"
        local status
        status=$(stack_status "$full")
        local color=$NC
        [[ "$status" == *"COMPLETE"* && "$status" != *"DELETE"* ]] && color=$GREEN
        [[ "$status" == *"FAILED"*   ]] && color=$RED
        [[ "$status" == *"ROLLBACK"* ]] && color=$YELLOW
        [[ "$status" == "NOT_EXIST"  ]] && color=$CYAN
        printf "%-40s ${color}%s${NC}\n" "$full" "$status"
    done
}

# ================= CLEANUP FAILED =================
ensure_stack_clean() {
    local stack_name="$1"
    local status
    status=$(stack_status "$stack_name")

    if [[ "$status" == "ROLLBACK_COMPLETE" || "$status" == "CREATE_FAILED" ]]; then
        warn "Deleting failed stack: $stack_name (was: $status)"
        aws cloudformation delete-stack --stack-name "$stack_name" --region "$REGION"
        aws cloudformation wait stack-delete-complete --stack-name "$stack_name" --region "$REGION"
    fi
}

# ================= DEPLOY SINGLE STACK =================
deploy_one() {
    local name="$1"
    local template="${STACK_TEMPLATE[$name]}"
    local full="${STACK_PREFIX}-${name}"

    ensure_stack_clean "$full"
    log "Deploying: $full ← $template"

    local params=()
    case "$name" in
        storage)
            params=("EnvironmentName=${ENVIRONMENT}")
            ;;
        database)
            params=(
                "VpcId=${VPC_ID}"
                "PublicSubnet1Id=${SUBNET_IDS[0]}"
                "PublicSubnet2Id=${SUBNET_IDS[1]}"
                "DBUsername=${DB_USERNAME}"
                "DBPassword=${DB_PASSWORD}"
            )
            ;;
        notifications)
            params=()
            ;;
        compute)
            params=(
                "LambdaArtifactBucket=${ARTIFACT_BUCKET}"
                "LambdaArtifactKey=${ARTIFACT_KEY}"
                "RDSPassword=${DB_PASSWORD}"
            )
            ;;
        api)
            params=("EnvironmentName=${ENVIRONMENT}")
            ;;
        frontend)
            params=()
            ;;
    esac

    local cmd=(
        aws cloudformation deploy
        --template-file "${TEMPLATES_DIR}/${template}"
        --stack-name "$full"
        --capabilities CAPABILITY_NAMED_IAM
        --region "$REGION"
        --no-fail-on-empty-changeset
    )
    [[ "${#params[@]}" -gt 0 ]] && cmd+=(--parameter-overrides "${params[@]}")

    if "${cmd[@]}"; then
        log "✅ $full — OK"
    else
        error "❌ $full — FAILED"
        # Print CloudFormation failure events for quick debug
        aws cloudformation describe-stack-events \
            --stack-name "$full" --region "$REGION" \
            --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
            --output table 2>/dev/null || true
        exit 1
    fi
}

# ================= TEARDOWN =================
teardown_all() {
    section "Teardown — deleting stacks in reverse order"
    local reversed=()
    for (( i=${#STACK_ORDER[@]}-1; i>=0; i-- )); do
        reversed+=("${STACK_ORDER[$i]}")
    done

    for name in "${reversed[@]}"; do
        local full="${STACK_PREFIX}-${name}"
        local status
        status=$(stack_status "$full")
        if [[ "$status" == "NOT_EXIST" ]]; then
            log "Skipping $full (not deployed)"
            continue
        fi
        warn "Deleting $full..."
        aws cloudformation delete-stack --stack-name "$full" --region "$REGION"
        aws cloudformation wait stack-delete-complete --stack-name "$full" --region "$REGION"
        log "Deleted $full"
    done
}

# ================= MAIN =================
MODE="all"
ONLY_STACK=""
FROM_STACK=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --only)   MODE="only";     ONLY_STACK="$2"; shift 2 ;;
        --from)   MODE="from";     FROM_STACK="$2"; shift 2 ;;
        --teardown) MODE="teardown"; shift ;;
        --status)   MODE="status";   shift ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

case "$MODE" in
    status)
        show_all_status
        exit 0
        ;;
    teardown)
        check_prerequisites
        teardown_all
        exit 0
        ;;
    only)
        check_prerequisites
        generate_password
        get_networking
        build_lambda
        upload_artifact
        deploy_one "$ONLY_STACK"
        ;;
    from)
        check_prerequisites
        generate_password
        get_networking
        build_lambda
        upload_artifact
        section "Deploying from: $FROM_STACK"
        found=0
        for name in "${STACK_ORDER[@]}"; do
            [[ "$name" == "$FROM_STACK" ]] && found=1
            [[ "$found" -eq 1 ]] && deploy_one "$name"
        done
        [[ "$found" -eq 0 ]] && { error "Stack '$FROM_STACK' not found. Valid: ${STACK_ORDER[*]}"; exit 1; }
        ;;
    all)
        section "Full Deploy"
        check_prerequisites
        generate_password
        get_networking
        build_lambda
        upload_artifact
        for name in "${STACK_ORDER[@]}"; do
            deploy_one "$name"
        done
        ;;
esac

section "Done"
show_all_status
