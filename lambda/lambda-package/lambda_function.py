import json
import os
import uuid
from datetime import datetime
from functools import lru_cache

import boto3
import joblib
import numpy as np
import pymysql


def risk_category(prob):
    if prob < 0.33:
        return "Low risk"
    if prob < 0.66:
        return "Medium risk"
    return "High risk"


@lru_cache(maxsize=1)
def load_model():
    model_path = os.environ.get(
        'MODEL_PATH',
        os.path.join(os.path.dirname(__file__), 'model', 'model.pkl')
    )
    return joblib.load(model_path)


def predict_probability(features):
    model = load_model()
    feature_array = np.array(features, dtype=float).reshape(1, -1)
    return float(model.predict_proba(feature_array)[0][1])


@lru_cache(maxsize=1)
def get_rds_connection():
    host = os.environ.get('RDS_HOST')
    if not host:
        return None

    return pymysql.connect(
        host=host,
        port=int(os.environ.get('RDS_PORT', '3306')),
        user=os.environ.get('RDS_USERNAME', 'admin'),
        password=os.environ.get('RDS_PASSWORD', ''),
        database=os.environ.get('RDS_DATABASE', 'health_predictions'),
        connect_timeout=5,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )


def store_in_rds(prediction_data, db_config):
    """Store prediction results in a MySQL RDS instance."""
    connection = db_config['connection']

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS predictions (
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
        created_at TIMESTAMP NULL
    )
    """

    insert_sql = """
    INSERT INTO predictions (
        id, age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang,
        outcome, probability, created_at, patient_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    with connection.cursor() as cursor:
        cursor.execute(create_table_sql)
        cursor.execute(
            insert_sql,
            (
                prediction_data['id'],
                prediction_data['age'],
                prediction_data['sex'],
                prediction_data['cp'],
                prediction_data['trestbps'],
                prediction_data['chol'],
                prediction_data['fbs'],
                prediction_data['restecg'],
                prediction_data['thalach'],
                prediction_data['exang'],
                prediction_data['outcome'],
                prediction_data['probability'],
                prediction_data['created_at'],
                prediction_data['patient_id']
            )
        )


def fetch_statistics(connection):
    """Fetch aggregated statistics from prediction records."""
    summary_sql = """
    SELECT
        COUNT(*) AS total_predictions,
        SUM(CASE WHEN outcome = 'Low risk' THEN 1 ELSE 0 END) AS low_risk_count,
        SUM(CASE WHEN outcome = 'Medium risk' THEN 1 ELSE 0 END) AS medium_risk_count,
        SUM(CASE WHEN outcome = 'High risk' THEN 1 ELSE 0 END) AS high_risk_count,
        AVG(age) AS avg_age,
        AVG(chol) AS avg_chol,
        AVG(probability) AS avg_probability
    FROM predictions
    """

    latest_sql = """
    SELECT id, patient_id, outcome, probability, created_at
    FROM predictions
    ORDER BY created_at DESC
    LIMIT 10
    """

    with connection.cursor() as cursor:
        cursor.execute(summary_sql)
        summary = cursor.fetchone() or {}
        cursor.execute(latest_sql)
        latest = cursor.fetchall() or []

    total_predictions = int(summary.get('total_predictions') or 0)
    low_risk_count = int(summary.get('low_risk_count') or 0)
    medium_risk_count = int(summary.get('medium_risk_count') or 0)
    high_risk_count = int(summary.get('high_risk_count') or 0)

    def pct(count):
        if total_predictions == 0:
            return 0.0
        return round((count / total_predictions) * 100, 2)

    return {
        "summary": {
            "total_predictions": total_predictions,
            "low_risk_count": low_risk_count,
            "medium_risk_count": medium_risk_count,
            "high_risk_count": high_risk_count,
            "low_risk_pct": pct(low_risk_count),
            "medium_risk_pct": pct(medium_risk_count),
            "high_risk_pct": pct(high_risk_count),
            "avg_age": round(float(summary.get('avg_age') or 0.0), 2),
            "avg_chol": round(float(summary.get('avg_chol') or 0.0), 2),
            "avg_probability": round(float(summary.get('avg_probability') or 0.0), 4)
        },
        "latest_predictions": latest
    }


def store_in_s3(prediction_data, bucket_name):
    """Store prediction results in S3"""
    s3_client = boto3.client('s3')

    key = f"predictions/{prediction_data['id']}.json"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(prediction_data),
        ContentType='application/json'
    )


def send_notification(prediction_data, topic_arn):
    """Send notification via SNS"""
    sns_client = boto3.client('sns')

    message = {
        "prediction_id": prediction_data['id'],
        "patient_id": prediction_data['patient_id'],
        "outcome": prediction_data['outcome'],
        "probability": prediction_data['probability'],
        "timestamp": prediction_data['created_at']
    }

    sns_client.publish(
        TopicArn=topic_arn,
        Message=json.dumps(message),
        Subject=f"Heart Disease Prediction Alert - {prediction_data['outcome']}"
    )


def lambda_handler(event, context):
    try:
        # Configuration from environment variables
        rds_host = os.environ.get('RDS_HOST')
        s3_bucket = os.environ.get('S3_BUCKET_NAME')
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')

        method = (event.get('httpMethod') or 'POST').upper()
        path = (event.get('path') or '/predict').lower()

        if method == 'OPTIONS':
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "CORS preflight OK"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
                }
            }

        if method == 'GET' and path.endswith('/stats'):
            if not rds_host:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Statistics endpoint requires RDS configuration."}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
                    }
                }

            connection = get_rds_connection()
            if connection is None:
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Could not connect to RDS."}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
                    }
                }

            stats = fetch_statistics(connection)
            return {
                "statusCode": 200,
                "body": json.dumps(stats, default=str),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
                }
            }

        # Extract features from event
        body = json.loads(event.get('body') or '{}')
        features = body.get('features')
        patient_id = body.get('patient_id', 'anonymous')

        if not features or len(features) != 9:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid or missing features. Expected 9 features."}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
                }
            }

        # Step 5: Run ML prediction locally using the packaged model
        probability = predict_probability(features)
        outcome = risk_category(probability)

        # Prepare prediction data
        prediction_id = str(uuid.uuid4())
        prediction_data = {
            "id": prediction_id,
            "patient_id": patient_id,
            "age": features[0],
            "sex": features[1],
            "cp": features[2],
            "trestbps": features[3],
            "chol": features[4],
            "fbs": features[5],
            "restecg": features[6],
            "thalach": features[7],
            "exang": features[8],
            "outcome": outcome,
            "probability": float(probability),
            "created_at": datetime.utcnow().isoformat()
        }

        # Step 6: Store results in RDS and S3
        if rds_host:
            db_config = {'connection': get_rds_connection()}
            store_in_rds(prediction_data, db_config)

        if s3_bucket:
            store_in_s3(prediction_data, s3_bucket)

        # Step 7: Send notification
        if sns_topic_arn:
            send_notification(prediction_data, sns_topic_arn)

        # Step 8: Return results
        return {
            "statusCode": 200,
            "body": json.dumps({
                "prediction_id": prediction_id,
                "outcome": outcome,
                "probability": round(float(probability), 4),
                "message": "Prediction completed and stored successfully"
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
            }
        }
