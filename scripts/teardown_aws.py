"""Delete everything scripts/provision_aws.py created.

Deletion has to happen in the REVERSE dependency order from creation - you
can't delete a VPC while a subnet still lives in it, or a subnet while an
EC2 instance is still attached, same as you can't delete a folder before
its files. This script mirrors provision_aws.py's steps backwards.

This IS destructive and irreversible (RDS/ElastiCache data is gone once
deleted - there's no undo). It will not run without --yes.

Usage:
    python scripts/teardown_aws.py --region us-east-1 --yes
"""

from __future__ import annotations

import argparse
import sys

import boto3
from botocore.exceptions import ClientError

PROJECT = "patchguard"


def tag_filter(name: str) -> list[dict]:
    return [{"Name": "tag:Name", "Values": [name]}]


def ignore_not_found(fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if "NotFound" not in code and code not in ("InvalidGroup.NotFound", "InvalidVpcID.NotFound", "NoSuchEntity"):
            raise


def teardown_ec2(ec2) -> None:
    reservations = ec2.describe_instances(Filters=tag_filter(f"{PROJECT}-app"))["Reservations"]
    instance_ids = [i["InstanceId"] for r in reservations for i in r["Instances"] if i["State"]["Name"] != "terminated"]
    if instance_ids:
        ec2.terminate_instances(InstanceIds=instance_ids)
        print(f"  Terminating EC2 instance(s): {instance_ids}")
        ec2.get_waiter("instance_terminated").wait(InstanceIds=instance_ids)
        print("  Terminated.")
    else:
        print("  No EC2 instance found.")

    key_name = f"{PROJECT}-key"
    ignore_not_found(ec2.delete_key_pair, KeyName=key_name)
    print(f"  Deleted key pair (if it existed): {key_name}")


def teardown_rds(rds) -> None:
    db_id = f"{PROJECT}-postgres"
    try:
        rds.delete_db_instance(DBInstanceIdentifier=db_id, SkipFinalSnapshot=True)
        print(f"  Deleting RDS instance {db_id} (takes several minutes)...")
        rds.get_waiter("db_instance_deleted").wait(DBInstanceIdentifier=db_id)
        print("  Deleted.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "DBInstanceNotFound":
            raise
        print(f"  RDS instance already gone: {db_id}")

    ignore_not_found(rds.delete_db_subnet_group, DBSubnetGroupName=f"{PROJECT}-db-subnet-group")
    print("  Deleted DB subnet group (if it existed).")


def teardown_elasticache(ec) -> None:
    cluster_id = f"{PROJECT}-redis"
    try:
        ec.delete_cache_cluster(CacheClusterId=cluster_id)
        print(f"  Deleting ElastiCache cluster {cluster_id}...")
        ec.get_waiter("cache_cluster_deleted").wait(CacheClusterId=cluster_id)
        print("  Deleted.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "CacheClusterNotFound":
            raise
        print(f"  ElastiCache cluster already gone: {cluster_id}")

    ignore_not_found(ec.delete_cache_subnet_group, CacheSubnetGroupName=f"{PROJECT}-cache-subnet-group")
    print("  Deleted cache subnet group (if it existed).")


def teardown_ecr(ecr) -> None:
    try:
        ecr.delete_repository(repositoryName=PROJECT, force=True)
        print(f"  Deleted ECR repository: {PROJECT}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "RepositoryNotFoundException":
            raise
        print(f"  ECR repository already gone: {PROJECT}")


def teardown_iam(iam) -> None:
    role_name = f"{PROJECT}-ec2-role"
    profile_name = f"{PROJECT}-ec2-profile"

    ignore_not_found(iam.remove_role_from_instance_profile, InstanceProfileName=profile_name, RoleName=role_name)
    ignore_not_found(iam.delete_instance_profile, InstanceProfileName=profile_name)
    print(f"  Deleted instance profile (if it existed): {profile_name}")

    ignore_not_found(iam.delete_role_policy, RoleName=role_name, PolicyName=f"{PROJECT}-dynamodb-access")
    for arn in (
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
        "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    ):
        ignore_not_found(iam.detach_role_policy, RoleName=role_name, PolicyArn=arn)
    ignore_not_found(iam.delete_role, RoleName=role_name)
    print(f"  Deleted IAM role (if it existed): {role_name}")


def teardown_network(ec2) -> None:
    vpcs = ec2.describe_vpcs(Filters=tag_filter(f"{PROJECT}-vpc"))["Vpcs"]
    if not vpcs:
        print("  No VPC found - nothing to tear down.")
        return
    vpc_id = vpcs[0]["VpcId"]

    # db-sg and cache-sg's ingress rules reference app-sg's GroupId as their allowed source, so
    # AWS refuses to delete app-sg while either still exists - delete the referencing groups first.
    for sg_name in (f"{PROJECT}-db-sg", f"{PROJECT}-cache-sg", f"{PROJECT}-app-sg"):
        sgs = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [sg_name]}, {"Name": "vpc-id", "Values": [vpc_id]}]
        )["SecurityGroups"]
        for sg in sgs:
            ignore_not_found(ec2.delete_security_group, GroupId=sg["GroupId"])
        print(f"  Deleted security group (if it existed): {sg_name}")

    rts = ec2.describe_route_tables(Filters=tag_filter(f"{PROJECT}-rt"))["RouteTables"]
    for rt in rts:
        for assoc in rt.get("Associations", []):
            if not assoc.get("Main"):
                ignore_not_found(ec2.disassociate_route_table, AssociationId=assoc["RouteTableAssociationId"])
        ignore_not_found(ec2.delete_route_table, RouteTableId=rt["RouteTableId"])
    print("  Deleted route table (if it existed).")

    igws = ec2.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])[
        "InternetGateways"
    ]
    for igw in igws:
        ignore_not_found(ec2.detach_internet_gateway, InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc_id)
        ignore_not_found(ec2.delete_internet_gateway, InternetGatewayId=igw["InternetGatewayId"])
    print("  Deleted internet gateway (if it existed).")

    for subnet_name in (f"{PROJECT}-subnet-a", f"{PROJECT}-subnet-b"):
        subnets = ec2.describe_subnets(Filters=tag_filter(subnet_name))["Subnets"]
        for subnet in subnets:
            ignore_not_found(ec2.delete_subnet, SubnetId=subnet["SubnetId"])
        print(f"  Deleted subnet (if it existed): {subnet_name}")

    ignore_not_found(ec2.delete_vpc, VpcId=vpc_id)
    print(f"  Deleted VPC: {vpc_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--yes", action="store_true", help="Required - confirms you want to delete everything")
    args = parser.parse_args()

    if not args.yes:
        print("This deletes RDS, ElastiCache, EC2, ECR, IAM, and networking resources")
        print("created by provision_aws.py. Data in RDS/ElastiCache is NOT recoverable.")
        print("Re-run with --yes to proceed.")
        sys.exit(1)

    session = boto3.Session(region_name=args.region)

    print("\n[1/7] EC2 instance and key pair")
    teardown_ec2(session.client("ec2"))

    print("\n[2/7] RDS Postgres")
    teardown_rds(session.client("rds"))

    print("\n[3/7] ElastiCache Redis")
    teardown_elasticache(session.client("elasticache"))

    print("\n[4/7] ECR repository")
    teardown_ecr(session.client("ecr"))

    print("\n[5/7] IAM role and instance profile")
    teardown_iam(session.client("iam"))

    print("\n[6/7 - 7/7] Security groups and networking (VPC, subnets, IGW, route table)")
    teardown_network(session.client("ec2"))

    print("\nDone. Note: DynamoDB tables are NOT deleted by this script (they're")
    print("cheap to keep and hold your audit log) - drop them manually if you want.")


if __name__ == "__main__":
    main()
