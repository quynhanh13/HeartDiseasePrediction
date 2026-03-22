#!/usr/bin/env python3
"""
Test script for Heart Disease Prediction Lambda Function
Run this script to test the Lambda function locally before deployment.
"""

import json
import sys
import os

# Mock boto3 to avoid import errors during local testing
class MockBoto3Client:
    def put_object(self, **kwargs):
        # Mock S3 response
        pass

    def publish(self, **kwargs):
        # Mock SNS response
        pass

class MockBoto3:
    def client(self, service):
        return MockBoto3Client()

# Mock the boto3 module
sys.modules['boto3'] = MockBoto3()


class MockCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, *args, **kwargs):
        return None


class MockConnection:
    def cursor(self):
        return MockCursor()


class MockPyMySQL:
    class cursors:
        DictCursor = object

    @staticmethod
    def connect(**kwargs):
        return MockConnection()


sys.modules['pymysql'] = MockPyMySQL()


class MockModel:
    def predict_proba(self, features):
        return [[0.7, 0.3]]


class MockJoblib:
    @staticmethod
    def load(path):
        return MockModel()


sys.modules['joblib'] = MockJoblib()

# Add the lambda directory to Python path
sys.path.append(os.path.dirname(__file__))

from lambda_function import get_rds_connection, lambda_handler, load_model, risk_category

load_model.cache_clear()
get_rds_connection.cache_clear()

def test_lambda_function():
    """Test the Lambda function with sample data"""

    # Sample event data
    test_event = {
        "body": json.dumps({
            "features": [50, 1, 2, 140, 200, 0, 1, 150, 0],  # Sample patient data
            "patient_id": "test-patient-123"
        })
    }

    # Mock context (not used in our function)
    test_context = {}

    print("🧪 Testing Lambda function...")
    print(f"Input features: {test_event['body']}")

    try:
        # Call the Lambda function
        result = lambda_handler(test_event, test_context)

        print("✅ Lambda function executed successfully")
        print(f"Status Code: {result['statusCode']}")

        if result['statusCode'] == 200:
            body = json.loads(result['body'])
            print("📊 Prediction Results:")
            print(f"  - Prediction ID: {body.get('prediction_id', 'N/A')}")
            print(f"  - Outcome: {body.get('outcome', 'N/A')}")
            print(f"  - Probability: {body.get('probability', 'N/A')}")
            print(f"  - Message: {body.get('message', 'N/A')}")
        else:
            print(f"❌ Error: {result['body']}")

    except Exception as e:
        print(f"❌ Lambda function failed: {str(e)}")
        return False

    return True

def test_risk_category():
    """Test the risk category function"""
    print("\n🧪 Testing risk_category function...")

    test_cases = [
        (0.2, "Low risk"),
        (0.5, "Medium risk"),
        (0.8, "High risk"),
        (0.33, "Medium risk"),  # Boundary test
        (0.66, "High risk")     # Boundary test
    ]

    for prob, expected in test_cases:
        result = risk_category(prob)
        if result == expected:
            print(f"✅ risk_category({prob}) = '{result}'")
        else:
            print(f"❌ risk_category({prob}) = '{result}' (expected '{expected}')")
            return False

    return True

def main():
    """Main test function"""
    print("🚀 Starting Heart Disease Prediction Lambda Tests\n")

    # Test risk category function
    if not test_risk_category():
        print("\n❌ Risk category tests failed!")
        return 1

    print("\nℹ️  This test validates local model inference and the remaining storage hooks.\n")

    if test_lambda_function():
        print("\n✅ All tests passed!")
        print("\n📋 Next steps:")
        print("1. Deploy AWS infrastructure using CloudFormation")
        print("2. Package model.pkl with the Lambda deployment zip")
        print("3. Test with real AWS resources")
        return 0
    else:
        print("\n❌ Lambda function test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())