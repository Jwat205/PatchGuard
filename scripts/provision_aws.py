"""Provision PatchGuard's free-tier AWS infrastructure with boto3.

Builds, in dependency order: VPC -> subnets -> security groups -> IAM role
-> ECR repo -> RDS (Postgres) -> ElastiCache (Redis) -> EC2 (Docker host).

Every step looks for an existing resource (by Name tag) before creating one,
so the script is safe to re-run if it fails partway through.

Prerequisites:
  - AWS credentials configured (`aws configure`, or AWS_ACCESS_KEY_ID /
    AWS_SECRET_ACCESS_KEY env vars) for an IAM user with permission to
    create VPC/EC2/RDS/ElastiCache/ECR/IAM resources.
  - boto3 installed (already in requirements.txt).

Usage:
    python scripts/provision_aws.py --region us-east-1

What you get at the end:
  - A VPC with two public subnets (needed because RDS/ElastiCache subnet
    groups require 2+ Availability Zones, even for a single-instance setup)
  - Security groups that only let the EC2 instance talk to RDS/ElastiCache
  - An EC2 t3.micro running Docker, with an IAM role that can pull from ECR
    and read/write the two DynamoDB tables
  - RDS db.t3.micro (Postgres) and ElastiCache cache.t3.micro (Redis),
    both private (no public IP) - reachable only from the EC2 security group
  - An EC2 key pair saved locally as PatchGuard.pem for SSH access

Everything above is AWS Free Tier eligible for the first 12 months on a new
account, EXCEPT the EC2 instance's data-transfer and the resources' own
always-on hours if you exceed the 750 hrs/month allowance per service.

Nothing here is destructive - it only creates resources. Deleting them is a
separate, deliberate step (see scripts/teardown_aws.py once you're done
testing) so you don't get billed for infrastructure you forgot about.
"""

from __future__ import annotations

import argparse
import json
import secrets
import stat
import sys
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

PROJECT = "patchguard"
VPC_CIDR = "10.0.0.0/16"
SUBNET_A_CIDR = "10.0.1.0/24"
SUBNET_B_CIDR = "10.0.2.0/24"

OUTPUT_FILE = Path(__file__).parent / "aws-provision-output.json"
KEY_FILE = Path(__file__).parent / f"{PROJECT}.pem"


def tag_filter(name: str) -> list[dict]:
    return [{"Name": "tag:Name", "Values": [name]}]


def my_public_ip() -> str:
    """Used to scope SSH access to the operator's own IP instead of 0.0.0.0/0."""
    with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=5) as resp:
        return resp.read().decode().strip()


