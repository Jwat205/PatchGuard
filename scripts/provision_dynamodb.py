"""Create the DynamoDB tables PatchGuard needs, sized to stay inside the
AWS Free Tier's combined 25 RCU / 25 WCU provisioned-capacity allowance.

Usage:
    python scripts/provision_dynamodb.py [--region us-east-1] [--endpoint-url http://localhost:8001]
"""

import argparse

import boto3
from botocore.exceptions import ClientError

TABLES = [
    {
        "TableName": "patchguard-pr-events",
        "KeySchema": [{"AttributeName": "event_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "event_id", "AttributeType": "S"}],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
    {
        "TableName": "patchguard-review-events",
        "KeySchema": [
            {"AttributeName": "review_id", "KeyType": "HASH"},
            {"AttributeName": "event_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "review_id", "AttributeType": "S"},
            {"AttributeName": "event_id", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--endpoint-url", default=None, help="e.g. http://localhost:8001 for DynamoDB Local")
    args = parser.parse_args()

    client = boto3.client("dynamodb", region_name=args.region, endpoint_url=args.endpoint_url)

    for table in TABLES:
        try:
            client.create_table(**table)
            print(f"Creating {table['TableName']}...")
            client.get_waiter("table_exists").wait(TableName=table["TableName"])
            print(f"  {table['TableName']} is ACTIVE")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                print(f"  {table['TableName']} already exists, skipping")
            else:
                raise


if __name__ == "__main__":
    main()