# ---------------------------------------------------------------------------
# 1. Networking: VPC, subnets, internet gateway, route table
# ---------------------------------------------------------------------------
def provision_network(ec2) -> dict:
    """A VPC is an isolated network. Nothing in it can reach, or be reached
    by, anything outside it unless you explicitly wire up a route. Subnets
    slice the VPC's IP range into zones; each subnet lives in exactly one
    Availability Zone (AWS's term for an independent physical data center
    within a region). An Internet Gateway (IGW) is what gives a subnet a
    path to/from the public internet - attaching one to the VPC and adding
    a route for it is what makes a subnet "public"."""

    existing = ec2.describe_vpcs(Filters=tag_filter(f"{PROJECT}-vpc"))["Vpcs"]
    if existing:
        vpc_id = existing[0]["VpcId"]
        print(f"  VPC already exists: {vpc_id}")
    else:
        vpc = ec2.create_vpc(CidrBlock=VPC_CIDR)["Vpc"]
        vpc_id = vpc["VpcId"]
        ec2.get_waiter("vpc_available").wait(VpcIds=[vpc_id])
        ec2.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": f"{PROJECT}-vpc"}])
        # Lets EC2 instances in this VPC resolve public DNS names (needed to reach ECR/DynamoDB).
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={"Value": True})
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})
        print(f"  Created VPC: {vpc_id}")

    azs = ec2.describe_availability_zones()["AvailabilityZones"]
    az_a, az_b = azs[0]["ZoneName"], azs[1]["ZoneName"]

    def get_or_create_subnet(cidr: str, az: str, name: str) -> str:
        existing = ec2.describe_subnets(Filters=tag_filter(name))["Subnets"]
        if existing:
            print(f"  Subnet already exists: {name} ({existing[0]['SubnetId']})")
            return existing[0]["SubnetId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock=cidr, AvailabilityZone=az)["Subnet"]
        subnet_id = subnet["SubnetId"]
        ec2.create_tags(Resources=[subnet_id], Tags=[{"Key": "Name", "Value": name}])
        # "MapPublicIpOnLaunch" auto-assigns a public IP to instances launched here (EC2 needs
        # one; RDS/ElastiCache ignore this and stay private since we never give them one).
        ec2.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": True})
        print(f"  Created subnet: {name} ({subnet_id}) in {az}")
        return subnet_id

    subnet_a = get_or_create_subnet(SUBNET_A_CIDR, az_a, f"{PROJECT}-subnet-a")
    subnet_b = get_or_create_subnet(SUBNET_B_CIDR, az_b, f"{PROJECT}-subnet-b")

    existing_igw = ec2.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )["InternetGateways"]
    if existing_igw:
        igw_id = existing_igw[0]["InternetGatewayId"]
        print(f"  Internet Gateway already attached: {igw_id}")
    else:
        igw_id = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]
        ec2.create_tags(Resources=[igw_id], Tags=[{"Key": "Name", "Value": f"{PROJECT}-igw"}])
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        print(f"  Created and attached Internet Gateway: {igw_id}")

    # A route table's "0.0.0.0/0 -> igw" entry is the literal rule that makes traffic bound for
    # anywhere on the internet exit through the gateway instead of dead-ending inside the VPC.
    existing_rt = ec2.describe_route_tables(Filters=tag_filter(f"{PROJECT}-rt"))["RouteTables"]
    if existing_rt:
        rt_id = existing_rt[0]["RouteTableId"]
        print(f"  Route table already exists: {rt_id}")
    else:
        rt_id = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]["RouteTableId"]
        ec2.create_tags(Resources=[rt_id], Tags=[{"Key": "Name", "Value": f"{PROJECT}-rt"}])
        ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id)
        ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_a)
        ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_b)
        print(f"  Created route table {rt_id} and associated both subnets")

    return {"vpc_id": vpc_id, "subnet_a": subnet_a, "subnet_b": subnet_b}


# ---------------------------------------------------------------------------
# 2. Security groups: the per-resource firewalls
# ---------------------------------------------------------------------------
def provision_security_groups(ec2, vpc_id: str, my_ip: str) -> dict:
    """A security group is a stateful firewall attached to a resource (not
    a subnet) - "stateful" means a response to an allowed inbound request
    is automatically allowed back out, so you only ever write rules for the
    traffic that initiates a connection. We use three: one for the EC2 host
    (the only thing exposed to the internet), and one each for RDS/
    ElastiCache that trust *only* traffic coming from the EC2 group's ID -
    not an IP range. Referencing a security group instead of a CIDR block
    means the rule keeps working even if EC2 gets a new IP."""

    def get_or_create_sg(name: str, description: str) -> str:
        existing = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [name]}, {"Name": "vpc-id", "Values": [vpc_id]}]
        )["SecurityGroups"]
        if existing:
            print(f"  Security group already exists: {name} ({existing[0]['GroupId']})")
            return existing[0]["GroupId"]
        sg_id = ec2.create_security_group(GroupName=name, Description=description, VpcId=vpc_id)[
            "GroupId"
        ]
        ec2.create_tags(Resources=[sg_id], Tags=[{"Key": "Name", "Value": name}])
        print(f"  Created security group: {name} ({sg_id})")
        return sg_id

    app_sg = get_or_create_sg(f"{PROJECT}-app-sg", "PatchGuard EC2 app host")
    db_sg = get_or_create_sg(f"{PROJECT}-db-sg", "PatchGuard RDS Postgres")
    cache_sg = get_or_create_sg(f"{PROJECT}-cache-sg", "PatchGuard ElastiCache Redis")

    def ensure_ingress(sg_id: str, rules: list[dict]) -> None:
        try:
            ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=rules)
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidPermission.Duplicate":
                raise

    # App host: SSH from your IP only, HTTP/HTTPS from anywhere (that's the public webhook
    # endpoint GitHub calls, so it has to be reachable by anyone).
    ensure_ingress(
        app_sg,
        [
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": f"{my_ip}/32"}]},
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        ],
    )
    # Postgres: only from the app host's security group.
    ensure_ingress(
        db_sg,
        [{"IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432, "UserIdGroupPairs": [{"GroupId": app_sg}]}],
    )
    # Redis: only from the app host's security group.
    ensure_ingress(
        cache_sg,
        [{"IpProtocol": "tcp", "FromPort": 6379, "ToPort": 6379, "UserIdGroupPairs": [{"GroupId": app_sg}]}],
    )
    print(f"  Ingress rules ensured (SSH locked to {my_ip}/32)")

    return {"app_sg": app_sg, "db_sg": db_sg, "cache_sg": cache_sg}


# ---------------------------------------------------------------------------
# 3. IAM: the identity EC2 uses to talk to other AWS services
# ---------------------------------------------------------------------------
def provision_iam_role(iam) -> str:
    """Your AWS access keys authenticate *you*. The EC2 instance needs its
    own identity to call ECR/DynamoDB without you baking your keys into the
    machine (which would leak them to anyone who compromises it). An IAM
    Role is an identity with no fixed credentials - EC2 assumes it and gets
    short-lived, auto-rotating temporary credentials instead. An "instance
    profile" is just the wrapper that lets an EC2 instance actually attach
    a role at launch time."""

    role_name = f"{PROJECT}-ec2-role"
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}
        ],
    }
    try:
        iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy))
        print(f"  Created IAM role: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"  IAM role already exists: {role_name}")

    # Managed policy: lets EC2 pull images from ECR (push stays with your CI pipeline / your keys).
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    )
    # Managed policy: lets the CloudWatch agent on the box ship logs/metrics.
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
    )
    # Managed policy: lets the SSM agent register the instance so CI can run deploy commands
    # on it over the AWS API instead of opening SSH to the internet for GitHub Actions' runners.
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    )
    # Inline policy: scoped to exactly the two audit-log tables, not every table on the account.
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    region = boto3.Session().region_name
    table_arns = [
        f"arn:aws:dynamodb:{region}:{account_id}:table/{PROJECT}-pr-events",
        f"arn:aws:dynamodb:{region}:{account_id}:table/{PROJECT}-review-events",
    ]
    dynamo_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query", "dynamodb:DescribeTable"],
                "Resource": table_arns,
            }
        ],
    }
    iam.put_role_policy(
        RoleName=role_name, PolicyName=f"{PROJECT}-dynamodb-access", PolicyDocument=json.dumps(dynamo_policy)
    )

    profile_name = f"{PROJECT}-ec2-profile"
    try:
        iam.create_instance_profile(InstanceProfileName=profile_name)
        iam.add_role_to_instance_profile(InstanceProfileName=profile_name, RoleName=role_name)
        print(f"  Created instance profile: {profile_name}")
        # IAM changes take a few seconds to propagate; EC2 launch fails if we race it.
        boto3.client("iam").get_waiter("instance_profile_exists").wait(InstanceProfileName=profile_name)
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"  Instance profile already exists: {profile_name}")

    return profile_name


# ---------------------------------------------------------------------------
# 4. ECR: where your Docker image lives
# ---------------------------------------------------------------------------
def provision_ecr(ecr) -> str:
    """ECR is a private Docker registry. Your GitHub Actions build already
    pushes to ghcr.io - either point CI at ECR instead, or (simpler) have
    the EC2 box keep pulling from ghcr.io and skip ECR. This repo is
    created either way since it's free to have and useful as a fallback."""

    repo_name = PROJECT
    try:
        repo = ecr.create_repository(repositoryName=repo_name)["repository"]
        print(f"  Created ECR repository: {repo['repositoryUri']}")
        return repo["repositoryUri"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "RepositoryAlreadyExistsException":
            raise
        repo = ecr.describe_repositories(repositoryNames=[repo_name])["repositories"][0]
        print(f"  ECR repository already exists: {repo['repositoryUri']}")
        return repo["repositoryUri"]


# ---------------------------------------------------------------------------
# 5. RDS: managed Postgres
# ---------------------------------------------------------------------------
def provision_rds(rds, subnet_a: str, subnet_b: str, db_sg: str) -> dict:
    """RDS still needs a "subnet group" spanning 2+ AZs even when you only
    run one instance (db.t3.micro, no standby) - that's an RDS platform
    requirement, not something optional you can skip for a single-AZ
    deployment. AWS reserves the right to fail the instance over into the
    second AZ's subnet during maintenance, so it has to exist."""

    group_name = f"{PROJECT}-db-subnet-group"
    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=group_name,
            DBSubnetGroupDescription="PatchGuard RDS subnet group",
            SubnetIds=[subnet_a, subnet_b],
        )
        print(f"  Created DB subnet group: {group_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "DBSubnetGroupAlreadyExists":
            raise
        print(f"  DB subnet group already exists: {group_name}")

    db_id = f"{PROJECT}-postgres"
    password = secrets.token_urlsafe(24)
    try:
        rds.create_db_instance(
            DBInstanceIdentifier=db_id,
            DBName="patchguard",
            Engine="postgres",
            EngineVersion="16.4",
            DBInstanceClass="db.t3.micro",  # Free Tier: 750 hrs/month for 12 months
            AllocatedStorage=20,  # Free Tier cap
            StorageType="gp2",
            MasterUsername="patchguard",
            MasterUserPassword=password,
            VpcSecurityGroupIds=[db_sg],
            DBSubnetGroupName=group_name,
            PubliclyAccessible=False,  # No public IP - reachable only inside the VPC
            MultiAZ=False,  # Multi-AZ standby isn't free-tier eligible
            BackupRetentionPeriod=1,
            StorageEncrypted=True,
        )
        print(f"  Creating RDS instance {db_id} (takes several minutes)...")
        print(f"  Master password (SAVE THIS - shown once): {password}")
        return {"db_id": db_id, "password": password, "created": True}
    except ClientError as e:
        if e.response["Error"]["Code"] != "DBInstanceAlreadyExists":
            raise
        print(f"  RDS instance already exists: {db_id}")
        return {"db_id": db_id, "password": None, "created": False}


# ---------------------------------------------------------------------------
# 6. ElastiCache: managed Redis
# ---------------------------------------------------------------------------
def provision_elasticache(ec, subnet_a: str, subnet_b: str, cache_sg: str) -> str:
    group_name = f"{PROJECT}-cache-subnet-group"
    try:
        ec.create_cache_subnet_group(
            CacheSubnetGroupName=group_name,
            CacheSubnetGroupDescription="PatchGuard ElastiCache subnet group",
            SubnetIds=[subnet_a, subnet_b],
        )
        print(f"  Created cache subnet group: {group_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "CacheSubnetGroupAlreadyExists":
            raise
        print(f"  Cache subnet group already exists: {group_name}")

    cluster_id = f"{PROJECT}-redis"
    try:
        ec.create_cache_cluster(
            CacheClusterId=cluster_id,
            Engine="redis",
            EngineVersion="7.1",
            CacheNodeType="cache.t3.micro",  # Free Tier: 750 hrs/month for 12 months
            NumCacheNodes=1,
            CacheSubnetGroupName=group_name,
            SecurityGroupIds=[cache_sg],
        )
        print(f"  Creating ElastiCache cluster {cluster_id} (takes a few minutes)...")
    except ClientError as e:
        if e.response["Error"]["Code"] != "CacheClusterAlreadyExists":
            raise
        print(f"  ElastiCache cluster already exists: {cluster_id}")

    return cluster_id


# ---------------------------------------------------------------------------
# 7. EC2: the Docker host running the app
# ---------------------------------------------------------------------------
DOCKER_USER_DATA = """#!/bin/bash
set -euxo pipefail
dnf update -y
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
# CI's deploy step needs somewhere to find the app's runtime secrets (DATABASE_URL, REDIS_URL,
# etc.) - it only pulls a new image and restarts the container, it never carries secrets itself.
# Create /opt/patchguard/.env by hand on this box once, after provisioning, with those values.
mkdir -p /opt/patchguard
"""


def provision_ec2(ec2, subnet_a: str, app_sg: str, instance_profile: str, key_name: str) -> dict:
    """EC2 gives you a raw virtual machine - it does not come with Docker
    installed. "User data" is a shell script AWS runs once, automatically,
    the first time the instance boots (it's how we install Docker without
    having to SSH in manually). We fetch the AMI (Amazon Machine Image -
    the base OS snapshot) ID dynamically via SSM Parameter Store instead of
    hardcoding one, since Amazon publishes a new AMI ID for every patch of
    Amazon Linux and a hardcoded ID would go stale."""

    ssm = boto3.client("ssm", region_name=ec2.meta.region_name)
    ami_id = ssm.get_parameter(
        Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    )["Parameter"]["Value"]

    key_path = KEY_FILE
    key_exists = any(k["KeyName"] == key_name for k in ec2.describe_key_pairs()["KeyPairs"])
    if not key_exists:
        key = ec2.create_key_pair(KeyName=key_name, KeyType="rsa", KeyFormat="pem")
        key_path.write_text(key["KeyMaterial"])
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # chmod 600 - SSH refuses to use a wide-open key file
        print(f"  Created key pair {key_name}, saved private key to {key_path}")
    else:
        print(f"  Key pair already exists: {key_name} (reusing; private key not re-downloadable by AWS)")

    existing = ec2.describe_instances(
        Filters=tag_filter(f"{PROJECT}-app") + [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
    )
    reservations = existing.get("Reservations", [])
    if reservations:
        instance_id = reservations[0]["Instances"][0]["InstanceId"]
        print(f"  EC2 instance already exists: {instance_id}")
        return {"instance_id": instance_id}

    instance = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="t3.micro",  # Free Tier: 750 hrs/month for 12 months
        MinCount=1,
        MaxCount=1,
        KeyName=key_name,
        SecurityGroupIds=[app_sg],
        SubnetId=subnet_a,
        IamInstanceProfile={"Name": instance_profile},
        UserData=DOCKER_USER_DATA,
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": f"{PROJECT}-app"}]}
        ],
        BlockDeviceMappings=[
            {"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 20, "VolumeType": "gp2"}}  # Free Tier cap: 30GB/mo across all EBS
        ],
    )
    instance_id = instance["Instances"][0]["InstanceId"]
    print(f"  Launching EC2 instance: {instance_id}")
    return {"instance_id": instance_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--key-name", default=f"{PROJECT}-key")
    parser.add_argument("--my-ip", default=None, help="Override auto-detected public IP for SSH access")
    parser.add_argument("--skip-ec2", action="store_true", help="Provision everything except the EC2 instance")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    ec2 = session.client("ec2")
    iam = session.client("iam")
    ecr = session.client("ecr")
    rds = session.client("rds")
    elasticache = session.client("elasticache")

    my_ip = args.my_ip or my_public_ip()
    print(f"Detected public IP for SSH access: {my_ip}")

    print("\n[1/7] Networking (VPC, subnets, internet gateway, routes)")
    net = provision_network(ec2)

    print("\n[2/7] Security groups")
    sgs = provision_security_groups(ec2, net["vpc_id"], my_ip)

    print("\n[3/7] IAM role for EC2")
    instance_profile = provision_iam_role(iam)

    print("\n[4/7] ECR repository")
    ecr_uri = provision_ecr(ecr)

    print("\n[5/7] RDS Postgres")
    rds_info = provision_rds(rds, net["subnet_a"], net["subnet_b"], sgs["db_sg"])

    print("\n[6/7] ElastiCache Redis")
    cache_id = provision_elasticache(elasticache, net["subnet_a"], net["subnet_b"], sgs["cache_sg"])

    ec2_info = {}
    if not args.skip_ec2:
        print("\n[7/7] EC2 instance")
        ec2_info = provision_ec2(ec2, net["subnet_a"], sgs["app_sg"], instance_profile, args.key_name)
    else:
        print("\n[7/7] Skipped EC2 (--skip-ec2)")

    output = {
        "region": args.region,
        "network": net,
        "security_groups": sgs,
        "instance_profile": instance_profile,
        "ecr_uri": ecr_uri,
        "rds": rds_info,
        "elasticache_cluster_id": cache_id,
        "ec2": ec2_info,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nDone. Full resource summary written to {OUTPUT_FILE}")
    print("RDS and ElastiCache take several minutes to become available -")
    print("poll their status with:")
    print(f"  aws rds describe-db-instances --db-instance-identifier {rds_info['db_id']} --query 'DBInstances[0].DBInstanceStatus'")
    print(f"  aws elasticache describe-cache-clusters --cache-cluster-id {cache_id} --query 'CacheClusters[0].CacheClusterStatus'")


if __name__ == "__main__":
    sys.exit(main())
